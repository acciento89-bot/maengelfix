"""Explicit fake transports only: no provider, auth, engine or native QA actions."""
import copy,hashlib,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import candidate,stream_zip,business_policy,release_asset,cli,publisher
PKG='com.kamilunavo.navokids';ROOT=business_policy.ROOT
ENV={'GITHUB_REPOSITORY':'acciento89-bot/maengelfix','GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-navokids-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_NAVOKIDS_OPERATION':'inspect'}
class Response:
 def __init__(self,raw):self.raw=io.BytesIO(raw);self.status=200;self.read_sizes=[]
 def read(self,n):self.read_sizes.append(n);return self.raw.read(n)
 def __enter__(self):return self
 def __exit__(self,*args):pass
class EntrypointTests(unittest.TestCase):
 def test_workflow_closed_manual_default_inspect_google_free_prepare(self):
  path=ROOT.parent/'workflows/navoops-navokids-production-submit.yml';w=json.loads(path.read_text());self.assertEqual(set(w['on']),{'workflow_dispatch'});i=w['on']['workflow_dispatch']['inputs'];self.assertEqual(i['package']['options'],[PKG]);self.assertEqual(i['package']['default'],PKG);self.assertEqual(i['operation']['default'],'inspect');self.assertNotIn('id-token',w['jobs']['prepare']['permissions'])
  self.assertTrue(all('workflow_dispatch'in j['if']and'run_attempt == 1'in j['if']and'refs/heads/main'in j['if']for j in w['jobs'].values()));steps=w['jobs']['submit']['steps'];verify=next(n for n,s in enumerate(steps)if 'verify-transfer'in s.get('run',''));auth=next(n for n,s in enumerate(steps)if s.get('id')=='google-auth');self.assertLess(verify,auth)
  body=str(w['jobs']['inspect']);self.assertNotIn('setup-java',body);self.assertNotIn('candidate_asset_id',body);self.assertNotIn('prepare --package',body)
 def test_real_pending_inspect_only_owned_post_get_delete_no_candidate_crypto(self):
  class ReadOnly:
   def __init__(self):self.calls=[]
   def request(self,method,path,body=None,media=None):
    self.calls.append((method,path))
    if method=='POST':return publisher.Response(200,{'id':'owned-unit'})
    if method=='GET':return publisher.Response(200,{'listings':[{'language':'de-DE'},{'language':'en-US'}]})
    return publisher.Response(204)
  fake=ReadOnly()
  with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,ENV,clear=True),patch.object(cli,'HttpTransport',return_value=fake),patch.object(cli,'GitHubClient',side_effect=AssertionError('No candidate API in inspect'))as gh,patch.object(cli,'BundleVerifier',side_effect=AssertionError('No Java in inspect'))as java:
   code=cli.main(['inspect','--package',PKG,'--catalog-sha256',candidate.digest((ROOT/'navokids-catalog.json').read_bytes()),'--report',str(Path(temp)/'report.json')],family='navokids1');self.assertEqual(code,0);gh.assert_not_called();java.assert_not_called();self.assertEqual([m for m,p in fake.calls],['POST','GET','DELETE']);self.assertTrue(json.loads((Path(temp)/'report.json').read_text())['apps'][0]['cleanup']['confirmed'])
 def test_context_denies_old_business_ios_push_attempt_and_other_repo(self):
  cli.execution_context(ENV,family='navokids1')
  for key,value in [('GITHUB_EVENT_NAME','push'),('GITHUB_REF','refs/tags/release'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_REPOSITORY','other/repo'),('GITHUB_WORKFLOW_REF',ENV['GITHUB_WORKFLOW_REF'].replace('navokids','business'))]:
   with self.subTest(key=key),self.assertRaises(candidate.CandidateError):cli.execution_context({**ENV,key:value},family='navokids1')
 def test_file_backed_upload_has_exact_content_length_and_bounded_reads(self):
  raw=b'UNIT-ONLY-BINARY\x00\xff';sha=candidate.digest(raw)
  class Opener:
   def open(self,request,timeout):
    self.request=request;body=[]
    while True:
     chunk=request.data.read(8192)
     if not chunk:break
     body.append(chunk)
    self.body=b''.join(body);return Response(b'{"versionCode":9}')
  with tempfile.TemporaryDirectory()as temp,patch.dict(stream_zip.PINS,{'aab':(sha,len(raw),1)}):
   p=Path(temp)/'unit';p.write_bytes(raw);ref=stream_zip.FileRef(p,sha,len(raw),'aab');cat={PKG:{'listingLocales':['de-DE','en-US'],'localeSnapshotSha256':'a'*64,'releaseNotes':{'de-DE':'Unit only','en-US':'Unit only'}}};http=publisher.HttpTransport('UNIT_ONLY_TOKEN',cat,inspect_only=False,family='navokids1');op=Opener();http._opener=op
   result=http.request('POST','/upload/androidpublisher/v3/applications/'+PKG+'/edits/owned-unit/bundles?uploadType=media',media=publisher.MediaPayload(ref,'application/octet-stream'));self.assertEqual(result.status,200);self.assertEqual(op.request.get_header('Content-length'),str(len(raw)));self.assertIs(op.request.data,ref);self.assertEqual(op.body,raw);ref.close()
 def test_stream_download_cdn_does_not_receive_repo_token_and_hash_mismatch_stops(self):
  raw=b'UNIT-ONLY-DOWNLOAD';sha=candidate.digest(raw)
  class Opener:
   def __init__(self,location):self.location=location;self.requests=[];self.response=Response(raw)
   def open(self,request,timeout):
    self.requests.append(request)
    if len(self.requests)==1:raise HTTPError(request.full_url,307,'unit',{'Location':self.location},None)
    return self.response
  with tempfile.TemporaryDirectory()as temp,stream_zip.stream_store(temp):
   c=release_asset.GitHubClient('UNIT_ONLY_TOKEN',family='navokids1');op=Opener('https://release-assets.githubusercontent.com/unit?sig=UNIT_NOT_A_SECRET');c._opener=op;ref=c.download_asset(42,sha,len(raw));self.assertEqual(ref.sha256,sha);self.assertFalse(any(k.lower()=='authorization'for k in op.requests[1].headers));self.assertTrue(all(n<=stream_zip.CHUNK for n in op.response.read_sizes))
  with tempfile.TemporaryDirectory()as temp,stream_zip.stream_store(temp):
   c=release_asset.GitHubClient('UNIT_ONLY_TOKEN',family='navokids1');op=Opener('https://evil.invalid/unit');c._opener=op
   with self.assertRaises(candidate.CandidateError):c.download_asset(42,sha,len(raw))
   self.assertEqual(len(op.requests),1)
 def test_stream_download_wrong_exact_sha_rejected(self):
  raw=b'UNIT-ONLY-UNAPPROVED-BODY'
  class Opener:
   def open(self,request,timeout):return Response(raw)
  with tempfile.TemporaryDirectory()as temp,stream_zip.stream_store(temp):
   c=release_asset.GitHubClient('UNIT_ONLY_TOKEN',family='navokids1');c._opener=Opener()
   with self.assertRaises(candidate.CandidateError):c.download_asset(42,'0'*64,len(raw))
 def test_current_metadata_original_failure_cannot_be_renamed_success_or_recovery(self):
  app=business_policy.registry();proof={r['role']:candidate.strict_json((ROOT/r['path']).read_bytes())for r in app['sourceProofs']};base='/repos/acciento89-bot/navokids/actions/';data={base+'runs/40912063730':proof['original-failed-run'],base+'runs/40926938191':proof['recovery-success-run'],base+'artifacts/12921086708':proof['recovery-result']['artifact']}
  class Git:
   def json(self,path):return copy.deepcopy(self.data[path])
  g=Git();g.data=copy.deepcopy(data)
  with patch.object(release_asset,'require_ready',return_value=None):
   c=type('MetadataUnitOnly',(),{'app':app,'package':PKG})();self.assertEqual(release_asset.verify_provenance(g,c)['originalFailedSourceRunId'],40912063730)
   for route,key,value in [(base+'runs/40912063730','conclusion','success'),(base+'runs/40926938191','conclusion','failure'),(base+'runs/40926938191','run_attempt',True),(base+'artifacts/12921086708','expired',True),(base+'artifacts/12921086708','digest','sha256:'+'0'*64)]:
    g.data=copy.deepcopy(data);g.data[route][key]=value
    with self.subTest(key=key,value=value),self.assertRaises(candidate.CandidateError):release_asset.verify_provenance(g,c)
 def test_receipt_cap_stays_16mib_and_no_file_written_on_excess(self):
  with tempfile.TemporaryDirectory()as temp:
   p=Path(temp)/'receipt.json'
   with self.assertRaises(candidate.CandidateError):cli.write_receipt(p,{'unitOnly':'x'*(16*1024*1024)})
   self.assertFalse(p.exists())
