"""Synthetic local unit fixtures. These never assert genuine product/native QA."""
import copy, hashlib, io, json, struct, sys, zlib, zipfile
from datetime import datetime, timezone
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
PACKAGE = 'de.kamilunavo.brennercalc'
SHA1 = 'BCF2337D41E617C03BCAE698C09D1523654BD790'
SHA256 = '7985BD6B33711BACA7E6BA722C2B3870EBBC802F7DB4A7BC1206BDAE51C4D5D6'
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def encode(data): return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
def packed(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items(): z.writestr(name, raw)
    return stream.getvalue()
def png(color, width=320, height=640):
    def chunk(kind, raw): return struct.pack('>I', len(raw)) + kind + raw + struct.pack('>I', zlib.crc32(kind + raw) & 0xffffffff)
    pixels = b''.join(b'\0' + bytes(color) * width for _ in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6 if len(color)==4 else 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
class Verifier:
    def __init__(self, **overrides): self.overrides = overrides; self.calls = []
    def verify(self, raw, app):
        self.calls.append(digest(raw))
        return dict(package=app['package'], versionCode=app['newVersionCode'], versionName='1.2.0',
                    sha1=SHA1, sha256=SHA256, jarVerified=True, **self.overrides)
class Fixture:
    def __init__(self):
        self.catalog = {a['package']: a for a in json.loads((HERE / 'catalog.json').read_text())['apps']}
        self.catalog = copy.deepcopy(self.catalog); self.app = self.catalog[PACKAGE]
        self.app['releaseNotes']={'de-DE':'Synthetischer Testhinweis','en-US':'Synthetic unit test note'}
        self.app['requiredBundleAssets'] = [{'entry': 'base/assets/font.txt', 'sha256': digest(b'unit-font-not-real') }]
        self.aab = packed({'base/manifest/AndroidManifest.xml': b'unit-only-binary-manifest', 'base/assets/font.txt': b'unit-font-not-real',
                           'META-INF/MANIFEST.MF': b'unit signature manifest', 'META-INF/UPLOAD.SF': b'unit signature', 'META-INF/UPLOAD.RSA': b'unit not real cert'})
        self.files = {'bundle/app.aab': self.aab, 'qa/proof.json': b'{"unit_fixture_only":true}'}
        self.screens = {}
        for locale_index, locale in enumerate(('de-DE','en-US')):
            self.screens[locale] = []
            for i in range(4):
                color = (22 + locale_index*80+i, 44+i, 66+i)
                rgb = 'screens/'+locale+'/'+str(i+1).zfill(2)+'.png'; native = 'raw/'+locale+'/'+str(i+1).zfill(2)+'.png'
                self.files[rgb] = png(color); self.files[native] = png((*color,255))
                self.screens[locale].append({**self.entry(rgb),'rawNative':self.entry(native),'pixelSha256':digest(bytes(color)*320*640)})
        inventory={'schema':1,'operation':'inspect_existing_locales','ok':True,'inspectedAtUTC':NOW.isoformat(),'apps':[{'package':PACKAGE,'status':'ok','localeIds':['de-DE','en-US'],'cleanup':{'confirmed':True,'httpStatus':204}}]}
        self.files['qa/locale-inventory.json']=encode(inventory)
        self.app['listingLocales']=['de-DE','en-US']; self.app['localeSnapshotSha256']=digest(self.files['qa/locale-inventory.json'])
        self.files['qa/derived-apk-proof.json']=encode({'package':PACKAGE,'versionCode':self.app['newVersionCode'],'versionName':'1.2.0','sourceCommit':self.app['reviewedSourceCommit'],'sourceAabSha256':digest(self.aab),'apkSha256':'b'*64,'normalApplication':True})
        self.manifest = {'schema': 1, 'package': PACKAGE, 'versionCode': self.app['newVersionCode'], 'versionName': '1.2.0',
            'source': {'repository': self.app['repository'], 'commit': self.app['reviewedSourceCommit'], 'workflow': self.app['sourceWorkflow'],
                       'runId': 42, 'artifactId': 52, 'artifactArchiveSha256': 'a' * 64},
            'signing': {'repository': self.app['repository'], 'commit': self.app['reviewedSourceCommit'], 'workflow': self.app['signWorkflow'],
                        'runId': 43, 'artifactId': 53, 'artifactArchiveSha256': '', 'archive': 'provenance/signed-ci-artifact.zip'},
            'localeInventory':self.entry('qa/locale-inventory.json'), 'bundle': self.entry('bundle/app.aab'), 'nativeQa': {'path': 'qa/native-qa.json', 'sha256': ''},
            'screenshots': copy.deepcopy(self.screens)}
        provenance = {'GITHUB_REPOSITORY': self.app['repository'], 'GITHUB_SHA': self.app['reviewedSourceCommit'], 'GITHUB_RUN_ID': '43',
            'PACKAGE_NAME': PACKAGE, 'VERSION_CODE': str(self.app['newVersionCode']), 'VERSION_NAME': '1.2.0', 'CENTRAL_SHA1': SHA1, 'CENTRAL_SHA256': SHA256,
            'SOURCE_RUN_ID': '42', 'SOURCE_COMMIT': self.app['reviewedSourceCommit'], 'SOURCE_ARTIFACT_ID': '52', 'SOURCE_ARTIFACT_DIGEST': 'sha256:' + 'a' * 64, 'VERSION_OVERRIDE': None}
        self.signed_files = {'app-release.aab': self.aab, 'provenance.json': encode(provenance)}
        self.qa = {'schema': 1, 'outcome': 'pass', 'platform': 'Android', 'normalApplication': True, 'package': PACKAGE,
            'versionCode': self.app['newVersionCode'], 'versionName': '1.2.0', 'sourceCommit': self.app['reviewedSourceCommit'], 'signedAabSha256': digest(self.aab),
            'testedApkSha256': 'b' * 64, 'apkProof': self.entry('qa/derived-apk-proof.json'), 'testedAtUtc': NOW.isoformat(), 'captureLanguages': ['de-DE','en-US'],
            'realTransactions': {'purchases': False, 'restores': False, 'redemptions': False, 'adImpressions': False},
            'checks': {'launch': True, 'main': True, 'navigation': True, 'fontAndAssets': True},
            'screenshots': copy.deepcopy(self.manifest['screenshots']), 'proof': [self.entry('qa/proof.json')]}
    def entry(self, name): return {'path': name, 'sha256': digest(self.files[name])}
    def raw(self):
        self.files[self.manifest['signing']['archive']] = packed(self.signed_files)
        self.manifest['signing']['artifactArchiveSha256'] = digest(self.files[self.manifest['signing']['archive']])
        self.files['qa/native-qa.json'] = encode(self.qa); self.manifest['nativeQa']['sha256'] = digest(self.files['qa/native-qa.json'])
        self.files['manifest.json'] = encode(self.manifest)
        return packed(self.files)
