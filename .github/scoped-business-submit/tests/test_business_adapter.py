import copy,inspect,unittest
from fixtures import HERE,NOW,digest
import candidate,publisher
from test_publisher import FakeTransport

class BusinessAdapterTests(unittest.TestCase):
    def fixture(self,package='com.kamilunavo.maengelfix'):
        self.assertIn('family',inspect.signature(candidate.validate_archive).parameters,'closed family candidate adaptation missing')
        from business_fixtures import BusinessFixture,BusinessVerifier
        f=BusinessFixture(package);return f,BusinessVerifier
    def validate(self,f,verifier=None):
        from business_fixtures import BusinessVerifier
        raw=f.raw();return candidate.validate_archive(raw,digest(raw),f.package,f.catalog,verifier or BusinessVerifier(),NOW,family='business12')
    def test_central_business_actual_version_and_eas_single_stage_accepted_in_synthetic_fixture_only(self):
        for package in ['com.kamilunavo.maengelfix','com.kamilunavo.navokids']:
            f,_=self.fixture(package);c=self.validate(f);self.assertEqual(c.app['newVersionName'],f.app['newVersionName'])
    def test_wrong_per_app_certificate_is_rejected_including_central_on_eas(self):
        f,V=self.fixture('com.kamilunavo.navokids')
        with self.assertRaises(candidate.CandidateError):self.validate(f,V(sha1=candidate.CENTRAL_SHA1,sha256=candidate.CENTRAL_SHA256))
    def test_eas_never_fabricates_signer_or_accepts_recovered_unfrozen_or_other_build(self):
        f,V=self.fixture('com.kamilunavo.navokids')
        for field,value in [('credentialsFrozen',False),('recoveredFinishedBuild',True),('storeSubmission',True),('versionCode',True),('workflowCommit','a'*40),('easBuildID','not-id')]:
            g,_=self.fixture('com.kamilunavo.navokids');g.provenance[field]=value
            with self.subTest(field=field),self.assertRaises(candidate.CandidateError):self.validate(g)
        f.manifest['signing']=copy.deepcopy(f.manifest['source'])
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_wrong_source_signing_version_or_artifact_binding_stops(self):
        for field,value in [('SOURCE_COMMIT','a'*40),('SOURCE_RUN_ID','999'),('SOURCE_ARTIFACT_DIGEST','sha256:'+'b'*64),('VERSION_NAME','1.2.0')]:
            f,_=self.fixture();f.provenance[field]=value
            with self.subTest(field=field),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_pending_rights_review_or_wrong_native_bundle_or_unreviewed_frame_stops(self):
        for mode in ['rights_pending','root_pending','native_aab','unreviewed','rights_assets']:
            f,_=self.fixture()
            if mode=='rights_pending':f.rights['outcome']='pending'
            if mode=='root_pending':f.review['outcome']='pending'
            if mode=='native_aab':f.qa['signedAabSha256']='c'*64
            if mode=='unreviewed':f.review['rootVisuallyReviewedAllEight']=False
            if mode=='rights_assets':f.rights['requiredBundleAssets']=[]
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_business_version_transaction_uses_exact_name_and_preserves_other_tracks_and_text(self):
        f,_=self.fixture();c=self.validate(f);h=FakeTransport(c);before=copy.deepcopy(h.live)
        self.assertIn('family',inspect.signature(publisher.submit_candidate).parameters)
        r=publisher.submit_candidate(c,h,family='business12');self.assertTrue(r['ok'],r);self.assertEqual(r['versionName'],'1.1.0')
        prod=next(t for t in h.live['tracks']['tracks']if t['track']=='production');self.assertEqual(prod['releases'][0]['name'],'1.1.0 (9)')
        self.assertEqual(before['listings'],h.live['listings']);self.assertEqual(before['tracks']['tracks'][1],next(t for t in h.live['tracks']['tracks']if t['track']=='internal'))
    def test_unknown_commit_one_attempt_no_retry_or_delete_and_pending_review_is_preserved(self):
        f,_=self.fixture();c=self.validate(f)
        for response in [publisher.TransportError('private'),publisher.Response(400,{'reason':'CHANGES_ALREADY_IN_REVIEW'})]:
            h=FakeTransport(c,{'commit':response});r=publisher.submit_candidate(c,h,family='business12');self.assertFalse(r['ok']);self.assertEqual(len([x for x in h.calls if ':commit?'in x[1]]),1)
            self.assertFalse(any('CANCEL'in x[1]for x in h.calls));self.assertEqual(r['status'],'reconciliation_required'if isinstance(response,Exception)else'blocked_in_review')
            if isinstance(response,Exception):self.assertFalse(any(x[0]=='DELETE'and'/listings/'not in x[1]for x in h.calls))
    def test_business_not_accepted_by_default_calculator_and_calculator_not_by_business(self):
        f,_=self.fixture();c=self.validate(f);h=FakeTransport(c);r=publisher.submit_candidate(c,h);self.assertFalse(r['ok']);self.assertEqual(h.calls,[])
        raw=f.raw()
        with self.assertRaises(candidate.CandidateError):candidate.validate_archive(raw,digest(raw),f.package,f.catalog,None,NOW)

    def test_actual_tested_apk_payload_and_direct_installed_raw_hash_are_required(self):
        for mode in ['other_apk','wrong_installed_hash','missing_direct_proof']:
            f,_=self.fixture()
            from fixtures import encode,packed
            import json
            if mode=='other_apk':f.files['qa/tested.apk']=packed({'assets/font.ttf':b'other code/assets','assets/OFL.txt':b'unit-license-not-real'})
            elif mode=='wrong_installed_hash':f.files['qa/installed-hash.txt']=('c'*64+'  /data/app/unit/'+f.package+'-unit/base.apk\n').encode()
            else:
                d=json.loads(f.files['qa/derived-apk-proof.json']);del d['actualInstalledHashRawProof'];f.files['qa/derived-apk-proof.json']=encode(d);f.qa['apkProof']=f.entry('qa/derived-apk-proof.json')
            # Rebind ordinary file hashes; the guard must check actual semantics, not only stale entry hashes.
            for i,e in enumerate(f.qa['proof']):f.qa['proof'][i]=f.entry(e['path'])
            d=json.loads(f.files['qa/derived-apk-proof.json'])
            if mode=='other_apk':
                d['actualDerivedApkFile']=f.entry('qa/tested.apk');d['apkSha256']=digest(f.files['qa/tested.apk']);f.qa['testedApkSha256']=d['apkSha256'];f.review['testedApkSha256']=d['apkSha256'];f.files['qa/installed-hash.txt']=(d['apkSha256']+'  /data/app/unit/'+f.package+'-unit/base.apk\n').encode()
            if mode=='wrong_installed_hash':d['actualInstalledHashRawProof']=f.entry('qa/installed-hash.txt')
            if mode=='other_apk':d['actualInstalledHashRawProof']=f.entry('qa/installed-hash.txt')
            f.files['qa/derived-apk-proof.json']=encode(d);f.qa['apkProof']=f.entry('qa/derived-apk-proof.json')
            for i,e in enumerate(f.qa['proof']):f.qa['proof'][i]=f.entry(e['path'])
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)

    def test_original_unsigned_payload_or_signed_payload_map_or_retained_public_cert_mismatch_stops(self):
        import business_policy
        self.assertIn('files',inspect.signature(business_policy.verify_business_provenance).parameters,'Original source archive verification missing')
        from fixtures import packed
        for mode in ['source_payload','signed_payload_map','public_cert']:
            f,_=self.fixture()
            if mode=='source_payload':f.source_override=packed({'app-release.aab':packed({'base/assets/other.txt':b'wrong original source'})})
            elif mode=='signed_payload_map':f.signed_overrides={'payload.json':b'{}'}
            else:f.signed_overrides={'upload-certificate.txt':b'SHA1: 00\nSHA256: 00\n'}
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)
