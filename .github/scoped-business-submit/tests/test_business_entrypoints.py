import copy,inspect,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import HERE,NOW,digest
from business_fixtures import BusinessFixture,BusinessVerifier
from test_cli import CTX
from test_transport import Opener
from test_locale_inventory import ReadOnlyTransport
import candidate,cli,publisher,release_asset,business_policy

class BusinessGitHub:
    def __init__(self,f):
        self.raw=f.raw();a=f.app;self.calls=[];self.downloads=[];self.download_contexts=[];self.data={};own=release_asset.OWN_REPOSITORY;self.expected_package=f.package;self.expected_app=copy.deepcopy(a)
        asset={'id':91,'name':'business-candidate-'+f.package+'-'+a['newVersionName']+'-'+str(a['newVersionCode'])+'.zip','size':len(self.raw),'state':'uploaded','digest':'sha256:'+digest(self.raw)}
        self.asset=asset
        self.data['/repos/'+own]={'full_name':own};self.data['/repos/'+own+'/releases/assets/91']=asset;self.data['/repos/'+own+'/releases?per_page=100&page=1']=[{'id':81,'draft':True,'assets':[asset]}]
        for section,kind in ([('source','sourceArtifactName'),('signing','signedArtifactName')]if 'signing'in f.manifest else [('source','signedArtifactName')]):
            p=f.manifest[section];base='/repos/'+a['repository']+'/actions/'
            self.data[base+'runs/'+str(p['runId'])]={'id':p['runId'],'head_sha':p['commit'],'head_branch':'main','event':'workflow_dispatch','path':p['workflow'],'status':'completed','conclusion':'success','repository':{'full_name':a['repository']},'head_repository':{'full_name':a['repository']}}
            self.data[base+'artifacts/'+str(p['artifactId'])]={'id':p['artifactId'],'name':a[kind],'expired':False,'digest':'sha256:'+p['artifactArchiveSha256'],'workflow_run':{'id':p['runId'],'head_sha':p['commit'],'head_branch':'main'}}
    def json(self,path):self.calls.append(path);return copy.deepcopy(self.data[path])
    def download_asset(self,asset,*,package,app,expected_size):
        assert package==self.expected_package and app==self.expected_app
        assert type(expected_size)is int and expected_size==self.asset['size']
        self.download_contexts.append({'package':package,'app':copy.deepcopy(app),'expected_size':expected_size})
        self.downloads.append(asset);return self.raw

class BusinessEntrypointTests(unittest.TestCase):
    def enabled(self):self.assertIn('family',inspect.signature(cli.prepare_candidate).parameters,'Business entrypoint wiring missing')
    def test_prepare_transfer_exact_own_draft_and_eas_two_official_reads_without_invented_signer(self):
        self.enabled();f=BusinessFixture('com.kamilunavo.navokids');g=BusinessGitHub(f)
        with tempfile.TemporaryDirectory()as temp:
            dest=Path(temp)/'new';a=cli.prepare_candidate(g,91,digest(g.raw),f.package,f.catalog,'f'*64,BusinessVerifier(),dest,CTX,NOW,family='business12')
            self.assertEqual(len([p for p in g.calls if '/actions/'in p]),2);self.assertEqual(a['ci']['sourceRunId'],42);self.assertNotIn('signingRunId',a['ci']);self.assertEqual(g.download_contexts,[{'package':f.package,'app':f.app,'expected_size':g.asset['size']}])
            c=cli.verify_transfer(dest,digest(g.raw),digest((dest/'attestation.json').read_bytes()),f.package,f.catalog,'f'*64,BusinessVerifier(),CTX,NOW,family='business12');self.assertEqual(c.package,f.package)
            with self.assertRaises(candidate.CandidateError):cli.verify_transfer(dest,digest(g.raw),digest((dest/'attestation.json').read_bytes()),f.package,f.catalog,'f'*64,BusinessVerifier(),{**CTX,'runId':124},NOW,family='business12')
    def test_official_run_path_event_or_artifact_mismatch_rejected_central_and_eas(self):
        self.enabled()
        for package in ['com.kamilunavo.maengelfix','com.kamilunavo.navokids']:
            for key,value in [('event','push'),('path','.github/workflows/unrelated.yml'),('head_sha','a'*40)]:
                f=BusinessFixture(package);g=BusinessGitHub(f);c=candidate.validate_archive(g.raw,digest(g.raw),package,f.catalog,BusinessVerifier(),NOW,family='business12');run=next(p for p in g.data if '/actions/runs/'in p);g.data[run][key]=value
                with self.subTest(package=package,key=key),self.assertRaises(candidate.CandidateError):release_asset.verify_provenance(g,c,family='business12')
    def test_business_http_transport_is_closed_twelve_and_exact_app_version_only(self):
        self.enabled();raw=(HERE/'business-catalog.json').read_bytes();cat=business_policy.load_catalog(HERE/'business-catalog.json',digest(raw));f=BusinessFixture();cat[f.package]=f.app;f.raw()
        client=publisher.HttpTransport('unit-only',cat,inspect_only=False,family='business12');opener=Opener();client._opener=opener;base='/androidpublisher/v3/applications/'+f.package+'/edits/own'
        track={'track':'production','releases':[{'versionCodes':['9'],'status':'completed','name':'1.1.0 (9)','releaseNotes':[{'language':l,'text':'Unit note'}for l in ['de-DE','en-US']]}]}
        client.request('PUT',base+'/tracks/production',track);self.assertEqual(len(opener.calls),1)
        for method,path,body in [('PUT',base+'/tracks/internal',track),('POST',base+':commit',None),('POST',base+':commit?changesInReviewBehavior=CANCEL_IN_REVIEW_AND_SUBMIT',None),('POST','/androidpublisher/v3/applications/de.kamilunavo.brennercalc/edits',{}),('PUT',base+'/tracks/production',{**track,'releases':[{**track['releases'][0],'name':'1.2.0 (9)'}]})]:
            with self.subTest(path=path),self.assertRaises(Exception):client.request(method,path,body)
        self.assertEqual(len(opener.calls),1)
    def test_business_metadata_client_denies_calculator_other_owner_and_mutation_paths(self):
        self.enabled();client=release_asset.GitHubClient('unit-only',family='business12');opener=Opener();client._opener=opener
        for repo in {a['repository']for a in business_policy.fixed_apps().values()}:client.json('/repos/'+repo+'/actions/runs/42')
        count=len(opener.calls)
        for path in ['/repos/acciento89-bot/SHK/actions/runs/42','/repos/acciento89-bot/OneMoreFloor/actions/runs/42','/repos/other/navokids/actions/runs/42','/repos/acciento89-bot/navokids/actions/runs/42/rerun','https://evil.invalid']:
            with self.assertRaises(candidate.CandidateError):client.json(path)
        self.assertEqual(len(opener.calls),count);self.assertTrue(all(r.get_method()=='GET'for r,_ in opener.calls))
    def test_only_business_own_manual_main_workflow_context_and_pending_submit_before_github(self):
        self.enabled();good={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-business-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_BUSINESS_OPERATION':'submit'}
        self.assertEqual(cli.execution_context(good,family='business12'),CTX)
        with self.assertRaises(candidate.CandidateError):cli.execution_context({**good,'GITHUB_WORKFLOW_REF':good['GITHUB_WORKFLOW_REF'].replace('business','calculator')},family='business12')
        with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,good,clear=True),patch.object(cli,'GitHubClient',side_effect=AssertionError('Pending evidence must stop before network'))as github:
            code=cli.main(['prepare','--package','de.kamilunavo.navopass','--catalog-sha256',digest((HERE/'business-catalog.json').read_bytes()),'--report',str(Path(temp)/'report.json'),'--archive-sha256','a'*64,'--bundletool','not-read','--bundletool-sha256','b'*64],family='business12')
            self.assertEqual(code,2);github.assert_not_called()
