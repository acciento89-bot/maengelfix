"""Exact known-binary game schema; no fabricated CI or future arbitrary upload."""
import re
from datetime import datetime,timezone
from candidate import Candidate,checked_entry,require,digest,is_digest,listing_locales,zip_files,strict_json,recent_timestamp,decode_png,png_dimensions
from game_binary import binary_files

def validate_game_archive(raw, archive_sha256, package, catalog, verifier, now=None, family='game5'):
    from game_policy import scope, version, require_ready, verify_source_evidence, verify_final_reviews, validate_frame_language
    require(family == 'game5', 'Explicit closed game family required')
    expected_scope = scope(family)
    require(package in expected_scope and package in catalog, 'Package outside fixed scope')
    require(is_digest(archive_sha256) and digest(raw) == archive_sha256, 'Candidate archive SHA mismatch')
    app = catalog[package]; locales = require_ready(app) if family == 'game5' else listing_locales(app);
    version_name = version(package, family); certificate = app['certificate'] if family == 'game5' else {'sha1':CENTRAL_SHA1,'sha256':CENTRAL_SHA256}; files = zip_files(raw); now = now or datetime.now(timezone.utc)
    require('manifest.json' in files and len(files['manifest.json']) <= 128 * 1024, 'Missing/oversized manifest')
    manifest = strict_json(files['manifest.json'])
    require(isinstance(manifest,dict), 'Manifest must be a JSON object')
    required = {'schema','package','versionCode','versionName','bundle','nativeQa','screenshots','localeInventory','rootReview','rightsEvidence','sourceEvidence'}
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
    bundle = checked_entry(files, manifest['bundle']); require(bundle.sha256 == app['signedAabSha256'] and len(bundle.data) == app['signedAabBytes'], 'Unknown future game binary'); aab_files = binary_files(bundle.data)
    require('base/manifest/AndroidManifest.xml' in aab_files and any(re.fullmatch(r'META-INF/[^/]+\.SF', p, re.I) for p in aab_files) and
        any(re.fullmatch(r'META-INF/[^/]+\.(RSA|DSA|EC)', p, re.I) for p in aab_files), 'Unsigned or invalid AAB')
    for asset in app['requiredBundleAssets']:
        require(asset['entry'] in aab_files and digest(aab_files[asset['entry']]) == asset['sha256'], 'Required font/license/notice AAB bytes mismatch')
    source_media = verify_source_evidence(files,manifest,app,bundle)
    require(isinstance(manifest['screenshots'],dict) and set(manifest['screenshots']) == set(locales), 'Screenshots required for each selected existing locale')
    screenshots = {}; raw_screenshots = []
    for locale in locales:
        entries = manifest['screenshots'][locale]
        require(isinstance(entries,list) and 4 <= len(entries) <= (4 if family == 'game5' else 8), 'Four to eight distinct native screenshots required per locale')
        pictures = []; pixel_hashes = set()
        for frame_index,entry in enumerate(entries):
            fields = {'path','sha256','rawNative','pixelSha256'} | ({'inAppLanguage','mixedUi','languageLimitation','screenScope'} if family == 'game5' else set())
            require(isinstance(entry,dict) and set(entry) == fields, 'Invalid localized screenshot binding')
            if family == 'game5': validate_frame_language(app,locale,frame_index,entry)
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
    if family == 'game5':
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
    essential = ['manifest.json',bundle.path,native.path,inventory_file.path,apk_file.path] + [m.path for m in source_media] + [m.path for group in screenshots.values() for m in group] + [m.path for m in raw_screenshots] + ([icon.path] if icon else [])
    listed = essential + [m.path for m in proofs]
    if family == 'calculator9': require(len(essential) == len(set(essential)) and set(files) == set(listed), 'Unlisted/overlapping candidate files')
    if family == 'game5':
        reviews = verify_final_reviews(files,manifest,app,bundle,qa,native,now)
        essential += [m.path for m in reviews]
        require(len(essential) == len(set(essential)) and set(files) == set(essential + [m.path for m in proofs]), 'Unlisted/overlapping business review files')
    verified = verifier.verify(bundle.data, app)
    require(verified.get('jarVerified') is True and verified.get('sha1') == certificate['sha1'] and verified.get('sha256') == certificate['sha256'] and
        verified.get('package') == package and type(verified.get('versionCode')) is int and verified['versionCode'] == app['newVersionCode'] and verified.get('versionName') == version_name, 'Actual signed AAB certificate/identity verification failed')
    return Candidate(package, app, manifest, bundle.data, bundle.sha256, archive_sha256, screenshots, icon, native.sha256)
