#!/usr/bin/env python3
"""Bounded Publisher inventory; owns temporary edits, never writes releases."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


EXCLUDED = frozenset({
    "de.kamilunavo.arbeitsklar", "com.kamilunavo.onemorefloor", "de.kamilunavo.onemorefloor",
    "com.kamilunavo.duocompare", "com.kamilunavo.dungeonarchitect",
    "com.kamilunavo.monsterautotactics", "com.kamilunavo.pocketrail", "com.kamilunavo.gildenfunke",
})
READ_RESOURCES = ("bundles", "apks", "tracks")


class ScopeError(ValueError):
    pass


class TransportError(Exception):
    pass


class AuditInterrupted(Exception):
    pass


class CheckpointError(Exception):
    pass


@dataclass
class Response:
    status: int
    data: object


def load_catalog(file, expected_sha256):
    raw = Path(file).read_bytes()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256 or "") or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ScopeError("Catalog hash mismatch")
    data = json.loads(raw)
    apps = data.get("apps")
    if data.get("schema") != 1 or not isinstance(apps, list) or len(apps) != 26:
        raise ScopeError("Expected the approved26-app catalog")
    catalog = {}
    ids = set()
    for app in apps:
        package = app.get("package")
        app_id = app.get("appId")
        if (not isinstance(package, str) or not re.fullmatch(r"(?:de|com)\.kamilunav(?:o)?\.[a-z0-9_.]+", package)
                or package in EXCLUDED or package in catalog or "onemorefloor" in package
                or not isinstance(app_id, str) or not re.fullmatch(r"[0-9]{19}", app_id)
                or app_id in ids or app.get("visibleStatus") != "Produktion"):
            raise ScopeError("Catalog contains a missing, duplicate, excluded or non-production identity")
        catalog[package] = {"package": package, "appId": app_id}
        ids.add(app_id)
    return catalog


class Publisher:
    """Only temporary-edit create, owned-edit reads, and owned-edit delete exist."""
    def __init__(self, transport, catalog):
        self.transport = transport
        self.catalog = catalog
        self.owned = set()

    def request(self, method, package, edit_id=None, resource=None):
        if package not in self.catalog or package in EXCLUDED:
            raise ScopeError("Package is outside approved scope")
        base = "/applications/" + package + "/edits"
        if method == "POST" and edit_id is None and resource is None:
            response = self.transport.request("POST", base, {})
            if 200 <= response.status < 300:
                created = response.data.get("id") if isinstance(response.data, dict) else None
                if not isinstance(created, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", created):
                    raise ScopeError("Unusable create response; outcome is unknown")
                self.owned.add((package, created))
            return response
        if (package, edit_id) not in self.owned:
            raise ScopeError("Cannot access an unowned edit")
        if method == "GET" and resource in READ_RESOURCES:
            return self.transport.request("GET", base + "/" + edit_id + "/" + resource)
        if method == "DELETE" and resource is None:
            response = self.transport.request("DELETE", base + "/" + edit_id)
            if 200 <= response.status < 300 or response.status == 404:
                self.owned.remove((package, edit_id))
            return response
        raise ScopeError("Upload, track writes and edit commit are not permitted")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class HttpTransport:
    def __init__(self, token):
        self._token = token
        self._opener = build_opener(NoRedirect())

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request("https://androidpublisher.googleapis.com/androidpublisher/v3" + path,
                          data=data, method=method,
                          headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=5 if method == "DELETE" else 10) as result:
                raw = result.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    return Response(result.status, None)
                try:
                    parsed = json.loads(raw) if raw else None
                except (ValueError, UnicodeDecodeError):
                    parsed = None
                return Response(result.status, parsed)
        except HTTPError as error:
            # Error bodies and exception text may include sensitive request details.
            return Response(error.code, None)
        except (URLError, OSError, TimeoutError):
            raise TransportError("HTTP transport failed") from None


def _code(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError("Invalid version code")
    number = int(value)
    if not 1 <= number <= 2100000000:
        raise ValueError("Invalid version code")
    return number


def _array(data, field):
    if not isinstance(data, dict) or not isinstance(data.get(field, []), list):
        raise ValueError("Malformed response")
    return data.get(field, [])


def _uploads(data, field):
    uploads = []
    for item in _array(data, field):
        if not isinstance(item, dict):
            raise ValueError("Malformed upload")
        row = {"versionCode": _code(item.get("versionCode"))}
        binary = item.get("binary", {}) if field == "apks" else item
        if not isinstance(binary, dict):
            raise ValueError("Malformed upload hash")
        digest = binary.get("sha256")
        if digest is not None:
            if not isinstance(digest, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
                raise ValueError("Malformed upload hash")
            row["sha256"] = digest.lower()
        uploads.append(row)
    return uploads


def _tracks(data):
    tracks = []
    names = set()
    for item in _array(data, "tracks"):
        if not isinstance(item, dict):
            raise ValueError("Malformed track")
        name = item.get("track")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", name) or name in names:
            raise ValueError("Malformed or duplicate track")
        names.add(name)
        releases = []
        for release in _array(item, "releases"):
            if not isinstance(release, dict) or release.get("status") not in {"draft", "inProgress", "halted", "completed"}:
                raise ValueError("Malformed release")
            row = {"status": release["status"], "versionCodes": [_code(x) for x in _array(release, "versionCodes")]}
            if "userFraction" in release:
                fraction = release["userFraction"]
                if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1:
                    raise ValueError("Malformed rollout")
                row["userFraction"] = fraction
            releases.append(row)
        tracks.append({"track": name, "releases": releases})
    return tracks


def audit_packages(packages, catalog, transport, checkpoint=None):
    if not packages or len(set(packages)) != len(packages) or any(p not in catalog or p in EXCLUDED for p in packages):
        raise ScopeError("Requested scope is not approved")
    report = {"ok": False, "requestedPackages": list(packages), "apps": [], "stoppedBecause": None}
    publisher = Publisher(transport, catalog)

    def save():
        if checkpoint:
            try:
                checkpoint(report)
            except OSError:
                raise CheckpointError("Report checkpoint failed") from None

    for package in packages:
        row = {**catalog[package], "status": "started", "editId": None,
               "resourceStatus": {}, "bundles": [], "apks": [], "allTracks": [],
               "productionTrack": None, "maxCode": None, "maxCodeIncludingTracks": None,
               "cleanup": {"attempted": False, "confirmed": False, "httpStatus": None}}
        report["apps"].append(row)
        stop = None
        try:
            save()
            created = publisher.request("POST", package)
            if not 200 <= created.status < 300:
                row["status"] = "create_http_" + str(created.status)
                # A definitive4xx rejection created no owned edit.5xx may have an unknown outcome.
                row["cleanup"]["confirmed"] = 400 <= created.status < 500
                if not row["cleanup"]["confirmed"]:
                    stop = "create_outcome_unknown"
            else:
                row["editId"] = created.data["id"]
                save()  # Journal ownership before any subsequent API call.
                for resource in READ_RESOURCES:
                    try:
                        response = publisher.request("GET", package, row["editId"], resource)
                        if not 200 <= response.status < 300:
                            row["resourceStatus"][resource] = "http_" + str(response.status)
                            continue
                        if resource == "tracks":
                            row["allTracks"] = _tracks(response.data)
                            row["productionTrack"] = next((x for x in row["allTracks"] if x["track"] == "production"), None)
                        else:
                            row[resource] = _uploads(response.data, resource)
                        row["resourceStatus"][resource] = "ok"
                    except (TransportError, OSError, TimeoutError):
                        row["resourceStatus"][resource] = "transport_error"
                    except (ValueError, TypeError, KeyError):
                        row["resourceStatus"][resource] = "malformed_response"
                complete = all(row["resourceStatus"].get(x) == "ok" for x in READ_RESOURCES)
                codes = [x["versionCode"] for x in row["bundles"] + row["apks"]]
                track_codes = [c for t in row["allTracks"] for r in t["releases"] for c in r["versionCodes"]]
                if complete and codes:
                    row["maxCode"] = max(codes)
                    row["maxCodeIncludingTracks"] = max(codes + track_codes)
                    row["status"] = "ok"
                else:
                    row["status"] = "partial_read_failure" if not complete else "no_upload_codes"
        except (AuditInterrupted, KeyboardInterrupt):
            row["status"] = "interrupted"
            stop = "interrupted" if row["editId"] else "create_outcome_unknown"
        except CheckpointError:
            row["status"] = "checkpoint_failed"
            stop = "checkpoint_failed"
        except (TransportError, OSError, TimeoutError, ScopeError):
            row["status"] = "create_outcome_unknown"
            stop = "create_outcome_unknown"
        finally:
            # A signal can arrive after the client recorded the create response,
            # before the caller assigns/journals it. Ownership still requires cleanup.
            if not row["editId"]:
                row["editId"] = next((edit for owner, edit in publisher.owned if owner == package), None)
                if row["editId"] and row["status"] == "interrupted":
                    stop = "interrupted"
            if row["editId"]:
                row["cleanup"]["attempted"] = True
                try:
                    deleted = publisher.request("DELETE", package, row["editId"])
                    row["cleanup"]["httpStatus"] = deleted.status
                    row["cleanup"]["confirmed"] = 200 <= deleted.status < 300 or deleted.status == 404
                except (TransportError, OSError, TimeoutError, AuditInterrupted, KeyboardInterrupt):
                    row["cleanup"]["confirmed"] = False
                if not row["cleanup"]["confirmed"]:
                    row["status"] = "cleanup_unconfirmed"
                    stop = "cleanup_unconfirmed"
            try:
                save()
            except CheckpointError:
                stop = stop or "checkpoint_failed"
        if stop:
            report["stoppedBecause"] = stop
            break
    report["ok"] = (len(report["apps"]) == len(packages) and report["stoppedBecause"] is None
                    and all(x["status"] == "ok" and x["cleanup"]["confirmed"] for x in report["apps"]))
    return report


def write_report(file, report):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=file.parent, delete=False) as handle:
            temporary = handle.name
            json.dump(report, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, file)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).with_name("production-packages.json"))
    parser.add_argument("--expected-catalog-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    initial = {"ok": False, "status": "not_started", "startedAtUTC": started, "apps": []}
    write_report(args.report, initial)
    try:
        catalog = load_catalog(args.catalog, args.expected_catalog_sha256)
    except (ScopeError, ValueError, OSError):
        initial["status"] = "catalog_rejected"
        write_report(args.report, initial)
        return 1
    token = os.environ.pop("TOKEN", "")
    if not token:
        initial["status"] = "runtime_auth_missing"
        write_report(args.report, initial)
        return 1

    def interrupted(signum, frame):
        raise AuditInterrupted("Interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    def checkpoint(current):
        write_report(args.report, {"startedAtUTC": started, **current})

    report = audit_packages(list(catalog), catalog, HttpTransport(token), checkpoint)
    report["startedAtUTC"] = started
    report["finishedAtUTC"] = datetime.now(timezone.utc).isoformat()
    report["catalogSha256"] = args.expected_catalog_sha256
    report["sourceInventory"] = json.loads(args.catalog.read_text())["source"]
    report["providerWrites"] = "Temporary owned-edit create/delete only; no upload, track mutation or commit"
    write_report(args.report, report)
    print(json.dumps({"ok": report["ok"], "appsAudited": len(report["apps"]), "stoppedBecause": report["stoppedBecause"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
