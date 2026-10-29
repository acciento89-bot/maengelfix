import base64, copy, hashlib, io, json, stat, tempfile, unittest, zipfile
from pathlib import Path
from fixtures import Fixture, Verifier, HERE, PACKAGE, SHA1, SHA256, NOW, digest, encode, packed
import candidate

class CandidateTests(unittest.TestCase):
    def validate(self, fixture=None, verifier=None, raw=None, package=PACKAGE):
        f = fixture or Fixture(); raw = f.raw() if raw is None else raw
        return candidate.validate_archive(raw, digest(raw), package, f.catalog, verifier or Verifier(), NOW)
    def test_exact_signed_ci_bytes_normal_native_qa_and_font_notice_inventory_pass(self):
        f = Fixture(); result = self.validate(f)
        self.assertEqual(result.package, PACKAGE); self.assertEqual(result.aab, f.aab)
        self.assertEqual({l:len(v)for l,v in result.screenshots.items()}, {'de-DE':4,'en-US':4}); self.assertEqual(result.bundle_sha256, digest(f.aab))
    def test_all_other_packages_rejected_before_external_verifier(self):
        v = Verifier()
        for package in ['com.kamilunavo.onemorefloor', 'de.kamilunavo.maengelfix', '../production', '']:
            with self.subTest(package=package), self.assertRaises(candidate.CandidateError): self.validate(verifier=v, package=package)
        self.assertEqual(v.calls, [])
    def test_archive_hash_mismatch_rejected(self):
        f = Fixture(); raw = f.raw()
        with self.assertRaises(candidate.CandidateError): candidate.validate_archive(raw, '0' * 64, PACKAGE, f.catalog, Verifier(), NOW)
    def test_duplicate_traversal_alias_windows_and_symlink_zip_members_rejected(self):
        f = Fixture(); raw = f.raw()
        for name in ['../escape', '/absolute', 'a/../escape', 'a//file', 'C:/evil', 'a\\b', 'MANIFEST.JSON']:
            with self.subTest(name=name), self.assertRaises(candidate.CandidateError): self.validate(f, raw=packed({**f.files, name: b'x'}))
        stream = io.BytesIO(raw)
        with zipfile.ZipFile(stream, 'a') as z:
            info = zipfile.ZipInfo('link'); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16; z.writestr(info, '../x')
        with self.assertRaises(candidate.CandidateError): self.validate(f, raw=stream.getvalue())
        stream = io.BytesIO(raw)
        with zipfile.ZipFile(stream, 'a') as z: z.writestr('manifest.json', f.files['manifest.json'])
        with self.assertRaises(candidate.CandidateError): self.validate(f, raw=stream.getvalue())
    def test_manifest_duplicate_keys_and_unlisted_files_rejected(self):
        f = Fixture(); f.raw(); files = dict(f.files); files['manifest.json'] = files['manifest.json'].replace(b'"schema":1', b'"schema":1,"schema":1')
        with self.assertRaises(candidate.CandidateError): self.validate(f, raw=packed(files))
        with self.assertRaises(candidate.CandidateError): self.validate(f, raw=packed({**f.files, 'unlisted.png': b'not proof'}))
    def test_manifest_scope_versions_source_and_sign_workflows_frozen(self):
        for field, value in [('package','de.kamilunavo.hydrocalc'), ('versionCode', True), ('versionCode', 70), ('versionName','1.2.0-beta')]:
            f = Fixture(); f.manifest[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(candidate.CandidateError): self.validate(f)
        for section, key, value in [('source','commit','f'*40), ('source','workflow','.github/workflows/other.yml'), ('signing','commit','f'*40), ('signing','runId','1;exit'), ('signing','repository','other/repo')]:
            f=Fixture(); f.manifest[section][key]=value
            with self.subTest(section=section,key=key), self.assertRaises(candidate.CandidateError): self.validate(f)
    def test_boolean_schema_and_nonobject_reports_are_not_valid_versioned_evidence(self):
        for target in ['manifest','qa']:
            f=Fixture();getattr(f,target)['schema']=True
            with self.subTest(target=target),self.assertRaises(candidate.CandidateError):self.validate(f)
        f=Fixture();f.raw();files=dict(f.files);files['manifest.json']=b'[]'
        with self.assertRaises(candidate.CandidateError):self.validate(f,raw=packed(files))
    def test_signed_ci_archive_must_contain_the_exact_bundle_and_original_provenance(self):
        f=Fixture(); f.signed_files['app-release.aab']=b'other signed bundle'
        with self.assertRaises(candidate.CandidateError): self.validate(f)
        f=Fixture(); p=json.loads(f.signed_files['provenance.json']); p['SOURCE_RUN_ID']='99'; f.signed_files['provenance.json']=encode(p)
        with self.assertRaises(candidate.CandidateError): self.validate(f)
    def test_unsigned_or_wrong_certificate_and_manifest_identity_never_ready(self):
        f=Fixture(); f.aab=packed({'base/manifest/AndroidManifest.xml':b'x'}); f.files['bundle/app.aab']=f.aab; f.manifest['bundle']=f.entry('bundle/app.aab'); f.qa['signedAabSha256']=digest(f.aab); f.signed_files['app-release.aab']=f.aab
        with self.assertRaises(candidate.CandidateError): self.validate(f)
        for key,value in [('sha1','0'*40),('sha256','0'*64),('jarVerified',False),('package','wrong'),('versionCode',70),('versionName','1.1.0')]:
            v=Verifier(); original=v.verify
            v.verify=lambda raw,app,k=key,value=value,fn=original: {**fn(raw,app),k:value}
            with self.subTest(key=key), self.assertRaises(candidate.CandidateError): self.validate(verifier=v)
    def test_native_qa_exact_bundle_source_normal_app_and_no_real_commerce_required(self):
        for key,value in [('outcome','fail'),('normalApplication',False),('signedAabSha256','0'*64),('sourceCommit','0'*40),('testedAtUtc','2020-01-01T00:00:00+00:00')]:
            f=Fixture();f.qa[key]=value
            with self.subTest(key=key), self.assertRaises(candidate.CandidateError):self.validate(f)
        f=Fixture();f.qa['realTransactions']['restores']=True
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_native_proof_and_screenshot_hashes_are_verified(self):
        for target in ['qa/proof.json','screens/de-DE/01.png']:
            f=Fixture();f.files[target]+=b'changed'
            with self.subTest(target=target),self.assertRaises(candidate.CandidateError):self.validate(f)
        f=Fixture();f.manifest['screenshots']['de-DE'][1]=copy.deepcopy(f.manifest['screenshots']['de-DE'][0]);f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots'])
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_required_real_bundle_asset_hash_is_checked(self):
        f=Fixture();f.app['requiredBundleAssets'][0]['sha256']='0'*64
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_png_crc_or_incomplete_image_rejected_even_when_qa_hash_updated(self):
        f=Fixture();f.files['screens/de-DE/01.png']=f.files['screens/de-DE/01.png'][:-12];f.manifest['screenshots']['de-DE'][0]['sha256']=digest(f.files['screens/de-DE/01.png']);f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots'])
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_optional_icon_must_be_original_pinned_512_png(self):
        f=Fixture();f.files['screens/icon.png']=f.files['screens/de-DE/01.png'];f.manifest['icon']=f.entry('screens/icon.png')
        with self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_exact_nine_catalog_hash_and_scope_required(self):
        path=HERE/'catalog.json';catalog=candidate.load_catalog(path,digest(path.read_bytes()));self.assertEqual(len(catalog),9)
        with self.assertRaises(candidate.CandidateError):candidate.load_catalog(path,'0'*64)
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'catalog.json';data=json.loads(path.read_text());data['apps'][0]['package']='de.kamilunavo.maengelfix';p.write_bytes(encode(data))
            with self.assertRaises(candidate.CandidateError):candidate.load_catalog(p,digest(p.read_bytes()))
    def test_keytool_parser_requires_one_exact_certificate_pair(self):
        text='SHA1: '+':'.join(SHA1[i:i+2]for i in range(0,len(SHA1),2))+'\nSHA256: '+':'.join(SHA256[i:i+2]for i in range(0,len(SHA256),2))+'\n'
        self.assertEqual(candidate.parse_certificate(text),(SHA1,SHA256))
        for malformed in ['',text+text,text.replace('SHA256:','SHA-256:')]:
            with self.subTest(malformed=malformed[:10]),self.assertRaises(candidate.CandidateError):candidate.parse_certificate(malformed)
    def test_every_bundle_payload_entry_is_covered_by_signed_manifest_digest(self):
        files={'base/manifest/AndroidManifest.xml':b'unit payload','base/assets/a.txt':b'other payload'}
        manifest=b'Manifest-Version: 1.0\r\n\r\n'
        for name,raw in files.items():manifest+=b'Name: '+name.encode()+b'\r\nSHA-256-Digest: '+base64.b64encode(hashlib.sha256(raw).digest())+b'\r\n\r\n'
        signature=b'Signature-Version: 1.0\r\nSHA-256-Digest-Manifest: '+base64.b64encode(hashlib.sha256(manifest).digest())+b'\r\n\r\n'
        signed={**files,'META-INF/MANIFEST.MF':manifest,'META-INF/UPLOAD.SF':signature,'META-INF/UPLOAD.RSA':b'crypto verified separately'}
        candidate.verify_signature_manifest(signed)
        for changed in [{**signed,'base/assets/unsigned.txt':b'unsigned'}, {**signed,'base/assets/a.txt':b'changed'}, {**signed,'META-INF/UPLOAD.SF':b'Signature-Version: 1.0\r\n\r\n'}]:
            with self.subTest(keys=list(changed)[-1]),self.assertRaises(candidate.CandidateError):candidate.verify_signature_manifest(changed)
