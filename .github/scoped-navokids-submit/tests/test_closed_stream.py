"""Small CPU adversarial controls; real fixed binaries are tested separately, not shipped in tests."""
import copy,io,json,os,stat,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import candidate,business_policy,business_binary,stream_zip,release_asset,cli,publisher
PKG='com.kamilunavo.navokids'
def packed(rows,compression=zipfile.ZIP_STORED):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',compression=compression)as z:
  for n,data in rows:z.writestr(n,data)
 return b.getvalue()
class ClosedStreamTests(unittest.TestCase):
 def test_only_exact_one_family_and_pending_catalog_no_root_approval(self):
  raw=(business_policy.ROOT/'navokids-catalog.json').read_bytes();cat=business_policy.load_catalog(business_policy.ROOT/'navokids-catalog.json',candidate.digest(raw));self.assertEqual(set(cat),{PKG})
  # Pending is an explicit adversarial fixture, independent of the real catalog's
  # later, separately reviewed root approval. Keep the original rejection gate.
  pending=copy.deepcopy(cat[PKG]);pending.update(readiness='pending_final_native_screens_locales_rights_root_review',rootReviewSha256=None,rightsEvidenceSha256=None,archiveApproval=None)
  self.assertIsNone(pending['archiveApproval'])
  with self.assertRaises(candidate.CandidateError):business_policy.require_ready(pending)
  for family in ['calculator9','business12','game5','all','navokids']:
   with self.subTest(family=family),self.assertRaises(candidate.CandidateError):business_policy.scope(family)
 def test_current_real_catalog_binds_separate_root_inputs_rights_and_exact_archive(self):
  raw=(business_policy.ROOT/'navokids-catalog.json').read_bytes();app=business_policy.load_catalog(business_policy.ROOT/'navokids-catalog.json',candidate.digest(raw))[PKG]
  self.assertEqual(app['readiness'],'root_reviewed_candidate_inputs');self.assertEqual(app['rootReviewSha256'],'c479c0cb27f238c813101dfd2a8fcdb397e48c6dd9b71fad4c1bf47ed296d39f');self.assertEqual(app['rightsEvidenceSha256'],'8f7c764f9c535f070941c84938d9a29b8ebb39c8bd8889bbda6131790caf3089')
  approval=app['archiveApproval'];self.assertEqual(approval['reviewer'],'root');self.assertEqual(approval['outcome'],'approved_exact_navokids_candidate_archive');self.assertEqual(approval['candidateSha256'],'23766eb3f1fd4f38fd92669df4b3995ab315b01ac153b09ef16ac18f58e515e3');self.assertEqual(approval['candidateBytes'],1100106686)
  missing=copy.deepcopy(app);missing['archiveApproval']=None
  with self.assertRaises(candidate.CandidateError):business_policy.require_ready(missing)
 def test_known_binary_tuple_is_checked_before_any_large_hash(self):
  with patch.object(stream_zip,'regular',return_value=(Path('/unit-only'),SimpleNamespace(st_size=350780306))),patch.object(stream_zip,'hash_path',side_effect=AssertionError('Must reject first'))as h,self.assertRaises(candidate.CandidateError):stream_zip.FileRef('/unit-only','0'*64,350780306,'aab')
  h.assert_not_called()
 def test_path_aliases_case_collision_links_and_special_rejected(self):
  for n in ['../x','/x','a/../x','a//x','a\\x','a/./x','x%2fy']:
   with self.subTest(n=n),self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([(n,b'x')]))
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([('a',b'x'),('A',b'y')]))
  for mode in [stat.S_IFLNK,stat.S_IFCHR,stat.S_IFIFO]:
   i=zipfile.ZipInfo('a');i.external_attr=(mode|0o644)<<16
   with self.subTest(mode=mode),self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([(i,b'x')]))
 def test_encrypted_unsupported_count_ratio_and_member_size_limits(self):
  raw=bytearray(packed([('x',b'x')]));c=raw.index(b'PK\x01\x02');struct.pack_into('<H',raw,c+8,1)
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(bytes(raw))
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([('x',b'x')],zipfile.ZIP_BZIP2))
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([(str(i),b'x')for i in range(5001)]))
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([('x',b'0'*1_000_000)],zipfile.ZIP_DEFLATED))
  raw=bytearray(packed([('x',b'x')]));c=raw.index(b'PK\x01\x02');struct.pack_into('<I',raw,c+24,128*1024*1024+1)
  with self.assertRaises(candidate.CandidateError):stream_zip.mapping(bytes(raw))
 def test_no_large_or_dollar_plus_exception_for_outer_or_metadata(self):
  for n in ['lib/arm64-v8a/libc++_shared.so','res/drawable/$avd_hide_password__0.xml','qa/voice+anything.aac']:
   with self.subTest(n=n),self.assertRaises(candidate.CandidateError):stream_zip.mapping(packed([(n,b'x')]))
  business_binary.binary_name('base/lib/arm64-v8a/libc++_shared.so')
  with self.assertRaises(candidate.CandidateError):business_binary.binary_name('base/assets/surprise+.bin')
 def test_file_ref_no_unbounded_body_allocation_and_mutation_rejected(self):
  with tempfile.TemporaryDirectory()as temp:
   p=Path(temp)/'unit';p.write_bytes(b'UNIT-ONLY');ref=stream_zip.FileRef(p,candidate.digest(b'UNIT-ONLY'),9,'candidate')
   with self.assertRaises(candidate.CandidateError):ref.read()
   self.assertEqual(ref.read(4),b'UNIT');ref.close();p.write_bytes(b'CHANGED!!')
   with self.assertRaises(candidate.CandidateError):ref.stable()
 def test_metadata_routes_only_exact_original_failure_recovery_success_artifact(self):
  for route in ['/repos/acciento89-bot/navokids/actions/runs/40912063730','/repos/acciento89-bot/navokids/actions/runs/40926938191','/repos/acciento89-bot/navokids/actions/artifacts/12921086708']:release_asset.metadata_route(route,'navokids1')
  for route in ['/repos/acciento89-bot/navokids/actions/runs/42','/repos/acciento89-bot/SHK/actions/runs/40926938191','/repos/acciento89-bot/navokids/actions/runs/40912063730/rerun','https://evil.invalid']:
   with self.subTest(route=route),self.assertRaises(candidate.CandidateError):release_asset.metadata_route(route,'navokids1')
 def test_source_evidence_original_failure_and_uuid_chain_fixed(self):
  app=business_policy.registry();files={r['path']:(business_policy.ROOT/r['path']).read_bytes()for r in app['sourceProofs']};m={'sourceEvidence':{r['role']:{'path':r['path'],'sha256':r['sha256']}for r in app['sourceProofs']}}
  self.assertEqual(len(business_policy.verify_source_evidence(app,m,files)),10)
  for role in ['original-failed-run','root-recovery-approval','original-job-uuid-linkage','recovery-success-run']:
   changed=dict(files);changed[m['sourceEvidence'][role]['path']]+=b'changed'
   with self.subTest(role=role),self.assertRaises(candidate.CandidateError):business_policy.verify_source_evidence(app,m,changed)
 def test_managed_certificate_and_normal_false_cannot_join_recovered_route(self):
  app=copy.deepcopy(business_policy.registry());app['certificate']['sha256']=candidate.CENTRAL_SHA256
  with self.assertRaises(candidate.CandidateError):business_policy.assert_identity(app)
  for key,value in [('easBuildID','00000000-0000-0000-0000-000000000000'),('sourceCommit','0'*40),('signedAabSha256','0'*64),('originalFailedRunId',40926938191)]:
   a=copy.deepcopy(business_policy.registry());a[key]=value
   with self.subTest(key=key),self.assertRaises(candidate.CandidateError):business_policy.assert_identity(a)
 def test_pending_prepare_stops_before_client_bundletool_or_large_read(self):
  env={'GITHUB_REPOSITORY':'acciento89-bot/maengelfix','GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-navokids-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_NAVOKIDS_OPERATION':'submit'}
  with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,env,clear=True),patch.object(cli,'GitHubClient',side_effect=AssertionError('No client while pending'))as client,patch.object(stream_zip,'hash_path',side_effect=AssertionError('No big read while pending')):
   code=cli.main(['prepare','--package',PKG,'--catalog-sha256',candidate.digest((business_policy.ROOT/'navokids-catalog.json').read_bytes()),'--report',str(Path(temp)/'report.json'),'--archive-sha256','a'*64,'--bundletool','NOT_READ','--bundletool-sha256','b'*64],family='navokids1');self.assertEqual(code,2);client.assert_not_called()

 def test_bad_crc_is_controlled_candidate_error(self):
  raw=bytearray(packed([('data',b'UNIT-CONTENT')]))
  pos=raw.index(b'UNIT-CONTENT');raw[pos]=ord('X');z=stream_zip.mapping(bytes(raw))
  with self.assertRaises(candidate.CandidateError):z['data']
  with self.assertRaises(candidate.CandidateError):z.entry_hash('data')
  z.close()
 def test_generic_normal_false_provenance_cannot_enter_exact_recovered_route(self):
  app=business_policy.registry();p={'repository':app['repository'],'sourceCommit':app['reviewedSourceCommit'],'workflowCommit':app['reviewedSourceCommit'],'recoveredFinishedBuild':False,'workflowRun':'40926938191','easBuildID':app['easBuildID'],'easStatus':'FINISHED','version':'0.6.0','versionCode':9,'package':PKG,'managedCredentials':True,'credentialsFrozen':True,'storeSubmission':False,'easConfigOverrideOnly':{'appVersionSource':'local','profile':'portfolioAndroid','autoIncrement':False},'aabSHA256':app['signedAabSha256']}
  m={'source':{'runId':40926938191,'artifactId':12921086708,'artifactArchiveSha256':app['originalCiArchiveSha256'],'archive':'provenance/recovered-ci-artifact.zip'}}
  with self.assertRaisesRegex(candidate.CandidateError,'Recovered provenance'):business_policy.verify_business_provenance(app,m,p,app['signedAabSha256'],{})
