"""Game-only inner AAB/APK '+' filename compatibility; outer candidate paths stay strict."""
import io,re,stat,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
from candidate import CandidateError,MAX_ARCHIVE,require,digest,is_digest,parse_certificate,verify_signature_manifest,numeric_id

def binary_name(name):
    require(isinstance(name, str) and len(name) <= 240 and (re.fullmatch(r'[A-Za-z0-9_./+-]+', name) is not None or name in {'base/assets/bin/Data/Resources/unity default resources','assets/bin/Data/Resources/unity default resources'}),
            'Unsafe archive filename')
    p = PurePosixPath(name)
    require(not p.is_absolute() and all(x not in ('.', '..') for x in name.split('/')) and str(p) == name,
            'Unsafe archive path')
    return name

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

class GameBundleVerifier:
    """Runs only in future prepare/verify jobs on owner-approved genuine input."""
    def __init__(self, bundletool, expected_jar_sha256):
        self.jar = Path(bundletool)
        require(is_digest(expected_jar_sha256) and digest(self.jar.read_bytes()) == expected_jar_sha256, 'Pinned bundletool digest mismatch')
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
