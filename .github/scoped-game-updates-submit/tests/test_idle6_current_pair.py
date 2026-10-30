"""Exact retained current Idle6 metadata contracts; no external binaries or native claims."""
import json,unittest
from fixtures import HERE,digest
import game_policy
class CurrentIdlePairTests(unittest.TestCase):
 def app(self):return game_policy.fixed_apps()["de.kamilunavo.idlehandwerker"]
 def role(self,name):
  row=next(r for r in self.app()["sourceProofs"]if r["role"]==name);raw=(HERE/row["path"]).read_bytes();self.assertEqual(digest(raw),row["sha256"]);return json.loads(raw)
 def test_actual_current_generated_profiles_equal_the_pinned_current_pair(self):
  row=next(r for r in self.app()["sourceProofs"]if r["path"].endswith("/all-module-aab-apk-pair.json"));raw=(HERE/row["path"]).read_bytes();self.assertEqual(digest(raw),"117b7aededa6a0ff6060f7ced3a91594f2bbb19cd97cef005484a9db198d86a1");proof=json.loads(raw)
  self.assertEqual(self.app()["allowedGeneratedBaselineExtras"],proof["generatedExtras"]);self.assertEqual(proof["generatedExtras"]["assets/dexopt/baseline.prof"],"dbbc01a3553277354b004819b0d807333f125d0ff388c39a7a3809c506b21d0a");self.assertEqual((proof["mappedEntries"],proof["installTimeAssets"]),(462,457))
 def test_current_pair_derivation_binds_source_signed_aab_and_tested_apk(self):
  a=self.app();row=next(r for r in a["sourceProofs"]if r["path"].endswith("/qa-derivation.json"));raw=(HERE/row["path"]).read_bytes();self.assertEqual(digest(raw),"b4603c679e96c1d02c47b97c184a91a0787cc3710c82095bd1f8106115423bd7");d=json.loads(raw)
  self.assertEqual(d["sourceCommit"],a["reviewedSourceCommit"]);self.assertEqual(d["signedAab"]["sha256"],a["signedAabSha256"]);self.assertEqual(d["qaApk"]["sha256"],a["testedDerivedApkSha256"]);self.assertEqual((a["newVersionCode"],len(a["sourceProofs"]),len(a["requiredBundleAssets"])),(6,29,17))
