import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import preflight

CATALOG = HERE / "production-packages.json"
PACKAGE = "de.kamilunavo.brennercalc"
SECOND = "de.kamilunavo.hydrocalc"
BUNDLES = {"kind": "androidpublisher#bundlesListResponse", "bundles": [{"versionCode": 7, "sha256": "a" * 64}]}
APKS = {"kind": "androidpublisher#apksListResponse", "apks": [{"versionCode": 11, "binary": {"sha256": "b" * 64}}]}
TRACKS = {"kind": "androidpublisher#tracksListResponse", "tracks": [
    {"track": "production", "releases": [{"status": "completed", "versionCodes": ["6"]}]},
    {"track": "beta", "releases": [{"status": "draft", "versionCodes": ["12"]}]},
]}


class FakeTransport:
    def __init__(self, failures=None):
        self.failures = failures or {}
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        key = (method, path.split("/")[-1])
        override = self.failures.get(key)
        if isinstance(override, BaseException):
            raise override
        if override is not None:
            return override
        if method == "POST":
            return preflight.Response(201, {"id": "owned-edit"})
        if method == "DELETE":
            return preflight.Response(204, None)
        return preflight.Response(200, {"bundles": BUNDLES, "apks": APKS, "tracks": TRACKS}[key[1]])


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.catalog = preflight.load_catalog(CATALOG, hashlib.sha256(CATALOG.read_bytes()).hexdigest())

    def audit(self, transport, packages=None, checkpoint=None):
        return preflight.audit_packages(packages or [PACKAGE], self.catalog, transport, checkpoint)

    def test_reads_bundle_apk_and_every_track_code_then_deletes_exact_owned_edit(self):
        http = FakeTransport()
        report = self.audit(http)
        app = report["apps"][0]
        self.assertTrue(report["ok"])
        self.assertEqual(app["maxCode"], 11)
        self.assertEqual(app["maxCodeIncludingTracks"], 12)
        self.assertEqual(app["productionTrack"]["releases"], [{"status": "completed", "versionCodes": [6]}])
        self.assertEqual(app["cleanup"], {"attempted": True, "confirmed": True, "httpStatus": 204})
        self.assertEqual([(m, p) for m, p, _ in http.calls], [
            ("POST", f"/applications/{PACKAGE}/edits"),
            ("GET", f"/applications/{PACKAGE}/edits/owned-edit/bundles"),
            ("GET", f"/applications/{PACKAGE}/edits/owned-edit/apks"),
            ("GET", f"/applications/{PACKAGE}/edits/owned-edit/tracks"),
            ("DELETE", f"/applications/{PACKAGE}/edits/owned-edit"),
        ])

    def test_partial_read_failure_cleans_up_and_never_turns_partial_max_into_complete_max(self):
        http = FakeTransport({("GET", "apks"): preflight.Response(500, {"error": "sensitive provider body"})})
        report = self.audit(http)
        app = report["apps"][0]
        self.assertFalse(report["ok"])
        self.assertIsNone(app["maxCode"])
        self.assertEqual(app["resourceStatus"]["apks"], "http_500")
        self.assertIsNotNone(app["productionTrack"])
        self.assertTrue(app["cleanup"]["confirmed"])
        self.assertEqual(http.calls[-1][0], "DELETE")
        self.assertNotIn("sensitive provider body", json.dumps(report))

    def test_network_error_is_sanitized_and_owned_edit_still_deleted(self):
        http = FakeTransport({("GET", "bundles"): OSError("secret_token_do_not_log")})
        report = self.audit(http)
        self.assertFalse(report["ok"])
        self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])
        self.assertNotIn("secret_token_do_not_log", json.dumps(report))

    def test_cleanup_failure_stops_before_creating_another_app_edit(self):
        http = FakeTransport({("DELETE", "owned-edit"): preflight.Response(503, None)})
        report = self.audit(http, [PACKAGE, SECOND])
        self.assertFalse(report["ok"])
        self.assertFalse(report["apps"][0]["cleanup"]["confirmed"])
        self.assertEqual(len([x for x in http.calls if x[0] == "POST"]), 1)
        self.assertEqual(report["stoppedBecause"], "cleanup_unconfirmed")

    def test_cleanup_404_confirms_the_owned_edit_is_absent(self):
        report = self.audit(FakeTransport({("DELETE", "owned-edit"): preflight.Response(404, None)}))
        self.assertTrue(report["ok"])
        self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])

    def test_unknown_create_outcome_is_not_retried_or_claimed_clean(self):
        http = FakeTransport({("POST", "edits"): TimeoutError("token in exception")})
        report = self.audit(http, [PACKAGE, SECOND])
        self.assertFalse(report["ok"])
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(report["stoppedBecause"], "create_outcome_unknown")
        self.assertFalse(report["apps"][0]["cleanup"]["confirmed"])

    def test_malformed_edit_id_cannot_escape_into_a_different_endpoint(self):
        http = FakeTransport({("POST", "edits"): preflight.Response(201, {"id": "../other:commit"})})
        report = self.audit(http)
        self.assertFalse(report["ok"])
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(report["stoppedBecause"], "create_outcome_unknown")

    def test_missing_existing_app_is_reported_without_creating_or_replacing_a_listing(self):
        http = FakeTransport({("POST", "edits"): preflight.Response(404, None)})
        report = self.audit(http)
        self.assertFalse(report["ok"])
        self.assertIsNone(report["apps"][0]["maxCode"])
        self.assertEqual(http.calls, [("POST", f"/applications/{PACKAGE}/edits", {})])

    def test_interrupt_after_creation_runs_finally_cleanup_and_stops_scope(self):
        http = FakeTransport({("GET", "bundles"): KeyboardInterrupt()})
        report = self.audit(http, [PACKAGE, SECOND])
        self.assertFalse(report["ok"])
        self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])
        self.assertEqual(report["stoppedBecause"], "interrupted")
        self.assertEqual(http.calls[-1][0], "DELETE")

    def test_interrupt_after_client_records_ownership_before_runner_journals_id_still_deletes(self):
        real_publisher = preflight.Publisher

        class InterruptAfterOwnership(real_publisher):
            def request(self, method, *args, **kwargs):
                response = super().request(method, *args, **kwargs)
                if method == "POST":
                    raise preflight.AuditInterrupted()
                return response

        http = FakeTransport()
        with patch.object(preflight, "Publisher", InterruptAfterOwnership):
            report = self.audit(http, [PACKAGE, SECOND])
        self.assertFalse(report["ok"])
        self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])
        self.assertEqual([x[0] for x in http.calls], ["POST", "DELETE"])
        self.assertEqual(http.calls[-1][1], f"/applications/{PACKAGE}/edits/owned-edit")

    def test_checkpoint_write_failure_cannot_bypass_cleanup(self):
        def broken_checkpoint(report):
            if any(x.get("editId") and not x["cleanup"]["attempted"] for x in report["apps"]):
                raise OSError("disk failure with sensitive detail")
        http = FakeTransport()
        report = self.audit(http, [PACKAGE, SECOND], broken_checkpoint)
        self.assertFalse(report["ok"])
        self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])
        self.assertEqual([x[0] for x in http.calls], ["POST", "DELETE"])
        self.assertNotIn("sensitive detail", json.dumps(report))

    def test_invalid_code_or_response_does_not_become_a_zero_or_trusted_max(self):
        for payload in [{"bundles": [{"versionCode": True}]}, {"bundles": [{"versionCode": -1}]}, {"bundles": "not-an-array"}, None]:
            with self.subTest(payload=payload):
                report = self.audit(FakeTransport({("GET", "bundles"): preflight.Response(200, payload)}))
                self.assertFalse(report["ok"])
                self.assertIsNone(report["apps"][0]["maxCode"])
                self.assertTrue(report["apps"][0]["cleanup"]["confirmed"])

    def test_no_observed_uploads_is_not_reported_as_max_code_zero(self):
        report = self.audit(FakeTransport({("GET", "bundles"): preflight.Response(200, {}), ("GET", "apks"): preflight.Response(200, {}), ("GET", "tracks"): preflight.Response(200, {})}))
        self.assertFalse(report["ok"])
        self.assertIsNone(report["apps"][0]["maxCode"])

    def test_excluded_or_unknown_packages_cannot_reach_transport(self):
        for package in ["de.kamilunavo.arbeitsklar", "com.kamilunavo.onemorefloor", "de.kamilunavo.onemorefloor", "com.kamilunavo.duocompare", "com.kamilunavo.dungeonarchitect", "com.kamilunavo.monsterautotactics", "com.kamilunavo.pocketrail", "com.kamilunavo.gildenfunke", "com.unknown.missing"]:
            with self.subTest(package=package):
                http = FakeTransport()
                with self.assertRaises(preflight.ScopeError):
                    self.audit(http, [package])
                self.assertEqual(http.calls, [])

    def test_publisher_surface_rejects_upload_track_write_commit_and_unowned_delete(self):
        http = FakeTransport()
        publisher = preflight.Publisher(http, self.catalog)
        publisher.request("POST", PACKAGE)
        for method, edit, resource in [("POST", "owned-edit", "bundles"), ("PUT", "owned-edit", "tracks"), ("PATCH", "owned-edit", "tracks"), ("POST", "owned-edit", ":commit"), ("DELETE", "somebody-elses-edit", None)]:
            with self.subTest(method=method, resource=resource):
                with self.assertRaises(preflight.ScopeError):
                    publisher.request(method, PACKAGE, edit, resource)
        self.assertEqual(len(http.calls), 1)

    def test_catalog_hash_and_existing_app_id_are_required(self):
        with self.assertRaises(preflight.ScopeError):
            preflight.load_catalog(CATALOG, "0" * 64)
        data = json.loads(CATALOG.read_text())
        data["apps"][0]["appId"] = None
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "catalog.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(preflight.ScopeError):
                preflight.load_catalog(p, hashlib.sha256(p.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
