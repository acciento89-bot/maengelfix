"""Bounded, fixed-scope verification. No network and no Google identity here."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import base64
import binascii
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import tempfile
import zipfile
import zlib

CENTRAL_SHA1 = 'BCF2337D41E617C03BCAE698C09D1523654BD790'
CENTRAL_SHA256 = '7985BD6B33711BACA7E6BA722C2B3870EBBC802F7DB4A7BC1206BDAE51C4D5D6'
EXPECTED = {'de.kamilunavo.brennercalc': (6, 7), 'de.kamilunavo.hydrocalc': (5, 6),
    'de.kamilunavo.magcalc': (6, 7), 'de.kamilunavo.volumecalc': (5, 6),
    'de.kamilunav.kaltecalc': (4, 5), 'de.kamilunavo.luftungscalc': (4, 5),
    'de.kamilunavo.heizkorpercalc': (4, 5), 'de.kamilunavo.rohrcalc': (4, 5), 'de.kamilunavo.servicecheck': (4, 5)}
LOCALES = ('de-DE', 'en-US')
MAX_ARCHIVE = 256 * 1024 * 1024

class CandidateError(ValueError):
    pass

def require(value, message):
    if not value: raise CandidateError(message)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def is_digest(value): return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None

def numeric_id(value):
    require(type(value) in (int, str) and re.fullmatch(r'[1-9][0-9]{0,18}', str(value)) is not None, 'Invalid numeric identity')
    require(int(value) < 2**63, 'Numeric identity out of range')
    return int(value)

def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    try: return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, 'Nonfinite JSON'))
    except (ValueError, UnicodeError, TypeError) as error:
        if isinstance(error, CandidateError): raise
        raise CandidateError('Invalid JSON') from None

def safe_name(name):
    require(isinstance(name, str) and len(name) <= 240 and re.fullmatch(r'[A-Za-z0-9_./-]+', name) is not None,
            'Unsafe archive filename')
    p = PurePosixPath(name)
    require(not p.is_absolute() and all(x not in ('.', '..') for x in name.split('/')) and str(p) == name,
            'Unsafe archive path')
    return name

def zip_files(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ARCHIVE, 'Archive size outside bounds')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist(); require(0 < len(infos) <= 5000, 'Archive entry count outside bounds')
            names = set(); files = {}; total = 0
            for info in infos:
                name = info.filename.rstrip('/') if info.is_dir() else info.filename
                safe_name(name); folded = name.casefold()
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

def listing_locales(app, allow_pending=False):
    locales = app.get('listingLocales'); snapshot = app.get('localeSnapshotSha256')
    if allow_pending and locales is None and snapshot is None: return None
    require(isinstance(locales,list) and 1 <= len(locales) <= 2 and len(set(locales)) == len(locales) and
        all(isinstance(l,str) and re.fullmatch(r'(?:de|en)(?:-[A-Za-z0-9]{2,8})*',l) and len(l)<=24 for l in locales) and
        len({l.split('-')[0] for l in locales}) == len(locales) and is_digest(snapshot), 'Existing listing locales must first be inventory-pinned')
    require(set(app.get('releaseNotes',{})) == set(locales), 'Release notes must match selected existing locales')
    return tuple(locales)

def load_catalog(path, expected_sha256, family='calculator9'):
    if family != 'calculator9':
        from business_policy import load_catalog as business_catalog
        require(family == 'business12', 'Unknown closed submission family')
        return business_catalog(path, expected_sha256)
    raw = Path(path).read_bytes()
    require(is_digest(expected_sha256) and digest(raw) == expected_sha256, 'Catalog SHA mismatch')
    data = strict_json(raw); require(isinstance(data,dict) and type(data.get('schema')) is int and data['schema'] == 1 and
        data.get('localePolicy') == {'families':['de','en'],'maximumSelected':2}, 'Catalog schema/locale policy mismatch')
    require(isinstance(data.get('apps'), list) and len(data['apps']) == 9, 'Exactly nine calculators required')
    result = {}
    for app in data['apps']:
        package = app.get('package'); require(package in EXPECTED and package not in result, 'Excluded/duplicate calculator identity')
        previous, new = EXPECTED[package]
        require(type(app.get('previousMaxCode')) is int and app['previousMaxCode'] == previous and
            type(app.get('previousProductionCode')) is int and app['previousProductionCode'] == previous and
            type(app.get('newVersionCode')) is int and app['newVersionCode'] == new and app.get('newVersionName') == '1.2.0', 'Fixed release version mismatch')
        require(re.fullmatch(r'acciento89-bot/[A-Za-z0-9_-]+', app.get('repository', '')) and
                re.fullmatch(r'[a-f0-9]{40}', app.get('reviewedSourceCommit', '')), 'Missing reviewed source identity')
        listing_locales(app,allow_pending=True)
        require(isinstance(app.get('releaseNotes'),dict) and 1 <= len(app['releaseNotes']) <= 2 and all(isinstance(v, str) and 1 <= len(v) <= 500 for v in app['releaseNotes'].values()), 'Missing fixed release notes')
        require(isinstance(app.get('requiredBundleAssets'), list) and app['requiredBundleAssets'], 'Missing raw font/license asset inventory')
        for asset in app['requiredBundleAssets']: safe_name(asset['entry']); require(is_digest(asset.get('sha256')), 'Invalid required bundle asset digest')
        result[package] = app
    require(set(result) == set(EXPECTED), 'Nine-app scope mismatch')
    return result

@dataclass(frozen=True)
class DecodedPng:
    width: int
    height: int
    color_type: int
    rgb: bytes
    opaque: bool
    transparency_chunk: bool

def decode_png(raw):
    require(raw[:8] == b'\x89PNG\r\n\x1a\n' and len(raw) <= 20 * 1024 * 1024, 'PNG signature/size mismatch')
    offset = 8; dims = None; data = []; ended = False; color = None; transparency = False
    while offset < len(raw):
        require(offset + 12 <= len(raw), 'Truncated PNG chunk')
        size = struct.unpack('>I', raw[offset:offset+4])[0]; kind = raw[offset+4:offset+8]
        require(offset + 12 + size <= len(raw), 'Truncated PNG body')
        payload = raw[offset+8:offset+8+size]; crc = struct.unpack('>I', raw[offset+8+size:offset+12+size])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == crc, 'PNG CRC mismatch')
        if dims is None:
            require(kind == b'IHDR' and size == 13, 'PNG requires first IHDR')
            width, height, bits, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            require(1 <= width <= 8192 and 1 <= height <= 8192 and width * height <= 16_000_000 and
                bits == 8 and color in (2, 6) and compression == filtering == interlace == 0, 'Unsupported native PNG dimensions/format')
            dims = (width, height)
        elif kind == b'IHDR': raise CandidateError('Duplicate PNG IHDR')
        require(kind not in (b'acTL',b'fcTL',b'fdAT'), 'Animated screenshots rejected')
        require(kind in (b'IHDR',b'PLTE',b'IDAT',b'IEND') or kind[0] & 32, 'Unsupported critical PNG chunk')
        if kind == b'tRNS': transparency = True
        if kind == b'IDAT': data.append(payload)
        if kind == b'IEND':
            require(size == 0 and offset + 12 == len(raw), 'PNG trailing data or invalid IEND'); ended = True
        offset += size + 12
    require(ended and data, 'Incomplete PNG')
    expected = dims[1] * (1 + dims[0] * (3 if color == 2 else 4))
    try:
        decoder = zlib.decompressobj(); pixels = decoder.decompress(b''.join(data), expected + 1)
        require(len(pixels) == expected and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data, 'Invalid PNG pixel stream')
    except zlib.error: raise CandidateError('Invalid PNG compression') from None
    channels = 3 if color == 2 else 4; stride = dims[0]*channels
    decoded = bytearray(dims[1]*stride); previous = bytearray(stride)
    for y in range(dims[1]):
        offset = y*(stride+1); filtering = pixels[offset]; row = bytearray(pixels[offset+1:offset+stride+1])
        require(filtering <= 4, 'Unknown PNG row filter')
        if filtering:
            for i in range(stride):
                left = row[i-channels] if i >= channels else 0
                up = previous[i]; diagonal = previous[i-channels] if i >= channels else 0
                if filtering == 1: prediction = left
                elif filtering == 2: prediction = up
                elif filtering == 3: prediction = (left+up)//2
                else:
                    p = left+up-diagonal; a,b,c = abs(p-left),abs(p-up),abs(p-diagonal)
                    prediction = left if a <= b and a <= c else up if b <= c else diagonal
                row[i] = (row[i]+prediction)&255
        decoded[y*stride:(y+1)*stride] = row; previous = row
    if color == 6:
        opaque = decoded[3::4] == b'\xff'*(dims[0]*dims[1])
        rgb = bytearray(dims[0]*dims[1]*3); rgb[0::3]=decoded[0::4];rgb[1::3]=decoded[1::4];rgb[2::3]=decoded[2::4]
    else: opaque = True; rgb = decoded
    return DecodedPng(dims[0],dims[1],color,bytes(rgb),opaque and not transparency,transparency)

def png_dimensions(raw):
    image = decode_png(raw); return image.width,image.height

def recent_timestamp(value, now, description):
    try: stamp = datetime.fromisoformat(value.replace('Z','+00:00'))
    except (AttributeError,ValueError,TypeError): raise CandidateError('Invalid '+description+' date') from None
    require(stamp.tzinfo is not None and now-timedelta(days=7) <= stamp <= now+timedelta(minutes=5), 'Stale/future '+description+' evidence')

@dataclass(frozen=True)
class Media:
    path: str
    sha256: str
    data: bytes

@dataclass(frozen=True)
class Candidate:
    package: str
    app: dict
    manifest: dict
    aab: bytes
    bundle_sha256: str
    archive_sha256: str
    screenshots: dict
    icon: object
    native_qa_sha256: str

def checked_entry(files, entry):
    require(isinstance(entry, dict) and set(entry) == {'path', 'sha256'}, 'Invalid file manifest entry')
    name = safe_name(entry['path']); require(name in files and is_digest(entry['sha256']) and digest(files[name]) == entry['sha256'], 'Manifest file hash mismatch')
    return Media(name, entry['sha256'], files[name])

def validate_archive(raw, archive_sha256, package, catalog, verifier, now=None, family='calculator9'):
    from business_policy import scope, version, require_ready, verify_business_provenance, verify_final_reviews, validate_frame_language
    expected_scope = scope(family)
    require(package in expected_scope and package in catalog, 'Package outside fixed scope')
    require(is_digest(archive_sha256) and digest(raw) == archive_sha256, 'Candidate archive SHA mismatch')
    app = catalog[package]; locales = require_ready(app) if family == 'business12' else listing_locales(app);
    version_name = version(package, family); certificate = app['certificate'] if family == 'business12' else {'sha1':CENTRAL_SHA1,'sha256':CENTRAL_SHA256}; files = zip_files(raw); now = now or datetime.now(timezone.utc)
    require('manifest.json' in files and len(files['manifest.json']) <= 128 * 1024, 'Missing/oversized manifest')
    manifest = strict_json(files['manifest.json'])
    require(isinstance(manifest,dict), 'Manifest must be a JSON object')
    required = {'schema', 'package', 'versionCode', 'versionName', 'source', 'signing', 'bundle', 'nativeQa', 'screenshots','localeInventory'}
    if family == 'business12':
        required |= {'rootReview','rightsEvidence'}
        if app['route'] == 'managed_eas': required -= {'signing'}
    require(set(manifest) in (required, required | {'icon'}), 'Unexpected manifest fields')
    require(type(manifest['schema']) is int and manifest['schema'] == 1 and manifest['package'] == package and type(manifest['versionCode']) is int and
        manifest['versionCode'] == app['newVersionCode'] and manifest['versionName'] == version_name, 'Candidate identity mismatch')
    inventory_file = checked_entry(files,manifest['localeInventory'])
    require(inventory_file.sha256 == app['localeSnapshotSha256'] and len(inventory_file.data) <= 512*1024, 'Locale inventory differs from reviewed catalog snapshot')
    inventory = strict_json(inventory_file.data)
    require(isinstance(inventory,dict) and type(inventory.get('schema')) is int and inventory['schema'] == 1 and inventory.get('ok') is True and
        inventory.get('operation') == 'inspect_existing_locales' and isinstance(inventory.get('apps'),list), 'Invalid owned locale inventory evidence')
    rows = [row for row in inventory['apps'] if isinstance(row,dict) and row.get('package') == package]
    require(len(rows) == 1 and rows[0].get('status') == 'ok' and isinstance(rows[0].get('localeIds'),list) and
        len(set(rows[0]['localeIds'])) == len(rows[0]['localeIds']) and set(locales) <= set(rows[0]['localeIds']) and
        rows[0].get('cleanup',{}).get('confirmed') is True and (rows[0]['cleanup'].get('httpStatus') in (204,404) or
            (rows[0]['cleanup'].get('httpStatus') == 200 and rows[0]['cleanup'].get('emptyJsonAcknowledgement') is True)), 'Locale inventory/owned-edit cleanup not verified')
    recent_timestamp(inventory.get('inspectedAtUTC'),now,'locale inventory')
    ci_sections = [('source', 'sourceWorkflow'), ('signing', 'signWorkflow')] if family == 'calculator9' or app['route'] == 'central_kms' else [('source','sourceWorkflow')]
    for section, workflow in ci_sections:
        part = manifest[section]
        require(isinstance(part, dict) and set(part) == {'repository','commit','workflow','runId','artifactId','artifactArchiveSha256'} | ({'archive'} if section == 'signing' or family == 'business12' else set()), 'Invalid CI identity fields')
        require(part['repository'] == app['repository'] and part['commit'] == app['reviewedSourceCommit'] and part['workflow'] == app[workflow], 'Unreviewed CI source/sign identity')
        numeric_id(part['runId']); numeric_id(part['artifactId']); require(is_digest(part['artifactArchiveSha256']), 'Missing official CI archive digest')
    bundle = checked_entry(files, manifest['bundle'])
    if family == 'business12':
        from business_binary import binary_files
        aab_files = binary_files(bundle.data)
    else: aab_files = zip_files(bundle.data)
    require('base/manifest/AndroidManifest.xml' in aab_files and any(re.fullmatch(r'META-INF/[^/]+\.SF', p, re.I) for p in aab_files) and
        any(re.fullmatch(r'META-INF/[^/]+\.(RSA|DSA|EC)', p, re.I) for p in aab_files), 'Unsigned or invalid AAB')
    for asset in app['requiredBundleAssets']:
        require(asset['entry'] in aab_files and digest(aab_files[asset['entry']]) == asset['sha256'], 'Required font/license/notice AAB bytes mismatch')
    signing = manifest['signing'] if 'signing' in manifest else manifest['source']; signed_path = safe_name(signing['archive'])
    require(signed_path in files and digest(files[signed_path]) == signing['artifactArchiveSha256'], 'Signed CI archive digest mismatch')
    signed_files = zip_files(files[signed_path]); aabs = [p for p in signed_files if p.endswith('.aab')]
    provenance = [p for p in signed_files if PurePosixPath(p).name == 'provenance.json']
    require(len(aabs) == len(provenance) == 1 and signed_files[aabs[0]] == bundle.data, 'Candidate differs from original signed CI artifact')
    proof = strict_json(signed_files[provenance[0]])
    require(isinstance(proof,dict), 'Signing provenance must be a JSON object')
    expected = {'GITHUB_REPOSITORY': app['repository'], 'GITHUB_SHA': app['reviewedSourceCommit'], 'GITHUB_RUN_ID': str(signing['runId']),
        'PACKAGE_NAME': package, 'VERSION_CODE': str(app['newVersionCode']), 'VERSION_NAME': version_name, 'CENTRAL_SHA1': CENTRAL_SHA1, 'CENTRAL_SHA256': CENTRAL_SHA256,
        'SOURCE_RUN_ID': str(manifest['source']['runId']), 'SOURCE_COMMIT': app['reviewedSourceCommit'], 'SOURCE_ARTIFACT_ID': str(manifest['source']['artifactId']),
        'SOURCE_ARTIFACT_DIGEST': 'sha256:' + manifest['source']['artifactArchiveSha256']}
    business_provenance_files = []
    if family == 'business12': business_provenance_files = verify_business_provenance(app,manifest,proof,bundle.sha256,files)
    else: require(all(proof.get(k) == v for k,v in expected.items()) and proof.get('VERSION_OVERRIDE') in (None, ''), 'Signed CI original provenance mismatch')
    require(isinstance(manifest['screenshots'],dict) and set(manifest['screenshots']) == set(locales), 'Screenshots required for each selected existing locale')
    screenshots = {}; raw_screenshots = []
    for locale in locales:
        entries = manifest['screenshots'][locale]
        require(isinstance(entries,list) and 4 <= len(entries) <= (4 if family == 'business12' else 8), 'Four to eight distinct native screenshots required per locale')
        pictures = []; pixel_hashes = set()
        for frame_index,entry in enumerate(entries):
            fields = {'path','sha256','rawNative','pixelSha256'} | ({'inAppLanguage','mixedUi','languageLimitation'} if family == 'business12' else set())
            require(isinstance(entry,dict) and set(entry) == fields, 'Invalid localized screenshot binding')
            if family == 'business12': validate_frame_language(app,locale,frame_index,entry)
            image = checked_entry(files,{'path':entry['path'],'sha256':entry['sha256']}); native_image = checked_entry(files,entry['rawNative'])
            require(image.path.startswith('screens/'+locale+'/') and native_image.path.startswith('raw/'+locale+'/') and image.path.endswith('.png') and native_image.path.endswith('.png'), 'Screenshot paths must bind their selected locale')
            rgb = decode_png(image.data); original = decode_png(native_image.data)
            require(rgb.color_type == 2 and not rgb.transparency_chunk and rgb.opaque and original.opaque and
                320 <= rgb.width <= 3840 and 320 <= rgb.height <= 3840 and max(rgb.width,rgb.height) <= 2*min(rgb.width,rgb.height), 'Screenshot must be bounded RGB24 opaque PNG with maximum2:1 aspect')
            require((rgb.width,rgb.height) == (original.width,original.height) and rgb.rgb == original.rgb and
                is_digest(entry['pixelSha256']) and digest(rgb.rgb) == entry['pixelSha256'], 'Raw native and RGB screenshot pixels/dimensions differ')
            require(entry['pixelSha256'] not in pixel_hashes, 'Duplicate screenshot content within locale')
            pixel_hashes.add(entry['pixelSha256']); pictures.append(image); raw_screenshots.append(native_image)
        require(len({m.path for m in pictures}) == len(pictures), 'Duplicate localized screenshot paths')
        screenshots[locale] = tuple(pictures)
    native = checked_entry(files, manifest['nativeQa']); require(len(native.data) <= 512 * 1024, 'Oversized native QA report')
    qa = strict_json(native.data)
    require(isinstance(qa,dict) and type(qa.get('schema')) is int and qa['schema'] == 1 and qa.get('outcome') == 'pass' and qa.get('platform') == 'Android' and qa.get('normalApplication') is True and
        qa.get('package') == package and type(qa.get('versionCode')) is int and qa['versionCode'] == app['newVersionCode'] and qa.get('versionName') == version_name and
        qa.get('sourceCommit') == app['reviewedSourceCommit'] and qa.get('signedAabSha256') == bundle.sha256 and is_digest(qa.get('testedApkSha256')),
        'Native QA does not prove the exact normal candidate identity')
    if family == 'business12':
        require(qa.get('screenshots') == manifest['screenshots'] and 'captureLanguages' not in qa and isinstance(qa.get('listingLocales'),list) and len(qa['listingLocales']) == len(locales) and set(qa['listingLocales']) == set(locales), 'Business listing locales must be separate from actual per-frame UI languages')
    else:
        require(qa.get('screenshots') == manifest['screenshots'] and isinstance(qa.get('captureLanguages'),list) and
            len(qa['captureLanguages']) == len(locales) and set(qa['captureLanguages']) == set(locales), 'Native localized screenshot/capture declaration mismatch')
    require(qa.get('realTransactions') == {'purchases': False, 'restores': False, 'redemptions': False, 'adImpressions': False} and
        all(type(v) is bool for v in qa['realTransactions'].values()), 'Real commerce action in QA or ambiguous action evidence')
    require(qa.get('checks') == {'launch': True,'main': True,'navigation': True,'fontAndAssets': True} and all(type(v) is bool for v in qa['checks'].values()), 'Missing normal native QA checks')
    recent_timestamp(qa.get('testedAtUtc'),now,'native QA')
    apk_file = checked_entry(files,qa.get('apkProof'))
    apk_proof = strict_json(apk_file.data)
    require(apk_file.path.startswith('qa/') and isinstance(apk_proof,dict) and apk_proof.get('package') == package and
        type(apk_proof.get('versionCode')) is int and apk_proof['versionCode'] == app['newVersionCode'] and apk_proof.get('versionName') == version_name and
        apk_proof.get('sourceCommit') == app['reviewedSourceCommit'] and apk_proof.get('sourceAabSha256') == bundle.sha256 and
        apk_proof.get('apkSha256') == qa['testedApkSha256'] and apk_proof.get('normalApplication') is True, 'Derived/installed APK proof does not bind this signed AAB')
    require(isinstance(qa.get('proof'), list) and 1 <= len(qa['proof']) <= 16, 'Native QA raw proof required')
    proofs = [checked_entry(files, entry) for entry in qa['proof']]
    require(all(m.path.startswith('qa/') and m.path != native.path for m in proofs) and len({m.path for m in proofs}) == len(proofs), 'Ambiguous native proof paths')
    icon = checked_entry(files, manifest['icon']) if 'icon' in manifest else None
    if icon:
        require(app.get('optionalOriginalIcon') and icon.sha256 == app['optionalOriginalIcon']['sha256'] and png_dimensions(icon.data) == (512,512), 'Icon is not the exact pinned original512PNG')
    essential = ['manifest.json',bundle.path,signed_path,native.path,inventory_file.path,apk_file.path] + [m.path for group in screenshots.values() for m in group] + [m.path for m in raw_screenshots] + ([icon.path] if icon else [])
    listed = essential + [m.path for m in proofs]
    if family == 'calculator9': require(len(essential) == len(set(essential)) and set(files) == set(listed), 'Unlisted/overlapping candidate files')
    if family == 'business12':
        reviews = verify_final_reviews(files,manifest,app,bundle,qa,native,now)
        essential += [m.path for m in reviews] + [m.path for m in business_provenance_files]
        require(len(essential) == len(set(essential)) and set(files) == set(essential + [m.path for m in proofs]), 'Unlisted/overlapping business review files')
    verified = verifier.verify(bundle.data, app)
    require(verified.get('jarVerified') is True and verified.get('sha1') == certificate['sha1'] and verified.get('sha256') == certificate['sha256'] and
        verified.get('package') == package and type(verified.get('versionCode')) is int and verified['versionCode'] == app['newVersionCode'] and verified.get('versionName') == version_name, 'Actual signed AAB certificate/identity verification failed')
    return Candidate(package, app, manifest, bundle.data, bundle.sha256, archive_sha256, screenshots, icon, native.sha256)

def parse_certificate(text):
    def fingerprint(label, size):
        found = re.findall(r'^\s*' + label + r':\s*([A-Fa-f0-9:]+)\s*$', text, re.M)
        require(len(found) == 1, 'Exactly one signing certificate required')
        normalized = found[0].replace(':','').upper(); require(re.fullmatch('[A-F0-9]{'+str(size)+'}', normalized), 'Invalid certificate fingerprint')
        return normalized
    return fingerprint('SHA1',40), fingerprint('SHA256',64)

def verify_signature_manifest(files):
    manifests = [p for p in files if p.upper() == 'META-INF/MANIFEST.MF']
    signatures = [p for p in files if re.fullmatch(r'META-INF/[^/]+\.SF',p,re.I)]
    blocks = [p for p in files if re.fullmatch(r'META-INF/[^/]+\.(RSA|DSA|EC)',p,re.I)]
    require(len(manifests) == len(signatures) == len(blocks) == 1 and
        signatures[0].rsplit('.',1)[0].casefold() == blocks[0].rsplit('.',1)[0].casefold(), 'Exactly one complete signer required')
    def sections(raw):
        folded = []
        for line in raw.replace(b'\r\n',b'\n').split(b'\n'):
            if line.startswith(b' '):
                require(folded and folded[-1], 'Invalid manifest continuation'); folded[-1] += line[1:]
            else: folded.append(line)
        result = []; current = {}
        for line in folded + [b'']:
            if not line:
                if current: result.append(current); current = {}
                continue
            require(b': ' in line, 'Malformed signed manifest header')
            key,value = line.split(b': ',1)
            try: key = key.decode('ascii').lower(); value = value.decode('utf-8')
            except UnicodeError: raise CandidateError('Invalid signed manifest encoding') from None
            require(key not in current, 'Duplicate signed manifest header'); current[key] = value
        require(result, 'Empty signature/manifest'); return result
    def check_digest(value, raw):
        try: decoded = base64.b64decode(value,validate=True) if isinstance(value,str) else b''
        except (binascii.Error,ValueError): raise CandidateError('Malformed signed manifest digest') from None
        require(decoded == hashlib.sha256(raw).digest(), 'Unsigned or changed bundle payload entry')
    manifest_raw = files[manifests[0]]
    sf = sections(files[signatures[0]])
    check_digest(sf[0].get('sha-256-digest-manifest'),manifest_raw)
    headers = sections(manifest_raw); require(headers[0].get('manifest-version') == '1.0', 'Invalid JAR manifest version')
    entries = {}
    for header in headers[1:]:
        name = header.get('name'); require(isinstance(name,str) and name not in entries,'Ambiguous signed manifest entry'); entries[name] = header
    signature = re.compile(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)$',re.I)
    payload = {p for p in files if not signature.fullmatch(p)}
    require(set(entries) == payload, 'Unsigned or missing manifest-covered payload')
    for name in payload: check_digest(entries[name].get('sha-256-digest'),files[name])

class BundleVerifier:
    """Runs only in future prepare/verify jobs on owner-approved genuine input."""
    def __init__(self, bundletool, expected_jar_sha256):
        self.jar = Path(bundletool)
        require(is_digest(expected_jar_sha256) and digest(self.jar.read_bytes()) == expected_jar_sha256, 'Pinned bundletool digest mismatch')
    def verify(self, raw, app):
        verify_signature_manifest(zip_files(raw))
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
