"""Entirely synthetic Business candidate fixtures; never product QA evidence."""
import copy,json
from fixtures import Fixture,Verifier,NOW,PACKAGE,digest,encode,packed
import business_policy

class BusinessFixture(Fixture):
    def __init__(self,package='com.kamilunavo.maengelfix'):
        super().__init__();old=self.app;new=copy.deepcopy(business_policy.fixed_apps()[package]);self.package=package
        def replace(v):
            if isinstance(v,dict):return {k:replace(x)for k,x in v.items()}
            if isinstance(v,list):return [replace(x)for x in v]
            if v==PACKAGE:return package
            if v==old['reviewedSourceCommit']:return new['reviewedSourceCommit']
            if v=='1.2.0':return new['newVersionName']
            return v
        self.files={k:encode(replace(json.loads(v)))if k.endswith('.json')else v for k,v in self.files.items()}
        self.manifest=replace(self.manifest);self.qa=replace(self.qa)
        self.manifest['versionCode']=new['newVersionCode'];self.qa['versionCode']=new['newVersionCode']
        d=json.loads(self.files['qa/derived-apk-proof.json']);d['versionCode']=new['newVersionCode'];self.files['qa/derived-apk-proof.json']=encode(d);self.qa['apkProof']=self.entry('qa/derived-apk-proof.json')
        new['readiness']='root_reviewed_candidate_inputs'
        new.update({k:copy.deepcopy(old[k])for k in ['releaseNotes','requiredBundleAssets','listingLocales','localeSnapshotSha256']})
        new['requiredBundleAssets']=[{'entry':'base/assets/font.ttf','sha256':digest(b'unit-font-not-real')},{'entry':'base/assets/OFL.txt','sha256':digest(b'unit-license-not-real')}]
        self.aab=packed({'base/manifest/AndroidManifest.xml':b'unit manifest','base/assets/font.ttf':b'unit-font-not-real','base/assets/OFL.txt':b'unit-license-not-real','META-INF/UPLOAD.SF':b'unit','META-INF/UPLOAD.RSA':b'unit'})
        self.files['bundle/app.aab']=self.aab;self.manifest['bundle']=self.entry('bundle/app.aab');self.qa['signedAabSha256']=digest(self.aab)
        d=json.loads(self.files['qa/derived-apk-proof.json']);d['sourceAabSha256']=digest(self.aab);self.files['qa/derived-apk-proof.json']=encode(d);self.qa['apkProof']=self.entry('qa/derived-apk-proof.json')
        new['localeSnapshotSha256']=digest(self.files['qa/locale-inventory.json']);self.manifest['localeInventory']=self.entry('qa/locale-inventory.json')
        self.app=new;self.catalog={package:new}
        self.manifest['source'].update(repository=new['repository'],commit=new['reviewedSourceCommit'],workflow=new['sourceWorkflow'])
        if new['route']=='central_kms':
            self.manifest['source']['archive']='provenance/unsigned-ci-artifact.zip'
            self.manifest['signing'].update(repository=new['repository'],commit=new['reviewedSourceCommit'],workflow=new['signWorkflow'])
            self.provenance={'GITHUB_REPOSITORY':new['repository'],'GITHUB_SHA':new['reviewedSourceCommit'],'GITHUB_RUN_ID':'43','PACKAGE_NAME':package,'VERSION_CODE':str(new['newVersionCode']),'VERSION_NAME':new['newVersionName'],'CENTRAL_SHA1':new['certificate']['sha1'],'CENTRAL_SHA256':new['certificate']['sha256'],'SOURCE_RUN_ID':'42','SOURCE_COMMIT':new['reviewedSourceCommit'],'SOURCE_ARTIFACT_ID':'52','SOURCE_ARTIFACT_DIGEST':'sha256:'+'a'*64,'VERSION_OVERRIDE':None}
        else:
            del self.manifest['signing'];self.manifest['source']['archive']='provenance/signed-ci-artifact.zip'
            self.provenance={'repository':new['repository'],'sourceCommit':new['reviewedSourceCommit'],'workflowCommit':new['reviewedSourceCommit'],'workflowRun':'42','version':new['newVersionName'],'versionCode':new['newVersionCode'],'package':package,'easStatus':'FINISHED','managedCredentials':True,'credentialsFrozen':True,'storeSubmission':False,'recoveredFinishedBuild':False,'aabSHA256':digest(self.aab),'easBuildID':'12345678-1234-1234-1234-123456789abc','easConfigOverrideOnly':{'appVersionSource':'local','profile':'portfolioAndroid','autoIncrement':False}}
        # Synthetic fixtures explicitly declare German UI for both listing locales; never infer EN from en-US.
        new['frameLanguageRequirements']={locale:[{'inAppLanguage':'de','mixedUi':False,'languageLimitation':'' if locale.startswith('de') else 'English store listing; synthetic visible UI declaration is German.'}for _ in range(4)]for locale in ['de-DE','en-US']}
        for locale,frames in self.manifest['screenshots'].items():
            for index,entry in enumerate(frames):entry.update(new['frameLanguageRequirements'][locale][index])
        self.qa['screenshots']=copy.deepcopy(self.manifest['screenshots']);self.qa.pop('captureLanguages',None);self.qa['listingLocales']=['de-DE','en-US']
        self.rights={'schema':1,'reviewer':'root','outcome':'cleared_for_distribution','package':package,'sourceCommit':new['reviewedSourceCommit'],'requiredBundleAssets':new['requiredBundleAssets'],'proof':[self.entry('qa/proof.json')],'syntheticFixtureOnly':True}
        self.apk=packed({'AndroidManifest.xml':b'unit derived manifest','assets/font.ttf':b'unit-font-not-real','assets/OFL.txt':b'unit-license-not-real'})
        self.files['qa/tested.apk']=self.apk;self.files['qa/installed-hash.txt']=(digest(self.apk)+'  /data/app/unit/'+package+'-unit/base.apk\n').encode()
        self.qa['testedApkSha256']=digest(self.apk)
        apk_proof=json.loads(self.files['qa/derived-apk-proof.json']);apk_proof.update(apkSha256=digest(self.apk),actualDerivedApkFile=self.entry('qa/tested.apk'),actualInstalledHashRawProof=self.entry('qa/installed-hash.txt'))
        self.files['qa/derived-apk-proof.json']=encode(apk_proof);self.qa['apkProof']=self.entry('qa/derived-apk-proof.json');self.qa['proof'] += [self.entry('qa/tested.apk'),self.entry('qa/installed-hash.txt')]
        self.review={'schema':1,'reviewer':'root','outcome':'approved_candidate_inputs','package':package,'sourceCommit':new['reviewedSourceCommit'],'versionCode':new['newVersionCode'],'versionName':new['newVersionName'],'signedAabSha256':digest(self.aab),'testedApkSha256':self.qa['testedApkSha256'],'screenshots':self.manifest['screenshots'],'rootVisuallyReviewedAllEight':True,'testedAtUtc':NOW.isoformat(),'syntheticFixtureOnly':True}
    def raw(self):
        from candidate import zip_files
        import re
        signature=re.compile(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)$',re.I)
        payload={p:data for p,data in zip_files(self.aab).items()if not signature.fullmatch(p)}
        if self.app['route']=='central_kms':
            self.files[self.manifest['source']['archive']]=packed({self.app['sourceAabEntry']:packed(payload)})
            source_sha=digest(self.files[self.manifest['source']['archive']]);self.manifest['source']['artifactArchiveSha256']=source_sha
            if self.provenance.get('SOURCE_ARTIFACT_DIGEST')=='sha256:'+'a'*64:self.provenance['SOURCE_ARTIFACT_DIGEST']='sha256:'+source_sha
        self.signed_files={'app-release.aab':self.aab,'provenance.json':encode(self.provenance),'payload.json':encode({p:digest(data)for p,data in payload.items()}),'upload-certificate.txt':('SHA1: '+self.app['certificate']['sha1']+'\nSHA256: '+self.app['certificate']['sha256']+'\n').encode()}
        if hasattr(self,'signed_overrides'):self.signed_files.update(self.signed_overrides)
        if hasattr(self,'source_override'):
            self.files[self.manifest['source']['archive']]=self.source_override;self.manifest['source']['artifactArchiveSha256']=digest(self.source_override);self.provenance['SOURCE_ARTIFACT_DIGEST']='sha256:'+digest(self.source_override);self.signed_files['provenance.json']=encode(self.provenance)
        section=self.manifest['signing']if 'signing'in self.manifest else self.manifest['source']
        self.files[section['archive']]=packed(self.signed_files);section['artifactArchiveSha256']=digest(self.files[section['archive']])
        self.files['qa/native-qa.json']=encode(self.qa);self.manifest['nativeQa']=self.entry('qa/native-qa.json')
        self.review['nativeQaSha256']=self.manifest['nativeQa']['sha256'];self.review['rightsEvidenceSha256']=digest(encode(self.rights))
        self.files['qa/root-review.json']=encode(self.review);self.files['qa/rights-review.json']=encode(self.rights)
        self.manifest['rootReview']=self.entry('qa/root-review.json');self.manifest['rightsEvidence']=self.entry('qa/rights-review.json')
        self.app['rootReviewSha256']=self.manifest['rootReview']['sha256'];self.app['rightsEvidenceSha256']=self.manifest['rightsEvidence']['sha256']
        self.files['manifest.json']=encode(self.manifest);return packed(self.files)

class BusinessVerifier:
    def __init__(self,**overrides):self.overrides=overrides
    def verify(self,raw,app):
        d=dict(package=app['package'],versionCode=app['newVersionCode'],versionName=app['newVersionName'],sha1=app['certificate']['sha1'],sha256=app['certificate']['sha256'],jarVerified=True);d.update(self.overrides);return d
