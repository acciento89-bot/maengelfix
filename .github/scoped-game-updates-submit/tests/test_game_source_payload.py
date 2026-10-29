"""Actual retained source evidence and synthetic adversarial payload controls; no native QA."""
import copy,inspect,json,unittest
from pathlib import Path
from fixtures import HERE,digest,packed
import candidate,game_policy

class GameSourceTests(unittest.TestCase):
    def test_all_included_source_proof_bytes_match_the_fixed_registry_without_external_inputs(self):
        for app in game_policy.fixed_apps().values():
            for row in app['sourceProofs']:
                path=HERE/row['path'];self.assertTrue(path.resolve().is_relative_to(HERE.resolve()));raw=path.read_bytes();self.assertEqual(digest(raw),row['sha256']);self.assertEqual(len(raw),row['bytes'])
    def test_bounded_fixture_rejects_missing_modified_extra_proof_or_unknown_binary(self):
        from game_fixtures import GameFixture
        for mode in ['missing','modified','extra_fake_ci','unknown_binary']:
            f=GameFixture(self);files=dict(f.files);m=copy.deepcopy(f.manifest);role=next(iter(m['sourceEvidence']));data=f.aab
            if mode=='missing':del m['sourceEvidence'][role]
            elif mode=='modified':files[m['sourceEvidence'][role]['path']]+=b'changed'
            elif mode=='extra_fake_ci':m['sourceEvidence']['invented-github-run']={'path':'ci/provenance.json','sha256':'a'*64}
            else:data+=b'changed'
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):game_policy.verify_source_evidence(files,m,f.app,candidate.Media('bundle/app.aab',digest(f.aab),data))
    def test_rune_source_verification_never_requests_a_github_origin(self):
        class NoOrigin:
            def json(self,path):raise AssertionError('No GitHub origin for Rune')
        app=game_policy.fixed_apps()['com.kamilunavo.runenpfad'];c=candidate.Candidate(app['package'],app,{},b'',app['signedAabSha256'],'a'*64,{},None,'b'*64);r=game_policy.verify_current_source(NoOrigin(),c);self.assertIsNone(r['githubOrigin']);self.assertEqual(r['actualFixedMetadataReads'],[])

class GamePayloadTests(unittest.TestCase):
    def helper(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('game_payload'),'All-install-time payload adapter missing')
        import game_payload
        return game_payload
    def test_all_install_time_assets_are_mapped_with_no_base_only_success(self):
        h=self.helper();a={'base/dex/classes.dex':b'd','base/assets/base':b'b','assetPackInstallTime/assets/project.binary':b'p','assetPackInstallTime/assets/game.gdc':b'g'};apk={'classes.dex':b'd','assets/base':b'b','assets/project.binary':b'p','assets/game.gdc':b'g'};app={'engine':'Godot','sourceTopology':{'installTimeAssetFiles':2},'allowedGeneratedBaselineExtras':{}}
        r=h.verify_derived_payload(packed(a),packed(apk),app);self.assertEqual(r['installTimeAssets'],2)
        for mode in ['missing_pack','changed_gdc','module_collision','unknown_module','extra_apk']:
            source=copy.deepcopy(a);target=copy.deepcopy(apk)
            if mode=='missing_pack':del target['assets/project.binary']
            elif mode=='changed_gdc':target['assets/game.gdc']=b'old'
            elif mode=='module_collision':source['base/assets/project.binary']=b'p'
            elif mode=='unknown_module':source['other/assets/extra']=b'forbidden'
            else:target['assets/unexpected']=b'unknown'
            with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):h.verify_derived_payload(packed(source),packed(target),app)
    def test_only_exact_documented_generated_baseline_extras_are_accepted(self):
        h=self.helper();a=packed({'base/assets/a':b'a'});app={'engine':'Unity','sourceTopology':{},'allowedGeneratedBaselineExtras':{'assets/dexopt/baseline.prof':digest(b'known')}}
        h.verify_derived_payload(a,packed({'assets/a':b'a','assets/dexopt/baseline.prof':b'known'}),app)
        for value in [b'wrong',None]:
            target={'assets/a':b'a'}
            if value is not None:target['assets/dexopt/baseline.prof']=value
            with self.assertRaises(candidate.CandidateError):h.verify_derived_payload(a,packed(target),app)


class GameBinaryZipTests(unittest.TestCase):
    def parser(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('game_binary'),'Game-only libc++ ZIP adapter missing')
        import game_binary
        return game_binary
    def test_libc_plus_plus_engine_filename_is_accepted_without_relaxing_calculator_reader(self):
        p=self.parser();raw=packed({'base/lib/arm64-v8a/libc++_shared.so':b'unit-library'})
        self.assertEqual(p.binary_files(raw)['base/lib/arm64-v8a/libc++_shared.so'],b'unit-library')
        with self.assertRaises(candidate.CandidateError):candidate.zip_files(raw)
    def test_plus_support_keeps_traversal_case_duplicate_and_symlink_rejection(self):
        p=self.parser();import io,stat,zipfile
        for name in ['../libc++.so','/base/libc++.so','base/../libc++.so','base\\libc++.so','base//libc++.so']:
            with self.subTest(name=name),self.assertRaises(candidate.CandidateError):p.binary_files(packed({name:b'x'}))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w')as z:
            z.writestr('base/libc++.so',b'x');z.writestr('BASE/LIBC++.SO',b'x')
        with self.assertRaises(candidate.CandidateError):p.binary_files(stream.getvalue())
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w')as z:
            info=zipfile.ZipInfo('base/libc++.so');info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,b'outside')
        with self.assertRaises(candidate.CandidateError):p.binary_files(stream.getvalue())

    def test_only_exact_unity_default_resources_space_path_is_accepted(self):
        p=self.parser()
        for name in ['base/assets/bin/Data/Resources/unity default resources','assets/bin/Data/Resources/unity default resources']:self.assertIn(name,p.binary_files(packed({name:b'unit'})))
        for name in ['base/assets/ arbitrary space','base/assets/bin/Data/Resources/../unity default resources',' unity default resources']:
            with self.assertRaises(candidate.CandidateError):p.binary_files(packed({name:b'unit'}))
