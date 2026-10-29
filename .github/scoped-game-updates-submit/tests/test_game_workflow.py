import json,unittest
from fixtures import HERE,digest
import game_policy
WF=HERE.parent/'workflows/navoops-game-updates-production-submit.yml'
class GameWorkflowTests(unittest.TestCase):
    def workflow(self):self.assertTrue(WF.is_file(),'Separate five-game manual workflow missing');return json.loads(WF.read_text())
    def test_only_manual_exact_five_default_inspect_excludes_new_inreview_or_protected_games(self):
        w=self.workflow();self.assertEqual(set(w['on']),{'workflow_dispatch'});i=w['on']['workflow_dispatch']['inputs'];self.assertEqual(set(i),{'operation','package','candidate_asset_id','archive_sha256'});self.assertEqual(set(i['package']['options']),set(game_policy.scope('game5'))|{'all-five'});self.assertEqual(i['package']['default'],'all-five');self.assertEqual(i['operation']['default'],'inspect');self.assertEqual(i['operation']['options'],['inspect','submit']);self.assertEqual(w['concurrency'],{'group':'scoped-game-updates-production-submit','cancel-in-progress':False})
    def test_no_google_identity_in_prepare_and_existing_wif_only_after_immutable_transfer_verification(self):
        w=self.workflow();j=w['jobs'];self.assertEqual(w['permissions'],{'contents':'read'});self.assertEqual(set(j),{'inspect','prepare','submit'});self.assertEqual(j['prepare']['permissions'],{'contents':'write','actions':'read'});self.assertFalse(any(x.get('uses','').startswith('google-github-actions/')for x in j['prepare']['steps']))
        for name in ['inspect','submit']:self.assertEqual(j[name]['permissions'],{'contents':'read','id-token':'write'})
        for name,job in j.items():
            self.assertIn("github.ref == 'refs/heads/main'",job['if']);self.assertIn("github.event_name == 'workflow_dispatch'",job['if']);self.assertIn('github.run_attempt == 1',job['if']);self.assertNotIn('strategy',job);self.assertEqual(job['steps'][0]['with'],{'ref':'${{ github.sha }}','persist-credentials':False})
            self.assertEqual(job['env']['SCOPED_GAME_OPERATION'],'inspect'if name=='inspect'else'submit')
        steps=j['submit']['steps'];ids=[x.get('id')for x in steps];self.assertLess(ids.index('verify'),ids.index('google-auth'));transfer=next(x for x in steps if x.get('id')=='transfer');self.assertEqual(transfer['with']['artifact-ids'],'${{ needs.prepare.outputs.artifact_id }}');self.assertNotIn('name',transfer['with'])
        self.assertEqual(w['env']['WIF_PROVIDER'],'projects/1058001477767/locations/global/workloadIdentityPools/github/providers/github-actions');self.assertEqual(w['env']['GOOGLE_SERVICE_ACCOUNT'],'navoops@emerald-caster-508318-f2.iam.gserviceaccount.com')
    def test_game_catalog_exact_known_registry_and_game_entrypoint_are_pinned(self):
        w=self.workflow();self.assertEqual(w['env']['CATALOG_SHA256'],digest((HERE/'game-catalog.json').read_bytes()))
        for job in w['jobs'].values():
            for step in job['steps']:
                if 'cli.py 'in step.get('run',''):self.assertIn('scoped-game-updates-submit/game_cli.py ',step['run']);self.assertNotIn('scoped-calculator-submit',step['run']);self.assertNotIn('scoped-business-submit',step['run'])
    def test_inspect_never_downloads_candidate_tools_or_enters_submit(self):
        w=self.workflow();job=w['jobs']['inspect'];step=next(x for x in job['steps']if x.get('id')=='inspect');self.assertIn('game_cli.py inspect ',step['run']);self.assertNotIn('--asset-id',step['run']);self.assertNotIn('--archive-sha256',step['run']);self.assertFalse(any(x.get('uses','').startswith(('actions/setup-java','actions/download-artifact'))for x in job['steps']));self.assertFalse(any('curl 'in x.get('run','')for x in job['steps']))
