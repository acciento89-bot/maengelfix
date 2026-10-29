import copy, struct, unittest, zlib
from fixtures import Fixture, Verifier, PACKAGE, NOW, digest, png
import candidate

class ScreenshotTests(unittest.TestCase):
    def validate(self,f):
        raw=f.raw();return candidate.validate_archive(raw,digest(raw),PACKAGE,f.catalog,Verifier(),NOW)
    def replace(self,f,color=(22,44,66),width=320,height=640,raw_color=None,upload_color=None):
        image=f.manifest['screenshots']['de-DE'][0]
        raw=png(raw_color or (*color,255),width,height);rgb=png(upload_color or color,width,height)
        f.files[image['path']]=rgb;f.files[image['rawNative']['path']]=raw
        image['sha256']=digest(rgb);image['rawNative']['sha256']=digest(raw);image['pixelSha256']=digest(bytes(color)*width*height)
        f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots'])
    def test_four_distinct_native_raw_and_lossless_rgb_frames_per_existing_locale(self):
        f=Fixture();c=self.validate(f)
        self.assertEqual(set(c.screenshots),{'de-DE','en-US'});self.assertTrue(all(len(v)==4 for v in c.screenshots.values()))
    def test_current_720_by_1600_qa_frames_and_outside_google_bounds_are_rejected(self):
        for width,height in [(720,1600),(319,640),(3841,1921),(320,641)]:
            f=Fixture();self.replace(f,width=width,height=height)
            with self.subTest(size=(width,height)),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_rgb24_required_and_alpha_raw_must_be_opaque(self):
        for raw_color,uploaded in [((22,44,66,255),(22,44,66,255)),((22,44,66,0),(22,44,66))]:
            f=Fixture();self.replace(f,raw_color=raw_color,upload_color=uploaded)
            with self.subTest(raw=raw_color,upload=uploaded),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_pixel_changes_raw_hash_pixel_hash_and_cross_locale_paths_are_rejected(self):
        for mode in ['different_pixels','raw_hash','pixel_hash','cross_locale','missing_locale']:
            f=Fixture()
            if mode=='different_pixels':self.replace(f,upload_color=(23,44,66))
            elif mode=='raw_hash':f.manifest['screenshots']['de-DE'][0]['rawNative']['sha256']='0'*64
            elif mode=='pixel_hash':f.manifest['screenshots']['de-DE'][0]['pixelSha256']='0'*64
            elif mode=='cross_locale':f.manifest['screenshots']['de-DE'][0]=copy.deepcopy(f.manifest['screenshots']['en-US'][0])
            else:del f.manifest['screenshots']['en-US']
            f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots'])
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)
    def test_three_or_nine_frames_per_locale_are_rejected(self):
        for count in [3,9]:
            f=Fixture();f.manifest['screenshots']['de-DE']=(f.manifest['screenshots']['de-DE']*3)[:count];f.qa['screenshots']=copy.deepcopy(f.manifest['screenshots'])
            with self.subTest(count=count),self.assertRaises(candidate.CandidateError):self.validate(f)

    def test_png_standard_row_filters_reconstruct_the_exact_rgb_pixel_hash(self):
        expected=bytes([10,20,30,40,50,60,15,25,35,50,60,70])
        rows=[([10,20,30,40,50,60],[15,25,35,50,60,70]),([10,20,30,30,30,30],[15,25,35,35,35,35]),([10,20,30,40,50,60],[5,5,5,10,10,10]),([10,20,30,35,40,45],[10,15,20,23,23,23]),([10,20,30,30,30,30],[5,5,5,10,10,10])]
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        for filtering,(first,second)in enumerate(rows):
            raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes([filtering]+first+[filtering]+second)))+chunk(b'IEND',b'')
            with self.subTest(filter=filtering):self.assertEqual(candidate.decode_png(raw).rgb,expected)
    def test_pending_locale_catalog_and_different_derived_apk_proof_are_rejected(self):
        for mode in ['pending','snapshot','missing_existing_locale','apk_hash','apk_source_aab']:
            f=Fixture()
            if mode=='pending':f.app['listingLocales']=None;f.app['localeSnapshotSha256']=None
            elif mode=='snapshot':f.app['localeSnapshotSha256']='0'*64
            elif mode=='missing_existing_locale':
                import json
                report=json.loads(f.files['qa/locale-inventory.json']);report['apps'][0]['localeIds']=['de-DE']
                f.files['qa/locale-inventory.json']=json.dumps(report).encode();f.manifest['localeInventory']['sha256']=digest(f.files['qa/locale-inventory.json']);f.app['localeSnapshotSha256']=f.manifest['localeInventory']['sha256']
            else:
                import json
                proof=json.loads(f.files['qa/derived-apk-proof.json']);proof['apkSha256' if mode=='apk_hash'else 'sourceAabSha256']='0'*64
                f.files['qa/derived-apk-proof.json']=json.dumps(proof).encode();f.qa['apkProof']['sha256']=digest(f.files['qa/derived-apk-proof.json'])
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):self.validate(f)
