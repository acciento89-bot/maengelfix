"""Bounded synthetic fixture and scoped test-only registry authority; no external binaries or product QA."""
import copy,json,re
from unittest.mock import patch
from pathlib import Path
from fixtures import HERE,NOW,encode,packed,png,digest
import candidate,game_policy

def ready_app(package='com.kamilunavo.runenpfad'):
    a=copy.deepcopy(game_policy.fixed_apps()[package]);a.update(listingLocales=['de-DE','en-US'],localeSnapshotSha256='a'*64,releaseNotes={'de-DE':'Synthetischer Test','en-US':'Synthetic unit fixture'},rootReviewSha256='b'*64,rightsEvidenceSha256='c'*64,optionalOriginalIcon=None,readiness='root_reviewed_candidate_inputs')
    a['frameLanguageRequirements']={l:[{'inAppLanguage':'de','mixedUi':False,'languageLimitation':''if l=='de-DE'else'English listing with actual German UI declaration.','screenScope':'other'}for _ in range(4)]for l in a['listingLocales']};return a

class GameFixture:
    def __init__(self,testcase):
        # Only this unit test receives a synthetic registry; production pins/functions are never changed.
        original=json.loads((HERE/'known-games.json').read_bytes());apps={a['package']:copy.deepcopy(a)for a in original['apps']};row=apps['com.kamilunavo.runenpfad'];self.package=row['package']
        self.files={p['path']:(HERE/p['path']).read_bytes()for p in row['sourceProofs']};by_role={p['role']:self.files[p['path']]for p in row['sourceProofs']}
        aab_files={'base/manifest/AndroidManifest.xml':b'unit-only-manifest','base/dex/classes.dex':b'unit-only-dex'}
        for font in row['fontProofs']:
            data=b'UNIT-SERIALIZED-FONT\0'+by_role[font['originalFontSourceRole']];aab_files[font['entry']]=data;font['entrySha256']=digest(data)
            next(a for a in row['requiredBundleAssets']if a['entry']==font['entry'])['sha256']=digest(data)
        for asset in row['requiredBundleAssets']:
            if asset['entry']not in aab_files:aab_files[asset['entry']]=next(self.files[p['path']]for p in row['sourceProofs']if p['sha256']==asset['sha256'])
        payload={name:digest(raw)for name,raw in aab_files.items()};row['fullSignedPayloadSha256']=digest(encode(payload))
        aab_files.update({'META-INF/UPLOAD.SF':b'unit signature marker','META-INF/UPLOAD.RSA':b'unit certificate marker'});self.aab=packed(aab_files)
        apk_files={name[len('base/dex/'):]:raw for name,raw in aab_files.items()if name.startswith('base/dex/')}
        apk_files.update({name[len('base/'):]:raw for name,raw in aab_files.items()if name.startswith(('base/assets/','base/lib/'))});apk_files['AndroidManifest.xml']=b'unit-only-derived-manifest'
        baseline={name:('unit-baseline-'+name).encode()for name in row['allowedGeneratedBaselineExtras']};apk_files.update(baseline);row['allowedGeneratedBaselineExtras']={name:digest(raw)for name,raw in baseline.items()};self.apk=packed(apk_files)
        row.update(signedAabSha256=digest(self.aab),signedAabBytes=len(self.aab),testedDerivedApkSha256=digest(self.apk),testedDerivedApkBytes=len(self.apk))
        authority=patch.object(game_policy,'fixed_apps',return_value=apps);authority.start();testcase.addCleanup(authority.stop)
        self.app=ready_app();self.catalog={self.package:self.app};self.files['bundle/app.aab']=self.aab;self.files['qa/tested.apk']=self.apk;self.files['qa/installed.txt']=(digest(self.apk)+'  /data/app/unit/'+self.package+'-unit/base.apk\n').encode();self.files['qa/unit-proof.txt']=b'EXPLICIT SYNTHETIC UNIT REVIEW; NOT ACTUAL NATIVE QA'
        self.screens={}
        for j,l in enumerate(self.app['listingLocales']):
            rows=[]
            for i in range(4):
                color=(20+j*50+i,40+i,60+i);p='screens/'+l+'/'+str(i+1)+'.png';r='raw/'+l+'/'+str(i+1)+'.png';self.files[p]=png(color);self.files[r]=png((*color,255));rows.append({**self.entry(p),'rawNative':self.entry(r),'pixelSha256':digest(bytes(color)*320*640),**self.app['frameLanguageRequirements'][l][i]})
            self.screens[l]=rows
        inventory={'schema':1,'operation':'inspect_existing_locales','ok':True,'inspectedAtUTC':NOW.isoformat(),'apps':[{'package':self.package,'status':'ok','localeIds':self.app['listingLocales'],'cleanup':{'confirmed':True,'httpStatus':204}}]};self.files['qa/locales.json']=encode(inventory);self.app['localeSnapshotSha256']=digest(self.files['qa/locales.json'])
        apkproof={'package':self.package,'versionCode':self.app['newVersionCode'],'versionName':self.app['newVersionName'],'sourceCommit':self.app['reviewedSourceCommit'],'sourceAabSha256':digest(self.aab),'apkSha256':digest(self.apk),'normalApplication':True,'actualDerivedApkFile':self.entry('qa/tested.apk'),'actualInstalledHashRawProof':self.entry('qa/installed.txt')};self.files['qa/apk-proof.json']=encode(apkproof)
        self.qa={'schema':1,'outcome':'pass','platform':'Android','normalApplication':True,'package':self.package,'versionCode':self.app['newVersionCode'],'versionName':self.app['newVersionName'],'sourceCommit':self.app['reviewedSourceCommit'],'signedAabSha256':digest(self.aab),'testedApkSha256':digest(self.apk),'testedAtUtc':NOW.isoformat(),'listingLocales':self.app['listingLocales'],'screenshots':self.screens,'realTransactions':{'purchases':False,'restores':False,'redemptions':False,'adImpressions':False},'checks':{'launch':True,'main':True,'navigation':True,'fontAndAssets':True},'apkProof':self.entry('qa/apk-proof.json'),'proof':[self.entry(n)for n in ['qa/tested.apk','qa/installed.txt','qa/unit-proof.txt']],'syntheticFixtureOnly':True}
        self.rights={'schema':1,'reviewer':'root','outcome':'cleared_for_distribution','package':self.package,'sourceCommit':self.app['reviewedSourceCommit'],'signedAabSha256':digest(self.aab),'fullSignedPayloadSha256':self.app['fullSignedPayloadSha256'],'requiredBundleAssets':self.app['requiredBundleAssets'],'proof':[self.entry('qa/unit-proof.txt')],'syntheticFixtureOnly':True}
        self.manifest={'schema':1,'package':self.package,'versionCode':self.app['newVersionCode'],'versionName':self.app['newVersionName'],'bundle':self.entry('bundle/app.aab'),'nativeQa':{},'screenshots':self.screens,'localeInventory':self.entry('qa/locales.json'),'rootReview':{},'rightsEvidence':{},'sourceEvidence':{p['role']:{'path':p['path'],'sha256':p['sha256']}for p in self.app['sourceProofs']}}
        self.review={'schema':1,'reviewer':'root','outcome':'approved_candidate_inputs','package':self.package,'sourceCommit':self.app['reviewedSourceCommit'],'versionCode':self.app['newVersionCode'],'versionName':self.app['newVersionName'],'signedAabSha256':digest(self.aab),'testedApkSha256':digest(self.apk),'screenshots':self.screens,'rootVisuallyReviewedAllEight':True,'testedAtUtc':NOW.isoformat(),'syntheticFixtureOnly':True}
    def entry(self,p):return {'path':p,'sha256':digest(self.files[p])}
    def raw(self):
        self.files['qa/native.json']=encode(self.qa);self.manifest['nativeQa']=self.entry('qa/native.json');self.files['qa/rights.json']=encode(self.rights);self.manifest['rightsEvidence']=self.entry('qa/rights.json');self.review.update(nativeQaSha256=self.manifest['nativeQa']['sha256'],rightsEvidenceSha256=self.manifest['rightsEvidence']['sha256']);self.files['qa/root-review.json']=encode(self.review);self.manifest['rootReview']=self.entry('qa/root-review.json');self.app['rootReviewSha256']=self.manifest['rootReview']['sha256'];self.app['rightsEvidenceSha256']=self.manifest['rightsEvidence']['sha256'];self.files['manifest.json']=encode(self.manifest);return packed(self.files)

class FixtureVerifier:
    def verify(self,raw,app):return dict(jarVerified=True,package=app['package'],versionCode=app['newVersionCode'],versionName=app['newVersionName'],sha1=app['certificate']['sha1'],sha256=app['certificate']['sha256'])
