"""Only five preverified binary hashes; no arbitrary future source or signing waiver."""
import json
from pathlib import Path
from candidate import EXPECTED,require,digest,strict_json,is_digest,safe_name,listing_locales
ROOT=Path(__file__).resolve().parent
REGISTRY_SHA='676ba178ae2736cd97ff10a87874701f57643699c143f2b18ada75369f9ba5d7'
PROVIDER_SHA='5b671173dcc7dfadd82fdd2f857176da57b7a418cabfbb1dd75de43b5a3286a5'
READY_FIELDS={'listingLocales','localeSnapshotSha256','releaseNotes','rootReviewSha256','rightsEvidenceSha256','frameLanguageRequirements','optionalOriginalIcon','readiness'}
_RESERVED_GAME_STEPS=frozenset({
    ('de.kamilunavo.ninenine',6,8,(7,)),
    ('de.kamilunavo.idlehandwerker',4,6,(5,)),
    ('com.kamilunavo.runenpfad',4,6,(5,)),
})

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))

def fixed_apps():
    raw=(ROOT/'known-games.json').read_bytes();require(digest(raw)==REGISTRY_SHA,'Known game registry SHA mismatch');d=strict_json(raw)
    require(d.get('schema')==1 and d.get('family')=='game5'and len(d.get('apps',[]))==5,'Exactly five known game binaries required')
    result={a['package']:a for a in d['apps']};require(len(result)==5,'Duplicate known game package');return result

def scope(family='calculator9'):
    if family=='calculator9':return EXPECTED
    require(family=='game5','Unknown closed game family');return {k:(a['previousMaxCode'],a['newVersionCode'])for k,a in fixed_apps().items()}

def version(package,family='calculator9'):
    require(package in scope(family),'Package outside fixed family');return '1.2.0'if family=='calculator9'else fixed_apps()[package]['newVersionName']

def assert_identity(app):
    require(isinstance(app,dict)and app.get('package')in fixed_apps(),'Excluded game identity');expected=fixed_apps()[app['package']]
    require(all(k in app and canonical(app[k])==canonical(v)for k,v in expected.items()),'Unknown binary/source/certificate/topology or fixed game identity mismatch')

def allows_reserved_game_step(app,maximum,family):
    if family!='game5':return False
    # Reservations belong to the immutable identity, never candidate readiness
    # or caller-supplied flags. Current registry rows have no reservation.
    assert_identity(app);known=fixed_apps()[app['package']]
    reserved=known.get('reservedUnusedVersionCodes')
    if not isinstance(reserved,list)or not all(type(code)is int for code in reserved):return False
    if type(maximum)is not int or type(known['previousMaxCode'])is not int or type(known['newVersionCode'])is not int:return False
    return (known['package'],maximum,known['newVersionCode'],tuple(reserved))in _RESERVED_GAME_STEPS and maximum==known['previousMaxCode']

def load_catalog(path,expected_sha):
    raw=Path(path).read_bytes();require(is_digest(expected_sha)and digest(raw)==expected_sha,'Game catalog SHA mismatch');d=strict_json(raw)
    require(isinstance(d,dict)and set(d)=={'schema','family','knownRegistrySha256','previousProviderSnapshotSha256','localePolicy','apps'}and type(d.get('schema'))is int and d['schema']==1 and d['family']=='game5'and d['knownRegistrySha256']==REGISTRY_SHA and d['previousProviderSnapshotSha256']==PROVIDER_SHA and d['localePolicy']=={'families':['de','en'],'maximumSelected':2},'Game catalog shape/registry mismatch')
    previous=(ROOT/'provider-previous-state.json').read_bytes();require(digest(previous)==PROVIDER_SHA,'Historical provider snapshot SHA mismatch')
    require(isinstance(d['apps'],list)and len(d['apps'])==5,'Exactly five game catalog rows required');result={}
    for app in d['apps']:
        assert_identity(app);require(set(app)==set(fixed_apps()[app['package']])|READY_FIELDS and app['package']not in result,'Unexpected/duplicate game catalog fields')
        require(app['readiness']in('pending_final_native_screens_locales_rights_root_review','root_reviewed_candidate_inputs'),'Unknown game readiness')
        require(isinstance(app['releaseNotes'],dict),'Release notes must be an object')
        if app['listingLocales']is None:require(app['localeSnapshotSha256']is None and app['releaseNotes']=={},'Pending listing locale evidence cannot invent notes')
        else:listing_locales(app)
        require(all(app[k]is None or is_digest(app[k])for k in ('rootReviewSha256','rightsEvidenceSha256')),'Invalid root review hash')
        language_requirements(app,allow_pending=True);result[app['package']]=app
    require(set(result)==set(scope('game5')),'Exact five-game scope required');return result

def require_ready(app):
    assert_identity(app);require(app.get('readiness')=='root_reviewed_candidate_inputs','Final native/screens/rights/root review remains pending');locales=listing_locales(app)
    require(len(locales)==2 and {l.split('-')[0]for l in locales}=={'de','en'},'Actual existing DE/EN listing inventory required')
    require(is_digest(app.get('rootReviewSha256'))and is_digest(app.get('rightsEvidenceSha256')),'Final exact candidate/root/rights review missing')
    require(all(isinstance(v,str)and 1<=len(v)<=500 for v in app['releaseNotes'].values()),'Factual fixed release notes required');language_requirements(app);return locales

def language_requirements(app,allow_pending=False):
    requirements=app.get('frameLanguageRequirements')
    if allow_pending and requirements is None:return None
    locales=listing_locales(app);require(isinstance(requirements,dict)and set(requirements)==set(locales),'Actual per-frame language review pending')
    for locale,frames in requirements.items():
        require(isinstance(frames,list)and len(frames)==4,'Four reviewed frames per selected listing required')
        for row in frames:
            require(isinstance(row,dict)and set(row)=={'inAppLanguage','mixedUi','languageLimitation','screenScope'},'Explicit actual visible game language and screen scope required')
            language=row['inAppLanguage'];mixed=row['mixedUi'];limit=row['languageLimitation'];screen=row['screenScope']
            require(language in('de','en','mixed-de-en')and type(mixed)is bool and mixed is(language=='mixed-de-en')and isinstance(limit,str)and len(limit)<=500 and screen in('practice','other'),'Ambiguous UI language/mixed/screen declaration')
            require(not(mixed or language!=locale.split('-')[0])or bool(limit.strip()),'Mixed or listing/UI-language difference needs factual limitation')
            require(app['uiLanguagePolicy']!='german_only'or language=='de','Idle actual source is German-only')
            require(app['uiLanguagePolicy']!='english_only_practice'or language=='de'or screen=='practice','Nine English coverage is Practice only, not global English UI')
    return requirements

def validate_frame_language(app,locale,index,entry):
    requirements=language_requirements(app);require(locale in requirements and type(index)is int and 0<=index<4,'Unpinned listing/frame language')
    require(all(k in entry and canonical(entry[k])==canonical(v)for k,v in requirements[locale][index].items()),'Visible UI differs from pinned actual per-frame language contract')

def metadata_routes():
    return {cloud_route(row)for app in fixed_apps().values()for row in app['sourceTopology']['cloudReads']}

def cloud_route(row):return '/repos/'+row['repository']+'/actions/'+('runs'if row['kind']=='run'else'artifacts')+'/'+str(row['id'])

def verify_current_source(github,candidate):
    app=candidate.app;assert_identity(app);require(candidate.bundle_sha256==app['signedAabSha256'],'Unknown binary cannot inherit known source evidence');reads=[]
    for row in app['sourceTopology']['cloudReads']:
        path=cloud_route(row);value=github.json(path)
        if row['kind']=='run':
            require(type(value.get('id'))is int and value['id']==row['id']and value.get('head_sha')==row['head']and value.get('head_branch')=='main'and value.get('path')==row['workflow']and value.get('event')=='workflow_dispatch'and value.get('run_attempt')==1 and type(value.get('run_attempt'))is int and value.get('status')=='completed'and value.get('conclusion')=='success'and value.get('repository',{}).get('full_name')==row['repository']and value.get('head_repository',{}).get('full_name')==row['repository'],'Exact known cloud source/signer run changed or unavailable')
        else:
            source=value.get('workflow_run',{});require(type(value.get('id'))is int and value['id']==row['id']and value.get('name')==row['name']and value.get('expired')is False and value.get('digest')=='sha256:'+row['archiveSha256']and source.get('id')==row['runId']and source.get('head_sha')==row['head']and source.get('head_branch')=='main','Exact known immutable signer/source artifact changed or unavailable')
        reads.append({'path':path,'identity':row['id']})
    return {'kind':app['sourceTopology']['kind'],'knownSignedAabSha256':app['signedAabSha256'],'sourceCommit':app['reviewedSourceCommit'],'githubOrigin':app['repository'],'actualFixedMetadataReads':reads,'noInventedLocalCi':True}


def verify_source_evidence(files,manifest,app,bundle):
    from candidate import checked_entry
    from game_binary import binary_files as zip_files
    assert_identity(app);require(bundle.sha256==app['signedAabSha256']and digest(bundle.data)==app['signedAabSha256']and len(bundle.data)==app['signedAabBytes'],'Unknown binary cannot inherit frozen original provenance')
    entries=manifest.get('sourceEvidence');expected={r['role']:r for r in app['sourceProofs']};require(isinstance(entries,dict)and set(entries)==set(expected),'Missing/extra source evidence or invented CI topology')
    media={}
    for role,pin in expected.items():
        m=checked_entry(files,entries[role]);require(m.path==pin['path']and m.sha256==pin['sha256']and len(m.data)==pin['bytes'],'Original source proof bytes differ from known registry');media[role]=m
    aab=zip_files(bundle.data)
    import re
    payload={name:digest(data)for name,data in aab.items()if not re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)',name,re.I)}
    require(digest(canonical(payload).encode())==app['fullSignedPayloadSha256'],'Complete signed module payload differs from reviewed known binary')
    for row in app['requiredBundleAssets']:require(row['entry']in aab and digest(aab[row['entry']])==row['sha256'],'Required serialized font/original notice packaged bytes differ')
    for font in app['fontProofs']:
        original=media[font['originalFontSourceRole']].data;require(digest(original)==font['originalTtfSha256'],'Original committed TTF proof changed')
        resource=aab[font['entry']];require(digest(resource)==font['entrySha256'],'Serialized/converted font resource changed')
        if app['engine']=='Unity':
            require(font['encoding']=='unity_serialized_contains_complete_original_ttf'and original in resource,'Full original TTF bytes missing from Unity serialized font asset')
        else:
            require(font['encoding']=='godot_converted_resource_equal_prior_actual_engine_FontFile_data_inspection'and resource==media[font['engineInspectedResourceRole']].data,'Godot converted resource differs from actual previously inspected resource')
            report=strict_json(media['prior-engine-original-font-inspection'].data);rows=[r for r in report if r.get('resource')==font['engineInspectionResource']]
            require(len(rows)==1 and rows[0].get('pass')is True and rows[0].get('embeddedOriginalTtfSha256')==digest(original)and rows[0].get('originalBytes')==len(original),'Prior actual Engine FontFile.data proof does not bind this original font')
    return list(media.values())


def verify_final_reviews(files,manifest,app,bundle,qa,native,now):
    from candidate import checked_entry,recent_timestamp
    review=checked_entry(files,manifest['rootReview']);rights=checked_entry(files,manifest['rightsEvidence'])
    require(review.path.startswith('qa/')and rights.path.startswith('qa/')and len(review.data)<=512*1024 and len(rights.data)<=512*1024 and review.sha256==app['rootReviewSha256']and rights.sha256==app['rightsEvidenceSha256'],'Final root/right review does not match catalog pin')
    r=strict_json(review.data);a=strict_json(rights.data)
    expected={'schema':1,'reviewer':'root','outcome':'approved_candidate_inputs','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'versionCode':app['newVersionCode'],'versionName':app['newVersionName'],'signedAabSha256':bundle.sha256,'testedApkSha256':qa['testedApkSha256'],'nativeQaSha256':native.sha256,'screenshots':manifest['screenshots'],'rootVisuallyReviewedAllEight':True,'rightsEvidenceSha256':rights.sha256}
    require(isinstance(r,dict)and all(r.get(k)==v and type(r.get(k))is type(v)for k,v in expected.items()),'Final root candidate/native/eight-frame review remains pending or mismatched');recent_timestamp(r.get('testedAtUtc'),now,'root review')
    expected_rights={'schema':1,'reviewer':'root','outcome':'cleared_for_distribution','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'requiredBundleAssets':app['requiredBundleAssets'],'signedAabSha256':app['signedAabSha256'],'fullSignedPayloadSha256':app['fullSignedPayloadSha256']}
    require(isinstance(a,dict)and all(a.get(k)==v and type(a.get(k))is type(v)for k,v in expected_rights.items())and isinstance(a.get('proof'),list)and 1<=len(a['proof'])<=16,'Asset rights not actually cleared for this exact packaged inventory')
    proof=[checked_entry(files,entry)for entry in a['proof']]
    require(all(m.path.startswith('qa/')and m.path not in (review.path,rights.path)for m in proof),'Invalid raw rights evidence path')
    qa_proofs={entry['path']for entry in qa['proof']};require(all(m.path in qa_proofs for m in proof),'Raw rights proofs must also be hashlisted native proof inputs')
    # Retain the actual tested derived APK and direct installed hash output, not only asserted digest strings.
    from game_payload import verify_derived_payload
    from payload_binding import parse_installed_hash_proof
    apk_proof=strict_json(checked_entry(files,qa['apkProof']).data)
    apk=checked_entry(files,apk_proof.get('actualDerivedApkFile'));installed=checked_entry(files,apk_proof.get('actualInstalledHashRawProof'))
    require(apk.sha256==app['testedDerivedApkSha256']==qa['testedApkSha256']and apk.path in qa_proofs and installed.path in qa_proofs,'Actual derived/installed APK raw evidence missing or mismatched')
    verify_derived_payload(bundle.data,apk.data,app);parse_installed_hash_proof(installed.data,app['package'],apk.sha256)
    return review,rights
