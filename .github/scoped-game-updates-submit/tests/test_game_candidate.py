import copy,dataclasses,inspect,unittest
from fixtures import HERE,NOW,digest
from game_fixtures import GameFixture,FixtureVerifier,ready_app
from test_publisher import FakeTransport
import candidate,publisher,game_policy

class GameCandidateTests(unittest.TestCase):
    def enabled(self):self.assertIn('family',inspect.signature(candidate.validate_archive).parameters,'Game verifier adapter missing')
    def test_synthetic_fixture_exercises_complete_validator_without_product_qa(self):
        self.enabled();f=GameFixture(self);raw=f.raw();c=candidate.validate_archive(raw,digest(raw),f.package,f.catalog,FixtureVerifier(),NOW,family='game5');self.assertEqual(c.bundle_sha256,f.app['signedAabSha256']);self.assertTrue(f.qa['syntheticFixtureOnly'])
    def test_pending_native_or_root_rights_review_blocks_exact_known_binary(self):
        self.enabled()
        for mode in ['native','root','rights','apk']:
            f=GameFixture(self)
            if mode=='native':f.qa['outcome']='pending'
            elif mode=='root':f.review['rootVisuallyReviewedAllEight']=False
            elif mode=='rights':f.rights['outcome']='pending'
            else:f.qa['testedApkSha256']='a'*64
            raw=f.raw()
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):candidate.validate_archive(raw,digest(raw),f.package,f.catalog,FixtureVerifier(),NOW,family='game5')
    def test_german_only_idle_and_nine_english_only_practice_cannot_be_called_global_english(self):
        for package,screen in [('de.kamilunavo.idlehandwerker','other'),('de.kamilunavo.ninenine','other')]:
            a=ready_app(package);a['frameLanguageRequirements']['en-US'][0]={'inAppLanguage':'en','mixedUi':False,'languageLimitation':'Synthetic source-scope check','screenScope':screen}
            with self.assertRaises(candidate.CandidateError):game_policy.require_ready(a)
        a=ready_app('de.kamilunavo.ninenine');a['frameLanguageRequirements']['en-US'][0]={'inAppLanguage':'en','mixedUi':False,'languageLimitation':'Only Practice panel is English.','screenScope':'practice'};game_policy.require_ready(a)
    def test_english_listing_with_honest_german_ui_allowed_but_device_only_label_rejected(self):
        a=ready_app('de.kamilunavo.idlehandwerker');game_policy.require_ready(a);entry=copy.deepcopy(a['frameLanguageRequirements']['en-US'][0]);entry['inAppLanguage']='en'
        with self.assertRaises(candidate.CandidateError):game_policy.validate_frame_language(a,'en-US',0,entry)
    def test_game_transaction_exact_version_unknown_commit_once_and_no_cancel_fallback(self):
        self.enabled();self.assertIn('family',inspect.signature(publisher.submit_candidate).parameters,'Closed transaction family missing');f=GameFixture(self);c=candidate.Candidate(f.package,f.app,{},f.aab,digest(f.aab),'b'*64,{'de-DE':(),'en-US':()},None,'c'*64);h=FakeTransport(c,{'commit':publisher.TransportError('private')});r=publisher.submit_candidate(c,h,family='game5');self.assertEqual(r['status'],'reconciliation_required');self.assertEqual(len([x for x in h.calls if ':commit?'in x[1]]),1);self.assertFalse(any('CANCEL'in x[1]for x in h.calls));self.assertFalse(any(x[0]=='DELETE'and'/listings/'not in x[1]for x in h.calls))
    def test_unverified_other_binary_cannot_reach_any_provider_call_even_with_ready_app(self):
        self.enabled();self.assertIn('family',inspect.signature(publisher.submit_candidate).parameters);f=GameFixture(self);c=candidate.Candidate(f.package,f.app,{},b'not-the-game',f.app['signedAabSha256'],'b'*64,{},None,'c'*64);h=FakeTransport(c);r=publisher.submit_candidate(c,h,family='game5');self.assertFalse(r['ok']);self.assertEqual(h.calls,[])

    def test_rune_requires_actual_accepted_public_certificate_not_central_games_certificate(self):
        self.enabled();f=GameFixture(self);raw=f.raw()
        class WrongCertificate(FixtureVerifier):
            def verify(self,data,app):
                value=super().verify(data,app);value['sha256']=candidate.CENTRAL_SHA256;value['sha1']=candidate.CENTRAL_SHA1;return value
        with self.assertRaises(candidate.CandidateError):candidate.validate_archive(raw,digest(raw),f.package,f.catalog,WrongCertificate(),NOW,family='game5')
    def test_rune_candidate_rejects_fabricated_ci_sections_instead_of_its_local_source_evidence(self):
        self.enabled();f=GameFixture(self);f.manifest['source']={'repository':'invented/rune','runId':1};raw=f.raw()
        with self.assertRaises(candidate.CandidateError):candidate.validate_archive(raw,digest(raw),f.package,f.catalog,FixtureVerifier(),NOW,family='game5')
