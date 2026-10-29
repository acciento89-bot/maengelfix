import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fixtures import HERE,digest
from test_cli import CTX
from test_locale_inventory import ReadOnlyTransport
import business_policy,cli

WF=HERE.parent/'workflows/navoops-business-production-submit.yml'
class BusinessWorkflowTests(unittest.TestCase):
    def workflow(self):self.assertTrue(WF.is_file(),'Business-only manual workflow not staged');return json.loads(WF.read_text())
    def test_only_manual_closed_twelve_default_inspect_no_free_track_version_url(self):
        w=self.workflow();self.assertEqual(set(w['on']),{'workflow_dispatch'});i=w['on']['workflow_dispatch']['inputs'];self.assertEqual(set(i),{'operation','package','candidate_asset_id','archive_sha256'})
        self.assertEqual(set(i['package']['options']),set(business_policy.scope('business12'))|{'all-twelve'});self.assertEqual(i['package']['default'],'all-twelve');self.assertEqual(i['operation']['default'],'inspect');self.assertEqual(i['operation']['options'],['inspect','submit']);self.assertEqual(w['concurrency'],{'group':'scoped-business-production-submit','cancel-in-progress':False})
    def test_existing_wif_google_free_prepare_and_immutable_verified_transfer_before_google(self):
        w=self.workflow();self.assertEqual(w['permissions'],{'contents':'read'});jobs=w['jobs'];self.assertEqual(set(jobs),{'inspect','prepare','submit'})
        self.assertEqual(jobs['prepare']['permissions'],{'contents':'write','actions':'read'});self.assertFalse(any(s.get('uses','').startswith('google-github-actions/')for s in jobs['prepare']['steps']))
        for name in ['inspect','submit']:self.assertEqual(jobs[name]['permissions'],{'contents':'read','id-token':'write'})
        for name,j in jobs.items():
            self.assertIn("github.ref == 'refs/heads/main'",j['if']);self.assertIn("github.event_name == 'workflow_dispatch'",j['if']);self.assertIn('github.run_attempt == 1',j['if']);self.assertNotIn('strategy',j);self.assertEqual(j['steps'][0]['with'],{'ref':'${{ github.sha }}','persist-credentials':False})
            self.assertEqual(j['env']['SCOPED_BUSINESS_OPERATION'],'inspect'if name=='inspect'else'submit')
        steps=jobs['submit']['steps'];ids=[s.get('id')for s in steps];self.assertLess(ids.index('verify'),ids.index('google-auth'));tr=next(s for s in steps if s.get('id')=='transfer');self.assertEqual(tr['with']['artifact-ids'],'${{ needs.prepare.outputs.artifact_id }}');self.assertNotIn('name',tr['with'])
        self.assertEqual(w['env']['WIF_PROVIDER'],'projects/1058001477767/locations/global/workloadIdentityPools/github/providers/github-actions');self.assertEqual(w['env']['GOOGLE_SERVICE_ACCOUNT'],'navoops@emerald-caster-508318-f2.iam.gserviceaccount.com')
    def test_workflow_pins_catalog_and_business_entrypoint_not_default_calculator_cli(self):
        w=self.workflow();self.assertEqual(w['env']['CATALOG_SHA256'],digest((HERE/'business-catalog.json').read_bytes()))
        for job in w['jobs'].values():
            for step in job['steps']:
                if 'cli.py 'in step.get('run',''):self.assertIn('scoped-business-submit/business_cli.py ',step['run']);self.assertNotIn('scoped-calculator-submit',step['run'])
        inspect=next(s for s in w['jobs']['inspect']['steps']if s.get('id')=='inspect');self.assertNotIn('--archive-sha256',inspect['run']);self.assertNotIn('--asset-id',inspect['run'])
    def test_business_inspection_accepts_pending_catalog_and_never_candidate_java_or_submit(self):
        self.workflow();env={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-business-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_BUSINESS_OPERATION':'inspect','TOKEN':'synthetic-only'}
        with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,env,clear=True),patch.object(cli,'BundleVerifier',side_effect=AssertionError('No Java')),patch.object(cli,'GitHubClient',side_effect=AssertionError('No candidate download')),patch.object(cli,'submit_candidate',side_effect=AssertionError('No submit')),patch.object(cli,'HttpTransport',return_value=ReadOnlyTransport())as http:
            path=Path(temp)/'receipt.json';r=cli.main(['inspect','--package','all-twelve','--catalog-sha256',digest((HERE/'business-catalog.json').read_bytes()),'--report',str(path)],family='business12');self.assertEqual(r,0);d=json.loads(path.read_text());self.assertTrue(d['ok']);self.assertEqual(len(d['apps']),12);self.assertTrue(all(a['cleanup']['confirmed']for a in d['apps']));self.assertEqual(http.call_args.kwargs,{'inspect_only':True,'family':'business12'})
