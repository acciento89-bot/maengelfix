"""Bounded current Nine8 contracts, actual proof bytes and synthetic negative language cases."""
import json,copy,unittest
from fixtures import HERE,digest
import candidate,game_policy
class Nine8CurrentTests(unittest.TestCase):
 def app(self):
  raw=(HERE/"game-catalog.json").read_bytes();return game_policy.load_catalog(HERE/"game-catalog.json",digest(raw))["de.kamilunavo.ninenine"]
 def test_current_profiles_equal_exact_current_pair_no_stale_metadata(self):
  a=self.app();r=next(r for r in a["sourceProofs"]if r["path"].endswith("/current-full-aab-apk-pair.json"));raw=(HERE/r["path"]).read_bytes();self.assertEqual(digest(raw),"ac3531c3d81ca214718668c08cfdee51c43a16b3ab8ce96095fc95c2fb919b9d");pair=json.loads(raw);self.assertEqual(a["allowedGeneratedBaselineExtras"],pair["generatedExtras"]);self.assertEqual(pair["generatedExtras"]["assets/dexopt/baseline.prof"],"e855fe4ba080be5fc6a4d7ab904bcbc94f0cad911d8c3c9ca1ea6bdffbb671c8")
 def test_current_source_derivation_binds_exact_reviewed_binary_and_all_proofs(self):
  a=self.app();r=next(r for r in a["sourceProofs"]if r["path"].endswith("/current-qa-derivation.json"));raw=(HERE/r["path"]).read_bytes();self.assertEqual(digest(raw),"407bb3258623dd3288a919c361d097dafe2c9d91e35fbd68aa7862958409a44c");d=json.loads(raw);self.assertEqual(d["sourceCommit"],a["reviewedSourceCommit"]);self.assertEqual(d["signedAab"]["sha256"],a["signedAabSha256"]);self.assertEqual(d["qaApk"]["sha256"],a["testedDerivedApkSha256"]);self.assertEqual((a["newVersionCode"],len(a["sourceProofs"]),len(a["requiredBundleAssets"])),(8,29,12))
 def test_new_shell_enum_rejects_boolean_wrong_source_or_other_identity(self):
  a=self.app()
  for key,value in [("newVersionCode",True),("reviewedSourceCommit","c996"),("package","de.kamilunavo.idlehandwerker"),("uiLanguagePolicy","unknown")]:
   b=copy.deepcopy(a);b[key]=value
   with self.subTest(key=key),self.assertRaises(candidate.CandidateError):game_policy.language_requirements(b)
 def test_mixed_privacy_is_only_explicit_practice_scope(self):
  a=self.app();game_policy.language_requirements(a);b=copy.deepcopy(a);entry=next(e for rows in b["frameLanguageRequirements"].values()for e in rows if e["mixedUi"]);entry["screenScope"]="other"
  with self.assertRaises(candidate.CandidateError):game_policy.language_requirements(b)
