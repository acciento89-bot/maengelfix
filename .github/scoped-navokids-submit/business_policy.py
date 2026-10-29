"""The single fixed recovered NavoKids binary; never a generic EAS exception."""
from pathlib import Path
import copy,json
from functools import lru_cache
from candidate import require,digest,strict_json,is_digest,safe_name,listing_locales
ROOT=Path(__file__).resolve().parent
REGISTRY_SHA='4b290c400cd929df24394cce1b1339f329064e1484d1655183f23b6b40c0c0c5'
PACKAGE='com.kamilunavo.navokids'
READY_FIELDS={'listingLocales','localeSnapshotSha256','releaseNotes','optionalOriginalIcon','rootReviewSha256','rightsEvidenceSha256','frameLanguageRequirements','readiness','archiveApproval'}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
@lru_cache(maxsize=1)
def registry():
 raw=(ROOT/'known-navokids.json').read_bytes();require(digest(raw)==REGISTRY_SHA,'Closed NavoKids registry SHA changed');d=strict_json(raw);require(d.get('schema')==1 and d.get('family')=='navokids1'and d['app']['package']==PACKAGE,'Closed registry shape mismatch');return d['app']
def fixed_apps():return {PACKAGE:copy.deepcopy(registry())}
def scope(family='navokids1'):
 require(family=='navokids1','Only closed navokids1 family accepted');return {PACKAGE:(8,9)}
def version(package,family='navokids1'):require(package in scope(family),'Excluded NavoKids identity');return '0.6.0'
def assert_identity(app):
 require(isinstance(app,dict)and app.get('package')==PACKAGE,'Only exact NavoKids identity accepted');fixed=registry();require(set(app)<=set(fixed)|READY_FIELDS,'Unknown NavoKids identity/readiness fields');require(all(k in app and canonical(app[k])==canonical(v)for k,v in fixed.items()),'NavoKids fixed source/binary/certificate/lineage changed')
def load_catalog(path,sha256):
 raw=Path(path).read_bytes();require(is_digest(sha256)and digest(raw)==sha256,'NavoKids catalog SHA mismatch');d=strict_json(raw);require(type(d.get('schema'))is int and d['schema']==1 and set(d)=={'schema','family','knownRegistrySha256','localePolicy','apps'}and d['family']=='navokids1'and d['knownRegistrySha256']==REGISTRY_SHA and d['localePolicy']=={'families':['de','en'],'maximumSelected':2}and isinstance(d['apps'],list)and len(d['apps'])==1,'Exactly one closed catalog identity required');app=d['apps'][0];assert_identity(app);require(set(app)==set(registry())|READY_FIELDS,'Unknown NavoKids catalog fields');require(app['readiness']in('pending_final_native_screens_locales_rights_root_review','root_reviewed_candidate_inputs'),'Unknown readiness')
 if app['listingLocales']is None:require(app['localeSnapshotSha256']is None and app['releaseNotes']=={},'Pending locale inventory cannot invent notes')
 else:listing_locales(app)
 language_requirements(app,allow_pending=True);require(all(app[k]is None or is_digest(app[k])for k in('rootReviewSha256','rightsEvidenceSha256')),'Invalid review pins');return {PACKAGE:app}
def require_ready(app):
 assert_identity(app);require(app['readiness']=='root_reviewed_candidate_inputs','Final NavoKids native/rights/root readiness remains pending');locales=listing_locales(app);require(len(locales)==2 and{l.split('-')[0]for l in locales}=={'de','en'},'Actual existing DE/EN listing inventory required');require(is_digest(app.get('rootReviewSha256'))and is_digest(app.get('rightsEvidenceSha256')),'Exact root input and rights approvals missing');language_requirements(app);archive_approval(app);return locales
def archive_approval(app,sha=None,size=None):
 a=app.get('archiveApproval');require(isinstance(a,dict)and set(a)=={'reviewer','outcome','package','sourceCommit','candidateSha256','candidateBytes','signedAabSha256','testedApkSha256','rootReviewSha256','rightsEvidenceSha256','reviewedAtUtc'},'Exact external whole-archive root approval pending');require(a['reviewer']=='root'and a['outcome']=='approved_exact_navokids_candidate_archive'and a['package']==PACKAGE and a['sourceCommit']==app['reviewedSourceCommit']and a['signedAabSha256']==app['signedAabSha256']and a['testedApkSha256']==app['testedDerivedApkSha256']and a['rootReviewSha256']==app['rootReviewSha256']and a['rightsEvidenceSha256']==app['rightsEvidenceSha256']and is_digest(a['candidateSha256'])and type(a['candidateBytes'])is int and 0<a['candidateBytes']<=1280*1024*1024,'Whole archive approval identity differs')
 from candidate import recent_timestamp
 from datetime import datetime,timezone
 recent_timestamp(a['reviewedAtUtc'],datetime.now(timezone.utc),'whole archive approval')
 require(sha is None or sha==a['candidateSha256'],'Unapproved outer candidate SHA');require(size is None or size==a['candidateBytes'],'Unapproved outer candidate size');return a

def language_requirements(app,allow_pending=False):
 requirements=app.get('frameLanguageRequirements')
 if allow_pending and requirements is None:return None
 locales=listing_locales(app);require(isinstance(requirements,dict)and set(requirements)==set(locales),'Actual per-frame language review pending')
 for locale,frames in requirements.items():
  require(isinstance(frames,list)and len(frames)==4,'Four root-reviewed frames per selected listing required')
  for r in frames:
   require(isinstance(r,dict)and set(r)=={'inAppLanguage','mixedUi','languageLimitation'}and r['inAppLanguage']in('de','en','mixed-de-en')and type(r['mixedUi'])is bool and r['mixedUi']is(r['inAppLanguage']=='mixed-de-en')and isinstance(r['languageLimitation'],str)and len(r['languageLimitation'])<=500,'Explicit actual visible frame language required');require(not(r['mixedUi']or r['inAppLanguage']!=locale.split('-')[0])or bool(r['languageLimitation'].strip()),'Actual mixed/listing-language difference needs factual limitation')
 return requirements
def validate_frame_language(app,locale,index,entry):
 r=language_requirements(app);require(locale in r and type(index)is int and 0<=index<4 and all(canonical(entry.get(k))==canonical(v)for k,v in r[locale][index].items()),'Actual visible frame language differs from root pin')

def verify_source_evidence(app,manifest,files):
 from candidate import checked_entry
 expected={r['role']:r for r in registry()['sourceProofs']};entries=manifest.get('sourceEvidence');require(isinstance(entries,dict)and set(entries)==set(expected),'Exact original failed/EAS/recovery evidence required');media={}
 for role,pin in expected.items():
  m=checked_entry(files,entries[role]);require(m.path==pin['path']and m.sha256==pin['sha256']and len(m.data)==pin['bytes'],'Original immutable EAS lineage proof differs');media[role]=m
 original=strict_json(media['original-failed-run'].data);recovered=strict_json(media['recovery-success-run'].data)
 for value,id,conclusion in [(original,40912063730,'failure'),(recovered,40926938191,'success')]:
  require(value.get('id')==id and value.get('head_sha')==app['reviewedSourceCommit']and value.get('head_branch')=='main'and value.get('event')=='workflow_dispatch'and value.get('path')==app['sourceWorkflow']and value.get('run_attempt')==1 and value.get('status')=='completed'and value.get('conclusion')==conclusion and value.get('repository',{}).get('full_name')==app['repository']and value.get('head_repository',{}).get('full_name')==app['repository'],'Original failure/recovery success lineage falsely relabelled')
 approval=strict_json(media['root-recovery-approval'].data);require(media['root-recovery-approval'].sha256==app['rootRecoveryApprovalSha256']and approval.get('reviewer')=='root'and approval.get('outcome')=='approved_exact_existing_eas_recovery'and approval.get('originalFailedRunId')==40912063730 and approval.get('easBuildID')==app['easBuildID']and approval.get('aabSHA256')==app['signedAabSha256']and approval.get('sourceCommit')==app['reviewedSourceCommit']and approval.get('certificate')==app['certificate'],'Root approval does not authorize exact original EAS recovery')
 eas=strict_json(media['original-eas-finished-view'].data)['build'];require(eas.get('id')==app['easBuildID']and eas.get('status')=='FINISHED'and eas.get('gitCommitHash')==app['reviewedSourceCommit']and eas.get('appVersion')=='0.6.0'and eas.get('appBuildVersion')=='9'and eas.get('platform')=='ANDROID'and eas.get('buildProfile')=='portfolioAndroid'and eas.get('distribution')=='STORE','Original finished EAS identity differs')
 linkage=media['original-job-uuid-linkage'].data;require(app['easBuildID'].encode()in linkage and b'40912063730'in linkage,'Original failed job UUID link missing')
 request=strict_json(media['recovery-request'].data);require(request.get('runId')==40926938191 and request.get('originalSourceRun')==40912063730 and request.get('approvalSha256')==app['rootRecoveryApprovalSha256']and request.get('head')==app['reviewedSourceCommit']and request.get('easBuildID')==app['easBuildID']and request.get('inputs')=={'mode':'signed','recover_eas_build_id':app['easBuildID']},'Actual existing-build recovery request differs')
 return list(media.values())

def verify_business_provenance(app,manifest,proof,bundle_sha,files):
 from candidate import zip_files,checked_entry,parse_certificate
 assert_identity(app);source=manifest['source'];require('signing'not in manifest and source['runId']==40926938191 and source['artifactId']==12921086708 and source['artifactArchiveSha256']==app['originalCiArchiveSha256']and source['archive']=='provenance/recovered-ci-artifact.zip','Only exact recovered managed CI source is accepted')
 expected={'repository':app['repository'],'sourceCommit':app['reviewedSourceCommit'],'workflowCommit':app['reviewedSourceCommit'],'recoveredFinishedBuild':True,'workflowRun':'40926938191','easBuildID':app['easBuildID'],'easStatus':'FINISHED','version':'0.6.0','versionCode':9,'package':PACKAGE,'managedCredentials':True,'credentialsFrozen':True,'storeSubmission':False,'easConfigOverrideOnly':{'appVersionSource':'local','profile':'portfolioAndroid','autoIncrement':False},'aabSHA256':app['signedAabSha256']}
 require(isinstance(proof,dict)and set(proof)==set(expected)and all(proof[k]==v and type(proof[k])is type(v)for k,v in expected.items())and proof['easConfigOverrideOnly']['autoIncrement']is False and bundle_sha==app['signedAabSha256'],'Recovered provenance does not match the single frozen lineage')
 original=checked_entry(files,{'path':source['archive'],'sha256':source['artifactArchiveSha256']});ci=zip_files(original.data);require(ci['app-release.aab']==files[manifest['bundle']['path']],'Recovered original AAB differs');a,b=parse_certificate(ci['upload-certificate.txt'].decode('utf-8'));require(a==app['certificate']['sha1']and b==app['certificate']['sha256'],'Wrong original managed upload certificate');return verify_source_evidence(app,manifest,files)


def verify_final_reviews(files,manifest,app,bundle,qa,native,now):
    from candidate import checked_entry,recent_timestamp
    review=checked_entry(files,manifest['rootReview']);rights=checked_entry(files,manifest['rightsEvidence'])
    require(review.path.startswith('qa/')and rights.path.startswith('qa/')and len(review.data)<=512*1024 and len(rights.data)<=512*1024 and review.sha256==app['rootReviewSha256']and rights.sha256==app['rightsEvidenceSha256'],'Final root/right review does not match catalog pin')
    r=strict_json(review.data);a=strict_json(rights.data)
    expected={'schema':1,'reviewer':'root','outcome':'approved_candidate_inputs','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'versionCode':app['newVersionCode'],'versionName':app['newVersionName'],'signedAabSha256':bundle.sha256,'testedApkSha256':qa['testedApkSha256'],'nativeQaSha256':native.sha256,'screenshots':manifest['screenshots'],'rootVisuallyReviewedAllEight':True,'rightsEvidenceSha256':rights.sha256}
    require(isinstance(r,dict)and all(r.get(k)==v and type(r.get(k))is type(v)for k,v in expected.items()),'Final root candidate/native/eight-frame review remains pending or mismatched');recent_timestamp(r.get('testedAtUtc'),now,'root review')
    require(qa.get('testedApkSha256')==app['testedDerivedApkSha256'],'Only exact current derived APK accepted')
    expected_rights={'schema':1,'reviewer':'root','outcome':'cleared_for_distribution','package':app['package'],'sourceCommit':app['reviewedSourceCommit'],'requiredBundleAssets':app['requiredBundleAssets']}
    require(isinstance(a,dict)and all(a.get(k)==v and type(a.get(k))is type(v)for k,v in expected_rights.items())and isinstance(a.get('proof'),list)and 1<=len(a['proof'])<=16,'Asset rights not actually cleared for this exact packaged inventory')
    require(a.get('signedAabSha256')==app['signedAabSha256']and a.get('ownerImageConfirmationSha256')==app['ownerImageConfirmationSha256']and a.get('all8642VoiceDistributionReviewed')is True,'Complete exact voice/image distribution review remains pending')
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

