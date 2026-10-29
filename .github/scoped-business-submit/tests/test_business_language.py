"""Synthetic proof labels; an English listing never proves English UI."""
import copy,inspect,unittest
from fixtures import NOW,digest
from business_fixtures import BusinessFixture,BusinessVerifier
import candidate,business_policy

class BusinessLanguageTests(unittest.TestCase):
    def enabled(self):self.assertTrue(hasattr(business_policy,'validate_frame_language'),'Per-frame honest UI language contract missing')
    def validate(self,f):
        raw=f.raw();return candidate.validate_archive(raw,digest(raw),f.package,f.catalog,BusinessVerifier(),NOW,family='business12')
    def german_fixture(self):
        self.enabled();f=BusinessFixture();f.app['frameLanguageRequirements']={locale:[{'inAppLanguage':'de','mixedUi':False,'languageLimitation':''if locale.startswith('de')else'English store listing; actual visible UI remains German.'}for _ in range(4)]for locale in ['de-DE','en-US']}
        for locale,entries in f.manifest['screenshots'].items():
            for i,e in enumerate(entries):e.update(f.app['frameLanguageRequirements'][locale][i])
        f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots']);f.qa.pop('captureLanguages',None);f.qa['listingLocales']=['de-DE','en-US'];f.review['screenshots']=copy.deepcopy(f.manifest['screenshots']);return f
    def test_english_listing_accepts_explicit_actual_german_ui_with_pinned_limitation(self):
        f=self.german_fixture();c=self.validate(f);self.assertEqual(c.manifest['screenshots']['en-US'][0]['inAppLanguage'],'de')
    def test_english_listing_or_device_locale_cannot_relabel_actual_german_ui_as_english(self):
        for mode in ['en_label','device_locale_only','missing_language','unpinned_frame']:
            f=self.german_fixture();row=f.manifest['screenshots']['en-US'][0]
            if mode=='en_label':row['inAppLanguage']='en'
            elif mode=='device_locale_only':row['deviceLocale']='en-US';row.pop('inAppLanguage')
            elif mode=='missing_language':row.pop('inAppLanguage')
            else:row['languageLimitation']='different from root-pinned limitation'
            f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots']);f.review['screenshots']=copy.deepcopy(f.manifest['screenshots'])
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_mixed_legacy_german_chrome_english_panel_requires_flag_and_specific_limitation(self):
        f=self.german_fixture();row={'inAppLanguage':'mixed-de-en','mixedUi':True,'languageLimitation':'Legacy navigation is German; the new workspace panel is English.'};f.app['frameLanguageRequirements']['en-US'][1]=row;f.manifest['screenshots']['en-US'][1].update(row);f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots']);f.review['screenshots']=copy.deepcopy(f.manifest['screenshots']);self.validate(f)
        for change in [{'mixedUi':False},{'languageLimitation':''},{'inAppLanguage':'en'}]:
            altered=copy.deepcopy(f.app);altered['frameLanguageRequirements']['en-US'][1].update(change)
            with self.subTest(change=change),self.assertRaises(candidate.CandidateError):business_policy.require_ready(altered)
    def test_pending_language_contract_cannot_pass_even_with_locale_qa_and_review_hashes(self):
        f=self.german_fixture();f.app['frameLanguageRequirements']=None
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_listing_locales_are_separate_from_actual_ui_language_or_capture_language_claim(self):
        f=self.german_fixture();f.qa['listingLocales']=['de','en']
        with self.assertRaises(candidate.CandidateError):self.validate(f)
        f=self.german_fixture();f.qa['captureLanguages']=['de-DE','en-US']
        with self.assertRaises(candidate.CandidateError):self.validate(f)
