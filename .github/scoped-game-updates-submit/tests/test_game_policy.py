"""Five actual known binaries; source/static evidence is not native QA."""
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from fixtures import HERE
import candidate

class GamePolicyTests(unittest.TestCase):
    def policy(self):
        self.assertIsNotNone(importlib.util.find_spec('game_policy'),'Closed game policy missing')
        import game_policy
        return game_policy
    def test_exact_five_packages_codes_versions_known_binaries_and_rune_certificate(self):
        p=self.policy();apps=p.fixed_apps();self.assertEqual(len(apps),5);self.assertEqual({a['package']:a['newVersionCode']for a in apps.values()},{'com.kamilunavo.perfectdrop':15,'com.kamilunavo.risingsteps':9,'com.kamilunavo.runenpfad':6,'de.kamilunavo.ninenine':7,'de.kamilunavo.idlehandwerker':5});r=apps['com.kamilunavo.runenpfad'];self.assertEqual(r['newVersionName'],'0.4.0');self.assertEqual(r['certificate']['sha256'],'A76F8F0ED69FDD6BB1181322A07B961A353605E8B9F654A0D4E6BC2F186BEF2B');self.assertIsNone(r['repository']);self.assertEqual(r['sourceTopology']['cloudReads'],[])
    def test_unknown_future_binary_source_topology_or_other_app_cannot_join(self):
        p=self.policy();app=copy.deepcopy(p.fixed_apps()['com.kamilunavo.risingsteps'])
        for key,value in [('signedAabSha256','0'*64),('testedDerivedApkSha256','0'*64),('certificate',p.fixed_apps()['com.kamilunavo.runenpfad']['certificate']),('reviewedSourceCommit','a'*40),('newVersionName','9.9.9'),('package','com.kamilunavo.onemorefloor')]:
            bad=copy.deepcopy(app);bad[key]=value
            with self.subTest(key=key),self.assertRaises(candidate.CandidateError):p.assert_identity(bad)
        with self.assertRaises(candidate.CandidateError):p.scope('all-games')
        self.assertEqual(set(p.scope('calculator9')),set(candidate.EXPECTED))
    def test_actual_rune6_inputs_ready_only_other_four_remain_pending(self):
        p=self.policy();raw=(HERE/'game-catalog.json').read_bytes();cat=p.load_catalog(HERE/'game-catalog.json',candidate.digest(raw));self.assertEqual(len(cat),5)
        for app in cat.values():
            if app['package']=='com.kamilunavo.runenpfad':
                self.assertEqual((app['previousProductionCode'],app['previousMaxCode'],app['newVersionCode'],app['reservedUnusedVersionCodes']),(4,4,6,[5]))
                self.assertEqual(app['rootReviewSha256'],'5ee7e6a6572620ce1e7dc39c2c54a3a483d1575aa58f7391b76fb108aa1b99f8');self.assertEqual(app['rightsEvidenceSha256'],'97fa9dab4206b3940c4703610c2c02448981ecd8c4db4c3ff263ad1db661bf9c')
                self.assertEqual(p.require_ready(app),('de-DE','en-US'));self.assertTrue(p.allows_reserved_game_step(app,4,'game5'))
            else:
                self.assertEqual(app['newVersionCode'],app['previousMaxCode']+1)
                with self.assertRaises(candidate.CandidateError):p.require_ready(app)
    def test_catalog_shape_duplicate_scope_or_boolean_version_rejected(self):
        p=self.policy();original=json.loads((HERE/'game-catalog.json').read_text())
        for mode in ['schema','duplicate','omitted','topology','binary','extra']:
            d=copy.deepcopy(original)
            if mode=='schema':d['schema']=True
            elif mode=='duplicate':d['apps'][1]=copy.deepcopy(d['apps'][0])
            elif mode=='omitted':d['apps'].pop()
            elif mode=='topology':d['apps'][2]['repository']='acciento89-bot/invented-rune-ci'
            elif mode=='binary':d['apps'][0]['signedAabSha256']='a'*64
            else:d['allowUnknownBinary']=True
            raw=json.dumps(d).encode()
            with tempfile.TemporaryDirectory()as temp:
                path=Path(temp)/'catalog.json';path.write_bytes(raw)
                with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):p.load_catalog(path,candidate.digest(raw))
    def test_unity_serialized_fonts_and_godot_engine_converted_resources_are_honest(self):
        p=self.policy()
        for a in p.fixed_apps().values():
            self.assertTrue(a['fontProofs']);self.assertTrue(a['requiredBundleAssets'])
            for font in a['fontProofs']:
                self.assertFalse(font['entry'].endswith('.ttf'));self.assertIn('originalTtfSha256',font)
                self.assertIn('serialized'if a['engine']=='Unity'else'prior_actual_engine',font['encoding'])
    def test_rune_has_no_invented_ci_and_cloud_routes_are_exact_known_ids_only(self):
        p=self.policy();routes=p.metadata_routes();self.assertFalse(any('runenpfad'in route for route in routes));self.assertTrue(routes)
        for route in routes:self.assertRegex(route,r'^/repos/acciento89-bot/[A-Za-z0-9_-]+/actions/(?:runs|artifacts)/[1-9][0-9]+$')
