"""Business inner names only: closed exceptions, unchanged outer ZIP boundary."""
import io,stat,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import candidate,business_binary

def archive(entries,compression=zipfile.ZIP_STORED):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=compression) as z:
        for name,data in entries:z.writestr(name,data)
    return buf.getvalue()

class BusinessBinaryTests(unittest.TestCase):
    def test_only_exact_observed_native_paths_for_four_abis(self):
        for abi in ['arm64-v8a','armeabi-v7a','x86','x86_64']:
            for name in ['lib/'+abi+'/libc++_shared.so','base/lib/'+abi+'/libc++_shared.so','BUNDLE-METADATA/com.android.tools.build.debugsymbols/'+abi+'/libc++_shared.so.sym']:
                self.assertEqual(business_binary.binary_files(archive([(name,b'actual')]))[name],b'actual')
                with self.assertRaises(candidate.CandidateError):candidate.zip_files(archive([(name,b'actual')]))
    def test_exact_generated_drawables_only_inside_original_resource_directory(self):
        self.assertEqual(len(business_binary._GENERATED_DRAWABLES),40)
        for name in business_binary._GENERATED_DRAWABLES:
            for prefix in ['base/res/drawable/','res/drawable/']:
                self.assertIn(prefix+name,business_binary.binary_files(archive([(prefix+name,b'xml')])))
                with self.assertRaises(candidate.CandidateError):candidate.zip_files(archive([(prefix+name,b'xml')]))
    def test_no_general_plus_dollar_or_new_path_grant(self):
        for name in ['qa/libc++_shared.so','base/assets/libc++_shared.so','lib/riscv64/libc++_shared.so','lib/arm64-v8a/libother++.so','base/lib/arm64-v8a/libc++_shared.so.extra','base/res/drawable/$unknown.xml','base/res/drawable/$mtrl_unobserved__0.xml','res/drawable-hdpi/$avd_hide_password__0.xml','qa/$avd_hide_password__0.xml','res/drawable/sub/$avd_hide_password__0.xml','qa/has+plus.txt']:
            with self.subTest(name=name),self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([(name,b'x')]))
    def test_traversal_absolute_alias_backslash_and_encoded_paths_still_rejected(self):
        for name in ['/lib/arm64-v8a/libc++_shared.so','base/lib/../lib/arm64-v8a/libc++_shared.so','base//lib/arm64-v8a/libc++_shared.so','./lib/arm64-v8a/libc++_shared.so','base\\lib\\arm64-v8a\\libc++_shared.so','base/res/drawable/../$avd_hide_password__0.xml','base/res/drawable/%24avd_hide_password__0.xml','../qa/x','base/./x']:
            with self.subTest(name=name),self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([(name,b'x')]))
    def test_duplicate_casefold_collision_rejected(self):
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([('lib/arm64-v8a/other.so',b'a'),('lib/arm64-v8a/OTHER.so',b'b')]))
    def test_links_and_special_files_rejected(self):
        for mode in [stat.S_IFLNK,stat.S_IFCHR,stat.S_IFIFO,stat.S_IFSOCK]:
            info=zipfile.ZipInfo('base/assets/data');info.external_attr=(mode|0o644)<<16
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([(info,b'x')]))
    def test_encryption_and_unsupported_compression_rejected(self):
        raw=bytearray(archive([('base/assets/data',b'x')]))
        local=raw.index(b'PK\x03\x04');central=raw.index(b'PK\x01\x02')
        struct.pack_into('<H',raw,local+6,1);struct.pack_into('<H',raw,central+8,1)
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(bytes(raw))
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([('base/assets/data',b'x')],zipfile.ZIP_BZIP2))
    def test_all_original_size_count_and_expansion_limits_remain(self):
        self.assertEqual(business_binary.MAX_ARCHIVE,candidate.MAX_ARCHIVE)
        with patch.object(business_binary,'MAX_ARCHIVE',10),self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([('x',b'x')]))
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([(str(n),b'x')for n in range(5001)]))
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(archive([('base/assets/data',b'0'*1_000_000)],zipfile.ZIP_DEFLATED))
        # Modified declared file size is rejected before decompression/read.
        raw=bytearray(archive([('x',b'x')]));central=raw.index(b'PK\x01\x02');struct.pack_into('<I',raw,central+24,128*1024*1024+1)
        with self.assertRaises(candidate.CandidateError):business_binary.binary_files(bytes(raw))
    def test_malformed_empty_and_nonbytes_rejected(self):
        for raw in [b'',b'invalid',None,bytearray(b'bad')]:
            with self.subTest(raw=raw),self.assertRaises(candidate.CandidateError):business_binary.binary_files(raw)
    def test_same_signature_and_crypto_checks_after_business_reader(self):
        raw=archive([('base/lib/arm64-v8a/libc++_shared.so',b'library')])
        replies=['jar verified.','public certificate','valid','de.example.business','12','0.6.0']
        with tempfile.TemporaryDirectory()as temp:
            jar=Path(temp)/'bundletool.jar';jar.write_bytes(b'pinned')
            verifier=business_binary.BusinessBundleVerifier(jar,candidate.digest(b'pinned'))
            with patch.object(business_binary,'verify_signature_manifest')as signed,patch.object(business_binary,'parse_certificate',return_value=('A'*40,'B'*64)),patch.object(business_binary.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout=x)for x in replies])as crypto:
                result=verifier.verify(raw,{})
                signed.assert_called_once();self.assertIn('base/lib/arm64-v8a/libc++_shared.so',signed.call_args.args[0]);self.assertEqual(crypto.call_count,6)
                self.assertEqual(crypto.call_args_list[0].args[0][:3],['jarsigner','-J-Duser.language=en','-verify']);self.assertEqual(result['versionCode'],12)
            with patch.object(business_binary,'verify_signature_manifest',side_effect=candidate.CandidateError('bad JAR coverage')),patch.object(business_binary.subprocess,'run')as crypto,self.assertRaises(candidate.CandidateError):verifier.verify(raw,{})
            crypto.assert_not_called()
            with patch.object(business_binary,'verify_signature_manifest'),patch.object(business_binary.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='invalid')),self.assertRaises(candidate.CandidateError):verifier.verify(raw,{})
            with patch.object(business_binary,'verify_signature_manifest'),patch.object(business_binary.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='jar is unsigned')),self.assertRaises(candidate.CandidateError):verifier.verify(raw,{})
