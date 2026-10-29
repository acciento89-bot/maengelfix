"""Synthetic CPU controls; no genuine candidate or QA approval."""
import copy, importlib.util, json, unittest
from fixtures import HERE
import candidate

class BusinessPolicyTests(unittest.TestCase):
    def policy(self):
        self.assertIsNotNone(importlib.util.find_spec('business_policy'), 'business policy adapter is not implemented')
        import business_policy
        return business_policy
    def test_exact_twelve_mixed_versions_and_distinct_managed_eas_certificate(self):
        p=self.policy(); apps=p.fixed_apps()
        self.assertEqual(len(apps),12); self.assertNotIn('de.kamilunavo.brennercalc',apps)
        self.assertEqual(apps['com.kamilunavo.maengelfix']['newVersionName'],'1.1.0')
        self.assertEqual(apps['de.kamilunavo.reklaio']['newVersionName'],'0.6.0')
        kids=apps['com.kamilunavo.navokids'];self.assertEqual(kids['route'],'managed_eas')
        self.assertIsNone(kids['signWorkflow']);self.assertNotEqual(kids['certificate'],apps['de.kamilunavo.navopass']['certificate'])
    def test_unknown_family_or_union_or_package_does_not_expand_default_scope(self):
        p=self.policy()
        with self.assertRaises(candidate.CandidateError):p.scope('all')
        self.assertEqual(set(p.scope('calculator9')),set(candidate.EXPECTED))
        self.assertEqual(len(p.scope('business12')),12)
    def test_catalog_requires_exact_immutable_source_version_certificate_topology(self):
        p=self.policy();raw=(HERE/'business-catalog.json').read_bytes();catalog=p.load_catalog(HERE/'business-catalog.json',candidate.digest(raw))
        self.assertEqual(len(catalog),12)
        app=copy.deepcopy(catalog['com.kamilunavo.navokids'])
        for key,value in [('newVersionCode',10),('newVersionName','1.2.0'),('certificate',catalog['de.kamilunavo.navopass']['certificate']),('signWorkflow','.github/workflows/fake.yml'),('reviewedSourceCommit','a'*40)]:
            altered=copy.deepcopy(app);altered[key]=value
            with self.subTest(key=key),self.assertRaises(candidate.CandidateError):p.assert_identity(altered)
    def test_all_initial_products_block_submission_without_final_genuine_evidence(self):
        p=self.policy();raw=(HERE/'business-catalog.json').read_bytes();catalog=p.load_catalog(HERE/'business-catalog.json',candidate.digest(raw))
        for app in catalog.values():
            with self.subTest(app=app['app']),self.assertRaises(candidate.CandidateError):p.require_ready(app)
    def test_pending_or_empty_or_scalar_license_and_review_fields_never_pass(self):
        p=self.policy();app=copy.deepcopy(p.fixed_apps()['de.kamilunavo.navopass'])
        for field,value in [('requiredBundleAssets',[]),('rootReviewSha256',None),('rightsEvidenceSha256',None),('listingLocales',None)]:
            app.update(frameLanguageRequirements={l:[{'inAppLanguage':'de','mixedUi':False,'languageLimitation':'Actual German UI, regardless of listing locale.'}for _ in range(4)]for l in ['de-DE','en-US']},readiness='root_reviewed_candidate_inputs',listingLocales=['de-DE','en-US'],localeSnapshotSha256='a'*64,rootReviewSha256='b'*64,rightsEvidenceSha256='c'*64,requiredBundleAssets=[{'entry':'base/assets/fonts/f.ttf','sha256':'d'*64},{'entry':'base/assets/fonts/OFL.txt','sha256':'e'*64}],releaseNotes={'de-DE':'Test','en-US':'Test'})
            app[field]=value
            with self.subTest(field=field),self.assertRaises(candidate.CandidateError):p.require_ready(app)

    def test_catalog_boolean_schema_duplicate_package_unknown_fields_and_unlisted_scope_fail(self):
        import tempfile
        from pathlib import Path
        p=self.policy();original=json.loads((HERE/'business-catalog.json').read_text())
        for mode in ['boolean_schema','duplicate','unknown_root_field','unknown_app_field','omitted','other_package']:
            d=copy.deepcopy(original)
            if mode=='boolean_schema':d['schema']=True
            elif mode=='duplicate':d['apps'][1]=copy.deepcopy(d['apps'][0])
            elif mode=='unknown_root_field':d['arbitraryPackageOverride']='com.other.app'
            elif mode=='unknown_app_field':d['apps'][0]['skipRightsReview']=True
            elif mode=='omitted':d['apps'].pop()
            else:d['apps'][0]['package']='com.kamilunavo.onemorefloor'
            raw=json.dumps(d).encode()
            with self.subTest(mode=mode),tempfile.TemporaryDirectory()as temp:
                path=Path(temp)/'catalog.json';path.write_bytes(raw)
                with self.assertRaises(candidate.CandidateError):p.load_catalog(path,candidate.digest(raw))
