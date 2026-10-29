"""Closed twelve-app policy. Final evidence never follows from source readiness."""
from pathlib import Path
from candidate import EXPECTED, require, digest, strict_json, is_digest, safe_name, listing_locales
SOURCE_SHA = 'c82262e3e5906c7e742304b095a80aa4542433b80cb89daf9bbc1e731d52b441'
PROVIDER_SHA = '5b671173dcc7dfadd82fdd2f857176da57b7a418cabfbb1dd75de43b5a3286a5'
ROOT=Path(__file__).resolve().parent

def fixed_apps():
    raw=(ROOT/'business-source-manifest.json').read_bytes();require(digest(raw)==SOURCE_SHA,'Business source manifest SHA mismatch')
    old=(ROOT/'provider-previous-state.json').read_bytes();require(digest(old)==PROVIDER_SHA,'Prior provider snapshot SHA mismatch')
    manifest=strict_json(raw);provider=strict_json(old);require(provider.get('ok') is True,'Prior provider inspection not successful')
    result={}
    for p in manifest['products']:
        package=p['package'];require(package not in result,'Duplicate business identity')
        rows=[r for r in provider['apps'] if r.get('package')==package];require(len(rows)==1,'Prior provider identity missing')
        row=rows[0];release=row['productionTrack']['releases'];require(row.get('status')=='ok' and row.get('cleanup',{}).get('confirmed') is True and len(release)==1 and release[0].get('status')=='completed' and len(release[0]['versionCodes'])==1,'Prior production identity ambiguous')
        source=p['stages']['source'];sign=p['stages'].get('sign')
        require((p['route']=='managed_eas' and p['app']=='NavoKids' and sign is None) or (p['route']=='central_kms' and sign is not None),'Unsupported source family')
        require(type(p['previousProviderMax'])is int and type(p['versionCode'])is int and p['versionCode']==p['previousProviderMax']+1 and row['maxCodeIncludingTracks']==p['previousProviderMax'],'Business fixed max/version mismatch')
        result[package]={'app':p['app'],'package':package,'repository':p['repository'],'reviewedSourceCommit':p['reviewedCommit'],'reviewedGitTree':p['reviewedGitTree'],'reviewedProductDigest':p['reviewedProductDigest'],'route':p['route'],'certificate':p['expectedCertificate'],'previousProductionCode':int(release[0]['versionCodes'][0]),'previousMaxCode':p['previousProviderMax'],'newVersionCode':p['versionCode'],'newVersionName':p['versionName'],'sourceWorkflow':source['workflow'],'sourceWorkflowSha256':source['workflowSha256'],'sourceArtifactName':source['artifactName'],'sourceAabEntry':source['aabEntry'],'signWorkflow':sign['workflow']if sign else None,'signWorkflowSha256':sign['workflowSha256']if sign else None,'signedArtifactName':sign['artifactName']if sign else source['artifactName'],'signedAabEntry':sign['aabEntry']if sign else source['aabEntry']}
    require(len(result)==12,'Exactly twelve business identities required');return result

def scope(family='calculator9'):
    if family=='calculator9':return EXPECTED
    require(family=='business12','Unknown closed submission family')
    return {k:(v['previousMaxCode'],v['newVersionCode'])for k,v in fixed_apps().items()}

def version(package,family='calculator9'):
    require(package in scope(family),'Package outside fixed family')
    return '1.2.0'if family=='calculator9'else fixed_apps()[package]['newVersionName']

def assert_identity(app):
    require(isinstance(app,dict),'Business catalog row must be an object')
    fixed=fixed_apps();require(app.get('package')in fixed,'Excluded business identity')
    require(all(app.get(k)==v and type(app.get(k))is type(v)for k,v in fixed[app['package']].items()),'Business immutable identity mismatch')

def load_catalog(path,expected_sha):
    raw=Path(path).read_bytes();require(is_digest(expected_sha)and digest(raw)==expected_sha,'Business catalog SHA mismatch')
    d=strict_json(raw);require(isinstance(d,dict)and type(d.get('schema'))is int and d['schema']==1 and d.get('family')=='business12'and d.get('sourceManifestSha256')==SOURCE_SHA and d.get('previousProviderSnapshotSha256')==PROVIDER_SHA and d.get('localePolicy')=={'families':['de','en'],'maximumSelected':2},'Business catalog shape mismatch')
    require(set(d)=={'schema','family','sourceManifestSha256','previousProviderSnapshotSha256','localePolicy','apps'},'Unexpected Business catalog fields')
    require(isinstance(d.get('apps'),list)and len(d['apps'])==12,'Exactly twelve business catalog rows required')
    result={}
    for app in d['apps']:
        assert_identity(app)
        fields=set(fixed_apps()[app['package']])|{'listingLocales','localeSnapshotSha256','releaseNotes','requiredBundleAssets','optionalOriginalIcon','rootReviewSha256','rightsEvidenceSha256','readiness','frameLanguageRequirements'}
        require(set(app)==fields,'Unexpected or missing Business catalog row fields')
        require(app.get('readiness')in('pending_final_native_screens_locales_asset_rights_root_review','root_reviewed_candidate_inputs'),'Unknown Business readiness declaration')
        require(isinstance(app.get('releaseNotes'),dict),'Release notes must be an object')
        if app.get('listingLocales')is None:require(app.get('localeSnapshotSha256')is None and app['releaseNotes']=={},'Pending locale catalog cannot invent release-note locale IDs')
        else:listing_locales(app)
        require(all(app.get(k)is None or is_digest(app.get(k))for k in ('rootReviewSha256','rightsEvidenceSha256')),'Invalid final review digest')
        require(app['package']not in result,'Duplicate business catalog identity')
        assets=app.get('requiredBundleAssets');require(isinstance(assets,list),'Raw asset inventory must be a list')
        seen=set()
        for asset in assets:
            require(isinstance(asset,dict)and set(asset)=={'entry','sha256'},'Invalid raw asset binding');safe_name(asset['entry']);require(asset['entry'].startswith('base/')and asset['entry']not in seen and is_digest(asset['sha256']),'Invalid/duplicate raw asset binding');seen.add(asset['entry'])
        language_requirements(app,allow_pending=True)
        result[app['package']]=app
    require(set(result)==set(scope('business12')),'Business scope mismatch');return result

def require_ready(app):
    assert_identity(app);require(app.get('readiness')=='root_reviewed_candidate_inputs','Final Business candidate readiness remains pending');locales=listing_locales(app)
    require(len(locales)==2 and {l.split('-')[0]for l in locales}=={'de','en'},'Existing German and English locale inventories required')
    require(is_digest(app.get('rootReviewSha256'))and is_digest(app.get('rightsEvidenceSha256')),'Final root/native/asset rights review remains pending')
    require(isinstance(app.get('releaseNotes'),dict)and all(isinstance(v,str)and 1<=len(v)<=500 for v in app['releaseNotes'].values()),'Fixed factual release notes required')
    language_requirements(app)
    assets=app.get('requiredBundleAssets');require(isinstance(assets,list)and len(assets)>=2,'Packaged raw font/license asset inventory pending')
    require(any(a.get('entry','').lower().endswith(('.ttf','.otf'))for a in assets)and any(a.get('entry','').lower().endswith(('ofl.txt','license.txt','notice.txt'))for a in assets),'Original font and packaged license/notice bytes required')
    return locales


def verify_business_provenance(app,manifest,proof,bundle_sha,files):
    assert_identity(app);require(isinstance(proof,dict),'Business provenance must be an object')
    source=manifest['source'];sign=manifest.get('signing')
    if app['route']=='central_kms':
        require(isinstance(sign,dict),'Original central signing stage required')
        expected={'GITHUB_REPOSITORY':app['repository'],'GITHUB_SHA':app['reviewedSourceCommit'],'GITHUB_RUN_ID':str(sign['runId']),'PACKAGE_NAME':app['package'],'VERSION_CODE':str(app['newVersionCode']),'VERSION_NAME':app['newVersionName'],'CENTRAL_SHA1':app['certificate']['sha1'],'CENTRAL_SHA256':app['certificate']['sha256'],'SOURCE_RUN_ID':str(source['runId']),'SOURCE_COMMIT':app['reviewedSourceCommit'],'SOURCE_ARTIFACT_ID':str(source['artifactId']),'SOURCE_ARTIFACT_DIGEST':'sha256:'+source['artifactArchiveSha256']}
        require(all(proof.get(k)==v and type(proof.get(k))is type(v)for k,v in expected.items())and proof.get('VERSION_OVERRIDE')in(None,''),'Signed CI original business provenance mismatch')
    else:
        import re
        require(sign is None,'Managed EAS has no fabricated central signer')
        expected={'repository':app['repository'],'sourceCommit':app['reviewedSourceCommit'],'workflowCommit':app['reviewedSourceCommit'],'workflowRun':str(source['runId']),'version':app['newVersionName'],'versionCode':app['newVersionCode'],'package':app['package'],'easStatus':'FINISHED','managedCredentials':True,'credentialsFrozen':True,'storeSubmission':False,'recoveredFinishedBuild':False,'aabSHA256':bundle_sha,'easConfigOverrideOnly':{'appVersionSource':'local','profile':'portfolioAndroid','autoIncrement':False}}
        require(all(proof.get(k)==v and type(proof.get(k))is type(v)for k,v in expected.items()),'Managed EAS original provenance mismatch')
        override=proof['easConfigOverrideOnly'];require(type(override.get('autoIncrement'))is bool and re.fullmatch(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}',proof.get('easBuildID',''))is not None,'Managed EAS exact build identity required')

    from candidate import zip_files,checked_entry,parse_certificate
    import re
    signed=manifest['signing']if sign is not None else source
    archive=checked_entry(files,{'path':signed['archive'],'sha256':signed['artifactArchiveSha256']});signed_files=zip_files(archive.data)
    require([n for n in signed_files if n.endswith('.aab')]==[app['signedAabEntry']] and digest(signed_files[app['signedAabEntry']])==bundle_sha,'Exact original signed AAB path/bytes required')
    require('upload-certificate.txt'in signed_files,'Original public upload certificate evidence missing')
    try:sha1,sha256=parse_certificate(signed_files['upload-certificate.txt'].decode('utf-8'))
    except UnicodeError:require(False,'Invalid retained public certificate evidence')
    require(sha1==app['certificate']['sha1']and sha256==app['certificate']['sha256'],'Original public certificate differs from this app')
    if app['route']=='managed_eas':return []
    original=checked_entry(files,{'path':source['archive'],'sha256':source['artifactArchiveSha256']});source_files=zip_files(original.data)
    require([n for n in source_files if n.endswith('.aab')]==[app['sourceAabEntry']],'Exact original unsigned source AAB required')
    from business_binary import binary_files
    unsigned=binary_files(source_files[app['sourceAabEntry']]);signed_aab=binary_files(signed_files[app['signedAabEntry']])
    signature=re.compile(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)$',re.I)
    require(not any(re.fullmatch(r'META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)',n,re.I)for n in unsigned),'Original central source unexpectedly signed')
    payload=lambda entries:{n:digest(data)for n,data in entries.items()if not signature.fullmatch(n)}
    require(payload(unsigned)==payload(signed_aab),'Central signing changed original source payload')
    require('payload.json'in signed_files and strict_json(signed_files['payload.json'])==payload(signed_aab),'Original signed artifact payload map differs')
    return [original]


def verify_final_reviews(files,manifest,app,bundle,qa,native,now):
    from candidate import checked_entry,recent_timestamp
    review=checked_entry(files,manifest['rootReview']);rights=checked_entry(files,manifest['rightsEvidence'])
    require(review.path.startswith('qa/')and rights.path.startswith('qa/')and len(review.data)<=512*1024 and len(rights.data)<=512*1024 and review.sha256==app['rootReviewSha256']and rights.sha256==app['rightsEvidenceSha256'],'Final root/right review does not match catalog pin')
    r=strict_json(review.data);a=strict_json(rights.data)
    expected={'schema':1,'reviewer':'root','outcome':'approved_candidate_inputs','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'versionCode':app['newVersionCode'],'versionName':app['newVersionName'],'signedAabSha256':bundle.sha256,'testedApkSha256':qa['testedApkSha256'],'nativeQaSha256':native.sha256,'screenshots':manifest['screenshots'],'rootVisuallyReviewedAllEight':True,'rightsEvidenceSha256':rights.sha256}
    require(isinstance(r,dict)and all(r.get(k)==v and type(r.get(k))is type(v)for k,v in expected.items()),'Final root candidate/native/eight-frame review remains pending or mismatched');recent_timestamp(r.get('testedAtUtc'),now,'root review')
    expected_rights={'schema':1,'reviewer':'root','outcome':'cleared_for_distribution','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'requiredBundleAssets':app['requiredBundleAssets']}
    require(isinstance(a,dict)and all(a.get(k)==v and type(a.get(k))is type(v)for k,v in expected_rights.items())and isinstance(a.get('proof'),list)and 1<=len(a['proof'])<=16,'Asset rights not actually cleared for this exact packaged inventory')
    proof=[checked_entry(files,entry)for entry in a['proof']]
    require(all(m.path.startswith('qa/')and m.path not in (review.path,rights.path)for m in proof),'Invalid raw rights evidence path')
    qa_proofs={entry['path']for entry in qa['proof']};require(all(m.path in qa_proofs for m in proof),'Raw rights proofs must also be hashlisted native proof inputs')
    # Retain the actual tested derived APK and direct installed hash output, not only asserted digest strings.
    from payload_binding import verify_derived_payload,parse_installed_hash_proof
    apk_proof=strict_json(checked_entry(files,qa['apkProof']).data)
    apk=checked_entry(files,apk_proof.get('actualDerivedApkFile'));installed=checked_entry(files,apk_proof.get('actualInstalledHashRawProof'))
    require(apk.sha256==qa['testedApkSha256']and apk.path in qa_proofs and installed.path in qa_proofs,'Actual derived/installed APK raw evidence missing or mismatched')
    verify_derived_payload(bundle.data,apk.data);parse_installed_hash_proof(installed.data,app['package'],apk.sha256)
    return review,rights


def language_requirements(app,allow_pending=False):
    """Store listing locale and actual visible UI language are independent facts."""
    requirements=app.get('frameLanguageRequirements')
    if allow_pending and requirements is None:return None
    locales=listing_locales(app)
    require(isinstance(requirements,dict)and set(requirements)==set(locales),'Actual per-app/per-frame language review remains pending')
    for locale,frames in requirements.items():
        require(isinstance(frames,list)and len(frames)==4,'Exactly four reviewed frame language requirements per listing required')
        for row in frames:
            require(isinstance(row,dict)and set(row)=={'inAppLanguage','mixedUi','languageLimitation'},'Explicit actual visible UI language fields required')
            language=row['inAppLanguage'];mixed=row['mixedUi'];limitation=row['languageLimitation']
            require(language in ('de','en','mixed-de-en')and type(mixed)is bool and mixed is(language=='mixed-de-en')and isinstance(limitation,str)and len(limitation)<=500,'Ambiguous actual UI language or mixed-UI flag')
            require(not(mixed or language!=locale.split('-')[0])or bool(limitation.strip()),'Mixed UI or listing/UI language difference requires a factual limitation')
    return requirements


def validate_frame_language(app,locale,index,entry):
    requirements=language_requirements(app);require(locale in requirements and type(index)is int and 0<=index<4,'Unpinned listing/frame language identity')
    row=requirements[locale][index]
    require(all(entry.get(k)==v and type(entry.get(k))is type(v)for k,v in row.items()),'Actual visible frame language differs from root-pinned per-frame requirements')
