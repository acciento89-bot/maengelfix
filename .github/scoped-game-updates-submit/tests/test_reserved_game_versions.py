"""Synthetic publisher boundary tests; no real candidate, approval or provider action.

The temporary registry has an explicitly substituted test digest. Real
fixed_apps/assert_identity still parse and validate it; neither is mocked.
"""
import copy
import dataclasses
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fixtures import HERE, Fixture, Verifier, PACKAGE, NOW, digest
from test_publisher import FakeTransport
import candidate
import game_policy
import publisher

MISSING = object()
SLOTS = [
    ('de.kamilunavo.ninenine', 6, 8, [7]),
    ('de.kamilunavo.idlehandwerker', 4, 6, [5]),
    ('com.kamilunavo.runenpfad', 4, 6, [5]),
]

class ReservedGameVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Fixture()
        raw = fixture.raw()
        cls.calculator = candidate.validate_archive(raw, digest(raw), PACKAGE, fixture.catalog, Verifier(), NOW)
        cls.original = json.loads((HERE / 'known-games.json').read_bytes())

    @contextmanager
    def registry(self, package, maximum, target, reservation=MISSING, overrides=None):
        data = copy.deepcopy(self.original)
        row = next(a for a in data['apps'] if a['package'] == package)
        row.update(previousMaxCode=maximum, newVersionCode=target,
                   signedAabSha256=self.calculator.bundle_sha256,
                   signedAabBytes=len(self.calculator.aab),
                   reviewedSourceCommit='f' * 40,
                   # Synthetic source f cannot inherit exact67d-only English-shell policy.
                   uiLanguagePolicy='actual_per_frame_review')
        if reservation is MISSING:
            # Actual Rune6 now has a reservation; a missing-field fixture must
            # remove it rather than accidentally inherit the real approved row.
            row.pop('reservedUnusedVersionCodes', None)
        else:
            row['reservedUnusedVersionCodes'] = copy.deepcopy(reservation)
        if overrides:
            row.update(copy.deepcopy(overrides))
        # All modified authority lives in this synthetic temporary file. No
        # current source/native/rights approval is inferred from this fixture.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = json.dumps(data, sort_keys=True).encode()
            (root / 'known-games.json').write_bytes(raw)
            with patch.object(game_policy, 'ROOT', root), patch.object(game_policy, 'REGISTRY_SHA', digest(raw)):
                app = copy.deepcopy(game_policy.fixed_apps()[row['package']])
                app.update(listingLocales=['de-DE', 'en-US'], localeSnapshotSha256='a' * 64,
                           releaseNotes={'de-DE': 'Synthetischer Grenztest', 'en-US': 'Synthetic boundary test'},
                           rootReviewSha256='b' * 64, rightsEvidenceSha256='c' * 64,
                           optionalOriginalIcon=None, readiness='root_reviewed_candidate_inputs')
                app['frameLanguageRequirements'] = {
                    loc: [{'inAppLanguage': 'de', 'mixedUi': False,
                           'languageLimitation': '' if loc == 'de-DE' else 'Synthetic German UI fixture.',
                           'screenScope': 'practice'} for _ in range(4)]
                    for loc in app['listingLocales']}
                c = dataclasses.replace(self.calculator, package=app['package'], app=app)
                yield c, root

    @staticmethod
    def uploads(http):
        return [x for x in http.calls if x[0] == 'POST' and x[1].split('?')[0].endswith('/bundles')]

    def assert_stopped_before_payload(self, c, http=None, family='game5'):
        http = http or FakeTransport(c)
        report = publisher.submit_candidate(c, http, family=family)
        self.assertFalse(report['ok'])
        self.assertEqual(self.uploads(http), [])
        self.assertFalse(any(x[0] == 'PUT' or ':commit?' in x[1] for x in http.calls))
        self.assertEqual(http.edits, {})
        return report, http

    def test_all_three_reserved_owned_game_steps_upload_once_and_read_back(self):
        for package, maximum, target, reserved in SLOTS:
            with self.subTest(package=package), self.registry(package, maximum, target, reserved) as (c, _):
                http = FakeTransport(c)
                report = publisher.submit_candidate(c, http, family='game5')
                self.assertTrue(report['ok'], report.get('stopReason'))
                self.assertEqual(report['status'], 'submitted_for_review')
                self.assertEqual(len(self.uploads(http)), 1)
                self.assertEqual(http.commits, 1)
                self.assertTrue(report['readbackVerified'])
                self.assertEqual(http.edits, {})
                self.assertTrue(all(x['confirmed'] for x in report['cleanup']))

    def test_missing_extra_unknown_duplicate_or_wrong_type_reservations_never_upload(self):
        for package, maximum, target, reserved in SLOTS:
            bad = [MISSING, [], reserved + [target], [target + 100], reserved * 2,
                   str(reserved[0]), [float(reserved[0])], [True], [[reserved[0]]]]
            for value in bad:
                with self.subTest(package=package, reservation=repr(value)), self.registry(package, maximum, target, value) as (c, _):
                    self.assert_stopped_before_payload(c)

    def test_caller_reservation_cannot_replace_missing_immutable_registry_field(self):
        for package, maximum, target, reserved in SLOTS:
            with self.subTest(package=package), self.registry(package, maximum, target) as (c, _):
                c.app['reservedUnusedVersionCodes'] = reserved
                c.app['allowReservedVersion'] = True
                self.assert_stopped_before_payload(c)

    def test_candidate_reservation_source_or_binary_must_match_immutable_registry(self):
        for key, value in [('reservedUnusedVersionCodes', [100]), ('reviewedSourceCommit', 'e' * 40),
                           ('signedAabSha256', '0' * 64), ('newVersionCode', 9),
                           ('package', 'com.kamilunavo.onemorefloor')]:
            with self.subTest(field=key), self.registry(*SLOTS[0]) as (c, _):
                c.app[key] = value
                _, http = self.assert_stopped_before_payload(c)
                self.assertEqual(http.calls, [])

    def test_registry_digest_tampering_stops_before_edit(self):
        with self.registry(*SLOTS[0]) as (c, root):
            path = root / 'known-games.json'
            changed = json.loads(path.read_bytes())
            row = next(a for a in changed['apps'] if a['package'] == c.package)
            row['reviewedSourceCommit'] = 'e' * 40
            c.app['reviewedSourceCommit'] = 'e' * 40
            # Keep a valid five-game shape and matching candidate: only the
            # original digest pin can reject this post-approval byte change.
            path.write_text(json.dumps(changed, sort_keys=True))
            _, http = self.assert_stopped_before_payload(c)
            self.assertEqual(http.calls, [])

    def test_other_gap_maximum_target_package_and_family_are_not_reserved_slots(self):
        cases = [
            ('de.kamilunavo.ninenine', 5, 8, [7], {'previousProductionCode': 5}, 'game5'),
            ('de.kamilunavo.ninenine', 6, 9, [7], None, 'game5'),
            ('com.kamilunavo.runenpfad', 4, 7, [5], None, 'game5'),
            ('com.kamilunavo.runenpfad', 4, 6, [5], {'package': 'com.kamilunavo.onemorefloor'}, 'game5'),
            ('com.kamilunavo.runenpfad', 4, 6, [5], None, 'calculator9'),
            ('com.kamilunavo.runenpfad', 4, 6, [5], None, 'future_games'),
        ]
        for package, maximum, target, reserved, overrides, family in cases:
            with self.subTest(case=(package, maximum, target, family)), self.registry(package, maximum, target, reserved, overrides) as (c, _):
                self.assert_stopped_before_payload(c, family=family)

    def test_all_existing_consecutive_game_steps_stay_valid_without_reservations(self):
        for original in self.original['apps']:
            maximum = original['previousMaxCode']
            with self.subTest(package=original['package']), self.registry(original['package'], maximum, maximum + 1) as (c, _):
                http = FakeTransport(c)
                report = publisher.submit_candidate(c, http, family='game5')
                self.assertTrue(report['ok'], report.get('stopReason'))
                self.assertEqual(http.commits, 1)

    def test_calculator_consecutive_path_and_gap_rejection_are_unchanged(self):
        c = copy.deepcopy(self.calculator)
        c.app['reservedUnusedVersionCodes'] = [c.app['newVersionCode']]
        http = FakeTransport(c)
        self.assertTrue(publisher.submit_candidate(c, http)['ok'])
        c.app['newVersionCode'] += 1
        _, http = self.assert_stopped_before_payload(c, family='calculator9')
        self.assertEqual(http.calls, [])

    def test_future_test_registry_does_not_enable_successor_under_real_current_registry(self):
        with self.registry(*SLOTS[0]) as (c, _):
            successor = copy.deepcopy(c)
        _, http = self.assert_stopped_before_payload(successor)
        self.assertEqual(http.calls, [])
        raw = (HERE / 'game-catalog.json').read_bytes()
        catalog = game_policy.load_catalog(HERE / 'game-catalog.json', digest(raw))
        for row in catalog.values():
            if row['package'] == 'com.kamilunavo.runenpfad':
                self.assertEqual(row['reviewedSourceCommit'], 'd84b3e2e00514a38fc21a5da31950d2ddceebfd3')
                self.assertEqual(row['rootReviewSha256'], '5ee7e6a6572620ce1e7dc39c2c54a3a483d1575aa58f7391b76fb108aa1b99f8')
                game_policy.require_ready(row)
            elif row['package'] == 'de.kamilunavo.idlehandwerker':
                self.assertEqual(row['reviewedSourceCommit'], 'b984e914e18c0d007066c13c571d1c157eafb26a')
                self.assertEqual(row['rootReviewSha256'], 'b13c64ca74acdd85e6501cc6926edb1fd47577a5a4e8df81dfb13dfb8bb7d0d9')
                game_policy.require_ready(row)
            elif row['package'] == 'de.kamilunavo.ninenine':
                self.assertEqual(row['reviewedSourceCommit'], '67d236b7d35b70b59693a730164a0d8426409ee5')
                self.assertEqual(row['rootReviewSha256'], 'b31e9637d88b739fe4197c97862a80168ea8cdf2b01722d4bfbd6ba8f5a5ccb8')
                game_policy.require_ready(row)
            elif row['package'] == 'com.kamilunavo.perfectdrop':
                self.assertEqual(row['reviewedSourceCommit'], '499018036a5b12375fa7fbfcec9556ed177fd435')
                self.assertEqual(row['rootReviewSha256'], 'd124dd053e6de869d593376f718024f98cb088f334e71fb4afdaf750d8b4f041')
                game_policy.require_ready(row)
                self.assertFalse(game_policy.allows_reserved_game_step(row, row['previousMaxCode'], 'game5'))
                pending = copy.deepcopy(row); pending['rootReviewSha256'] = None
                with self.assertRaises(candidate.CandidateError):
                    game_policy.require_ready(pending)
            else:
                self.assertEqual(row['package'], 'com.kamilunavo.risingsteps')
                self.assertEqual((row['previousMaxCode'], row['newVersionCode']), (8, 9))
                self.assertEqual(row['reviewedSourceCommit'], '8245a0d495163e647f0f97dba330906034847f76')
                self.assertEqual(row['rootReviewSha256'], 'e7d8708be1187177ee1795a3f566a6e86d1901999f2a2d53ace700377764633e')
                self.assertEqual(row['rightsEvidenceSha256'], '3d2c6f285b19c8fd55ebd385354af7d020d18b6ed5789acb5e76c002508148b8')
                game_policy.require_ready(row)
                self.assertFalse(game_policy.allows_reserved_game_step(row, 8, 'game5'))
                pending = copy.deepcopy(row); pending['rootReviewSha256'] = None
                with self.assertRaises(candidate.CandidateError):
                    game_policy.require_ready(pending)

    def test_fresh_production_maximum_or_production_status_changes_still_stop(self):
        for slot in SLOTS:
            for mode in ['production', 'maximum', 'rollout', 'target_uploaded', 'newer_uploaded']:
                with self.subTest(slot=slot[0], mode=mode), self.registry(*slot) as (c, _):
                    http = FakeTransport(c)
                    if mode == 'production':
                        http.live['tracks']['tracks'][0]['releases'][0]['versionCodes'] = ['1']
                    elif mode == 'maximum':
                        http.live['bundles']['bundles'][0]['versionCode'] += 1
                    elif mode == 'rollout':
                        http.live['tracks']['tracks'][0]['releases'][0]['status'] = 'inProgress'
                    else:
                        http.live['bundles']['bundles'].append({'versionCode': c.app['newVersionCode'] + (mode == 'newer_uploaded'), 'sha256': c.bundle_sha256})
                    self.assert_stopped_before_payload(c, http)

    def test_reserved_candidate_replay_is_readonly_noop_without_second_upload_or_commit(self):
        with self.registry(*SLOTS[0]) as (c, _):
            http = FakeTransport(c)
            self.assertTrue(publisher.submit_candidate(c, http, family='game5')['ok'])
            http.calls.clear()
            report = publisher.submit_candidate(c, http, family='game5')
            self.assertTrue(report['ok'])
            self.assertEqual(report['status'], 'noop_already_present')
            self.assertEqual(http.commits, 1)
            self.assertEqual(self.uploads(http), [])
            self.assertFalse(any(':commit?' in x[1] or x[0] == 'PUT' for x in http.calls))
            self.assertEqual(http.edits, {})

    def test_reserved_commit_in_review_still_stops_once_and_cleans_owned_edit(self):
        with self.registry(*SLOTS[0]) as (c, _):
            http = FakeTransport(c, {'commit': publisher.Response(400, {'reason': 'CHANGES_ALREADY_IN_REVIEW'})})
            report = publisher.submit_candidate(c, http, family='game5')
            self.assertFalse(report['ok'])
            self.assertEqual(report['status'], 'blocked_in_review')
            self.assertEqual(len([x for x in http.calls if ':commit?' in x[1]]), 1)
            self.assertEqual(http.edits, {})
            self.assertFalse(any('CANCEL' in x[1] for x in http.calls))

    def test_reserved_unknown_upload_or_commit_never_retries_and_retains_cleanup_policy(self):
        for phase in ['upload', 'commit']:
            with self.subTest(phase=phase), self.registry(*SLOTS[0]) as (c, _):
                http = FakeTransport(c, {phase: publisher.TransportError('synthetic unknown')})
                report = publisher.submit_candidate(c, http, family='game5')
                self.assertFalse(report['ok'])
                self.assertEqual(report['status'], 'reconciliation_required')
                self.assertEqual(len(self.uploads(http)), 1)
                commits = [x for x in http.calls if ':commit?' in x[1]]
                self.assertEqual(len(commits), int(phase == 'commit'))
                if phase == 'upload':
                    self.assertEqual(http.edits, {})
                else:
                    self.assertEqual(len(http.edits), 1)
                    self.assertFalse(report['cleanup'][0]['attempted'])

    def test_reserved_readback_mismatch_never_reports_success(self):
        with self.registry(*SLOTS[0]) as (c, _):
            http = FakeTransport(c)
            original = http.request
            def change_after_commit(method, path, body=None, media=None):
                response = original(method, path, body, media)
                if ':commit?' in path:
                    http.live['tracks']['tracks'][0]['releases'][0]['inAppUpdatePriority'] = 5
                return response
            http.request = change_after_commit
            report = publisher.submit_candidate(c, http, family='game5')
            self.assertFalse(report['ok'])
            self.assertEqual(report['status'], 'reconciliation_required')
            self.assertEqual(http.commits, 1)
            self.assertEqual(http.edits, {})

    def test_identity_is_rechecked_at_reserved_gap_before_upload(self):
        with self.registry(*SLOTS[0]) as (c, _):
            http = FakeTransport(c)
            original = http.request
            def change_during_snapshot(method, path, body=None, media=None):
                response = original(method, path, body, media)
                if method == 'GET' and '/listings/en-US/icon' in path:
                    c.app['reviewedSourceCommit'] = 'e' * 40
                return response
            http.request = change_during_snapshot
            self.assert_stopped_before_payload(c, http)
