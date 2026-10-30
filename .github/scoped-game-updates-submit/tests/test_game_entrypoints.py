import copy,inspect,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import HERE,NOW,digest
from game_fixtures import GameFixture,FixtureVerifier,ready_app
from test_cli import CTX
from test_transport import Opener
from test_locale_inventory import ReadOnlyTransport
import candidate,cli,publisher,release_asset,game_policy

class SourceMetadata:
    def __init__(self,app):
        self.calls=[];self.data={}
        for row in app['sourceTopology']['cloudReads']:
            if row['kind']=='run':value={'id':row['id'],'head_sha':row['head'],'head_branch':'main','path':row['workflow'],'event':'workflow_dispatch','run_attempt':1,'status':'completed','conclusion':'success','repository':{'full_name':row['repository']},'head_repository':{'full_name':row['repository']}}
            else:value={'id':row['id'],'name':row['name'],'expired':False,'digest':'sha256:'+row['archiveSha256'],'workflow_run':{'id':row['runId'],'head_sha':row['head'],'head_branch':'main'}}
            self.data[game_policy.cloud_route(row)]=value
    def json(self,path):self.calls.append(path);return copy.deepcopy(self.data[path])

class DraftGithub:
    def __init__(self,f):
        self.raw=f.raw();self.calls=[];self.data={};own=release_asset.OWN_REPOSITORY;a=f.app
        asset={'id':91,'name':'game-update-candidate-'+f.package+'-'+a['newVersionName']+'-'+str(a['newVersionCode'])+'.zip','size':len(self.raw),'state':'uploaded','digest':'sha256:'+digest(self.raw)}
        self.data['/repos/'+own]={'full_name':own};self.data['/repos/'+own+'/releases/assets/91']=asset;self.data['/repos/'+own+'/releases?per_page=100&page=1']=[{'id':81,'draft':True,'assets':[asset]}]
    def json(self,path):self.calls.append(path);return copy.deepcopy(self.data[path])
    def download_asset(self,id):return self.raw

class GameEntrypointTests(unittest.TestCase):
    def enabled(self):self.assertIn('family',inspect.signature(cli.prepare_candidate).parameters,'Game CLI/transfer adaptation missing')
    def test_actual_source_topology_metadata_exact_ids_paths_attempts_and_digests_only(self):
        for a in game_policy.fixed_apps().values():
            c=candidate.Candidate(a['package'],a,{},b'',a['signedAabSha256'],'a'*64,{},None,'b'*64);g=SourceMetadata(a);game_policy.verify_current_source(g,c);self.assertEqual(len(g.calls),len(a['sourceTopology']['cloudReads']))
            for path,meta in g.data.items():
                bad=SourceMetadata(a);bad.data[path]['path']='.github/workflows/unrelated.yml'if '/runs/'in path else meta.get('path');bad.data[path]['digest']='sha256:'+'0'*64
                with self.assertRaises(candidate.CandidateError):game_policy.verify_current_source(bad,c)
    def test_prepare_transfer_uses_exact_same_owned_draft_bytes_without_invented_rune_ci(self):
        self.enabled();f=GameFixture(self);g=DraftGithub(f)
        with tempfile.TemporaryDirectory()as temp:
            dest=Path(temp)/'new';a=cli.prepare_candidate(g,91,digest(g.raw),f.package,f.catalog,'f'*64,FixtureVerifier(),dest,CTX,NOW,family='game5');self.assertIsNone(a['ci']['githubOrigin']);self.assertFalse(any('/actions/'in p for p in g.calls));c=cli.verify_transfer(dest,digest(g.raw),digest((dest/'attestation.json').read_bytes()),f.package,f.catalog,'f'*64,FixtureVerifier(),CTX,NOW,family='game5');self.assertEqual(c.bundle_sha256,f.app['signedAabSha256'])
            with self.assertRaises(candidate.CandidateError):cli.verify_transfer(dest,digest(g.raw),digest((dest/'attestation.json').read_bytes()),f.package,f.catalog,'f'*64,FixtureVerifier(),{**CTX,'runId':124},NOW,family='game5')
    def test_game_github_client_only_exact_public_source_metadata_and_own_draft_read_routes(self):
        self.enabled();g=release_asset.GitHubClient('unit-only',family='game5');opener=Opener();g._opener=opener
        for p in game_policy.metadata_routes():g.json(p)
        count=len(opener.calls)
        for p in ['/repos/acciento89-bot/runenpfad/actions/runs/1','/repos/acciento89-bot/risingsteps/actions/runs/1','/repos/acciento89-bot/SHK/actions/runs/42','/repos/acciento89-bot/99-9/actions/runs/40912634003/rerun','https://evil.invalid']:
            with self.assertRaises(candidate.CandidateError):g.json(p)
        self.assertEqual(len(opener.calls),count);self.assertTrue(all(r.get_method()=='GET'for r,_ in opener.calls))
    def test_fixed_game_version_production_only_and_safe_commit_behavior_transport(self):
        self.enabled();raw=(HERE/'game-catalog.json').read_bytes();cat=game_policy.load_catalog(HERE/'game-catalog.json',digest(raw));a=ready_app();cat[a['package']]=a;client=publisher.HttpTransport('unit-only',cat,inspect_only=False,family='game5');opener=Opener();client._opener=opener;base='/androidpublisher/v3/applications/'+a['package']+'/edits/own';track={'track':'production','releases':[{'versionCodes':['6'],'status':'completed','name':'0.4.0 (6)','releaseNotes':[{'language':l,'text':'Unit'}for l in ['de-DE','en-US']]}]};client.request('PUT',base+'/tracks/production',track)
        old=copy.deepcopy(track);old['releases'][0].update(versionCodes=['5'],name='0.4.0 (5)')
        with self.assertRaises(Exception):client.request('PUT',base+'/tracks/production',old)
        for method,path,body in [('POST',base+':commit',None),('POST',base+':commit?changesInReviewBehavior=CANCEL_IN_REVIEW_AND_SUBMIT',None),('PUT',base+'/tracks/beta',track),('POST','/androidpublisher/v3/applications/com.kamilunavo.onemorefloor/edits',{})]:
            with self.assertRaises(Exception):client.request(method,path,body)
        self.assertEqual(len(opener.calls),1)
    def test_inspect_pending_five_needs_no_candidate_java_or_submission(self):
        self.enabled();env={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-game-updates-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_GAME_OPERATION':'inspect','TOKEN':'unit-only'}
        with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,env,clear=True),patch.object(cli,'BundleVerifier',side_effect=AssertionError('No Java')),patch.object(cli,'GitHubClient',side_effect=AssertionError('No draft download')),patch.object(cli,'submit_candidate',side_effect=AssertionError('No submit')),patch.object(cli,'HttpTransport',return_value=ReadOnlyTransport()):
            report=Path(temp)/'receipt.json';r=cli.main(['inspect','--package','all-five','--catalog-sha256',digest((HERE/'game-catalog.json').read_bytes()),'--report',str(report)],family='game5');self.assertEqual(r,0);d=json.loads(report.read_text());self.assertEqual(len(d['apps']),5);self.assertTrue(all(x['cleanup']['confirmed']for x in d['apps']))
