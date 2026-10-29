import hashlib, json, unittest
from fixtures import HERE
import candidate

PATH=HERE.parent/'workflows/navoops-calculator-production-submit.yml'
class WorkflowTests(unittest.TestCase):
    def setUp(self):self.workflow=json.loads(PATH.read_text())
    def test_only_manual_exact_nine_package_and_immutable_asset_inputs(self):
        self.assertEqual(set(self.workflow['on']),{'workflow_dispatch'})
        inputs=self.workflow['on']['workflow_dispatch']['inputs'];self.assertEqual(set(inputs),{'operation','package','candidate_asset_id','archive_sha256'})
        self.assertEqual(inputs['package']['type'],'choice');self.assertEqual(set(inputs['package']['options']),set(candidate.EXPECTED)|{'all-nine'})
        self.assertEqual(inputs['operation']['options'],['inspect','submit']);self.assertEqual(inputs['operation']['default'],'inspect')
        self.assertEqual(inputs['package']['default'],'all-nine');self.assertTrue(inputs['operation']['required']);self.assertTrue(inputs['package']['required'])
        self.assertFalse(inputs['candidate_asset_id']['required']);self.assertFalse(inputs['archive_sha256']['required'])
        self.assertEqual(self.workflow['concurrency'],{'group':'scoped-calculator-production-submit','cancel-in-progress':False})
    def test_prepare_cannot_obtain_google_identity_and_both_jobs_pin_own_main_first_attempt(self):
        jobs=self.workflow['jobs'];self.assertEqual(set(jobs),{'inspect','prepare','submit'})
        for name,job in jobs.items():
            self.assertEqual(job['if'],"github.repository == 'acciento89-bot/maengelfix' && github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch' && github.run_attempt == 1"+" && inputs.operation == '"+('inspect' if name == 'inspect' else 'submit')+"'")
            checkout=job['steps'][0];self.assertEqual(checkout['uses'],'actions/checkout@v5');self.assertEqual(checkout['with'],{'ref':'${{ github.sha }}','persist-credentials':False})
            self.assertNotIn('strategy',job)
        self.assertEqual(jobs['prepare']['permissions'],{'contents':'write','actions':'read'})
        self.assertFalse(any(s.get('uses','').startswith('google-github-actions/')for s in jobs['prepare']['steps']))
        self.assertEqual(jobs['submit']['permissions'],{'contents':'read','id-token':'write'})
    def test_same_bytes_verified_before_existing_wif_and_transfer_uses_immutable_artifact_id(self):
        steps=self.workflow['jobs']['submit']['steps'];ids=[s.get('id')for s in steps]
        self.assertLess(ids.index('verify'),ids.index('google-auth'));self.assertLess(ids.index('google-auth'),ids.index('submit'))
        transfer=next(s for s in steps if s.get('id')=='transfer');self.assertEqual(transfer['uses'],'actions/download-artifact@v4')
        self.assertEqual(transfer['with']['artifact-ids'],'${{ needs.prepare.outputs.artifact_id }}');self.assertNotIn('name',transfer['with'])
        auth=next(s for s in steps if s.get('id')=='google-auth');self.assertEqual(auth['with'],{
            'workload_identity_provider':'${{ env.WIF_PROVIDER }}','service_account':'${{ env.GOOGLE_SERVICE_ACCOUNT }}',
            'token_format':'access_token','access_token_scopes':'https://www.googleapis.com/auth/androidpublisher'})
        self.assertEqual(auth['uses'],'google-github-actions/auth@v3')
        token_steps=[s['id']for s in steps if 'TOKEN'in s.get('env',{})];self.assertEqual(token_steps,['submit'])
    def test_catalog_digest_and_readonly_default_permissions_are_frozen(self):
        self.assertEqual(self.workflow['env']['CATALOG_SHA256'],hashlib.sha256((HERE/'catalog.json').read_bytes()).hexdigest())
        self.assertEqual(self.workflow['permissions'],{'contents':'read'})
        self.assertEqual(self.workflow['env']['WIF_PROVIDER'],'projects/1058001477767/locations/global/workloadIdentityPools/github/providers/github-actions')
        self.assertEqual(self.workflow['env']['GOOGLE_SERVICE_ACCOUNT'],'navoops@emerald-caster-508318-f2.iam.gserviceaccount.com')

    def test_inspect_job_has_no_candidate_download_java_or_mutating_cli_and_explicit_mode(self):
        job=self.workflow['jobs']['inspect'];self.assertEqual(job['permissions'],{'contents':'read','id-token':'write'})
        self.assertEqual(job['env']['SCOPED_CALCULATOR_OPERATION'],'inspect')
        steps=job['steps'];inspect=next(s for s in steps if s.get('id')=='inspect')
        self.assertIn('cli.py inspect --package',inspect['run']);self.assertNotIn('--asset-id',inspect['run']);self.assertNotIn('--archive-sha256',inspect['run'])
        self.assertFalse(any(s.get('uses','').startswith(('actions/setup-java','actions/download-artifact'))for s in steps))
        self.assertFalse(any('curl 'in s.get('run','')for s in steps))
        self.assertEqual([s['id']for s in steps if 'TOKEN'in s.get('env',{})],['inspect'])
        for name in ['prepare','submit']:self.assertEqual(self.workflow['jobs'][name]['env']['SCOPED_CALCULATOR_OPERATION'],'submit')

    def test_draft_visibility_write_permission_exists_only_in_google_free_prepare_job(self):
        jobs=self.workflow['jobs'];self.assertEqual([name for name,job in jobs.items()if job['permissions'].get('contents')=='write'],['prepare'])
        self.assertEqual(self.workflow['permissions'],{'contents':'read'});self.assertEqual(jobs['inspect']['permissions'],{'contents':'read','id-token':'write'});self.assertEqual(jobs['submit']['permissions'],{'contents':'read','id-token':'write'})
        self.assertNotIn('id-token',jobs['prepare']['permissions']);self.assertFalse(any(s.get('uses','').startswith('google-github-actions/')for s in jobs['prepare']['steps']))
        self.assertEqual([s['id']for s in jobs['prepare']['steps']if 'GH_TOKEN'in s.get('env',{})],['verify'])
