"""Business-only inner AAB/APK names; candidate/QA/source ZIP names stay strict."""
import io,re,stat,subprocess,tempfile,zipfile
from pathlib import Path
from candidate import (CandidateError,MAX_ARCHIVE,require,digest,parse_certificate,
                       verify_signature_manifest,numeric_id,safe_name,BundleVerifier)

# Exact original Material-generated drawable names present in retained Reklaio
# and WärmeTakt signed AABs and derived APKs. No general '$' or '+' path grant.
_GENERATED_DRAWABLES = frozenset(('$avd_hide_password__0.xml', '$avd_hide_password__1.xml', '$avd_hide_password__2.xml', '$avd_show_password__0.xml', '$avd_show_password__1.xml', '$avd_show_password__2.xml', '$m3_avd_hide_password__0.xml', '$m3_avd_hide_password__1.xml', '$m3_avd_hide_password__2.xml', '$m3_avd_show_password__0.xml', '$m3_avd_show_password__1.xml', '$m3_avd_show_password__2.xml', '$mtrl_checkbox_button_checked_unchecked__0.xml', '$mtrl_checkbox_button_checked_unchecked__1.xml', '$mtrl_checkbox_button_checked_unchecked__2.xml', '$mtrl_checkbox_button_icon_checked_indeterminate__0.xml', '$mtrl_checkbox_button_icon_checked_unchecked__0.xml', '$mtrl_checkbox_button_icon_checked_unchecked__1.xml', '$mtrl_checkbox_button_icon_checked_unchecked__2.xml', '$mtrl_checkbox_button_icon_indeterminate_checked__0.xml', '$mtrl_checkbox_button_icon_indeterminate_unchecked__0.xml', '$mtrl_checkbox_button_icon_indeterminate_unchecked__1.xml', '$mtrl_checkbox_button_icon_indeterminate_unchecked__2.xml', '$mtrl_checkbox_button_icon_unchecked_checked__0.xml', '$mtrl_checkbox_button_icon_unchecked_checked__1.xml', '$mtrl_checkbox_button_icon_unchecked_checked__2.xml', '$mtrl_checkbox_button_icon_unchecked_indeterminate__0.xml', '$mtrl_checkbox_button_icon_unchecked_indeterminate__1.xml', '$mtrl_checkbox_button_icon_unchecked_indeterminate__2.xml', '$mtrl_checkbox_button_unchecked_checked__0.xml', '$mtrl_checkbox_button_unchecked_checked__1.xml', '$mtrl_checkbox_button_unchecked_checked__2.xml', '$mtrl_switch_thumb_checked_pressed__0.xml', '$mtrl_switch_thumb_checked_unchecked__0.xml', '$mtrl_switch_thumb_checked_unchecked__1.xml', '$mtrl_switch_thumb_pressed_checked__0.xml', '$mtrl_switch_thumb_pressed_unchecked__0.xml', '$mtrl_switch_thumb_unchecked_checked__0.xml', '$mtrl_switch_thumb_unchecked_checked__1.xml', '$mtrl_switch_thumb_unchecked_pressed__0.xml'))
_ABIS = r'(?:arm64-v8a|armeabi-v7a|x86|x86_64)'
_NATIVE_SHARED = re.compile(r'(?:base/)?lib/'+_ABIS+r'/libc\+\+_shared\.so')
_NATIVE_SYMBOLS = re.compile(r'BUNDLE-METADATA/com\.android\.tools\.build\.debugsymbols/'+_ABIS+r'/libc\+\+_shared\.so\.sym')

def binary_name(name):
    if isinstance(name,str) and len(name)<=240:
        if _NATIVE_SHARED.fullmatch(name) or _NATIVE_SYMBOLS.fullmatch(name):return name
        prefix = 'base/res/drawable/' if name.startswith('base/res/drawable/') else 'res/drawable/'
        if name.startswith(prefix) and name[len(prefix):] in _GENERATED_DRAWABLES:return name
    return safe_name(name)

def binary_files(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ARCHIVE, 'Archive size outside bounds')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist(); require(0 < len(infos) <= 5000, 'Archive entry count outside bounds')
            names = set(); files = {}; total = 0
            for info in infos:
                name = info.filename.rstrip('/') if info.is_dir() else info.filename
                binary_name(name); folded = name.casefold()
                require(folded not in names, 'Duplicate or ambiguous ZIP entry'); names.add(folded)
                mode = info.external_attr >> 16
                require(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)), 'ZIP link/special file rejected')
                require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Encrypted/unsupported ZIP entry')
                total += info.file_size
                require(info.file_size <= 128 * 1024 * 1024 and total <= 512 * 1024 * 1024, 'Expanded archive too large')
                require(info.file_size <= max(info.compress_size, 1) * 500, 'ZIP expansion ratio outside bounds')
                if not info.is_dir(): files[name] = z.read(info)
            return files
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError):
        raise CandidateError('Invalid ZIP') from None

class BusinessBundleVerifier(BundleVerifier):
    """Same signature/tool/certificate checks, with the bounded Business inner reader."""
    def verify(self, raw, app):
        verify_signature_manifest(binary_files(raw))
        with tempfile.TemporaryDirectory(prefix='calculator-aab-verify-') as temp:
            aab = Path(temp)/'app.aab'; aab.write_bytes(raw)
            def run(args):
                try:
                    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
                except (OSError, subprocess.TimeoutExpired): raise CandidateError('Bounded bundle verifier failed') from None
                require(result.returncode == 0 and len(result.stdout) < 4*1024*1024, 'Bundle verifier rejected candidate')
                return result.stdout
            signature = run(['jarsigner','-J-Duser.language=en','-verify',str(aab)])
            require(any(line.strip() == 'jar verified.' for line in signature.splitlines()), 'Bundle is not cryptographically signed')
            sha1, sha256 = parse_certificate(run(['keytool','-J-Duser.language=en','-printcert','-jarfile',str(aab)]))
            run(['java','-jar',str(self.jar),'validate','--bundle='+str(aab)])
            def value(xpath): return run(['java','-jar',str(self.jar),'dump','manifest','--bundle='+str(aab),'--xpath='+xpath]).strip()
            return {'jarVerified': True,'sha1':sha1,'sha256':sha256,'package':value('/manifest/@package'),
                'versionCode':numeric_id(value('/manifest/@android:versionCode')),'versionName':value('/manifest/@android:versionName')}
