"""Fake-transport-only tests; no own provider/token/network used."""
from pathlib import Path
import importlib.util,io,json,sys,unittest
from urllib.error import HTTPError
P=Path(__file__).parents[1]/'diagnose_maengelfix_snapshot.py'
spec=importlib.util.spec_from_file_location('m_diagnostic',P);d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
class Reply:
 def __init__(self,status=200,value=None,raw=None):self.status=status;self.raw=raw if raw is not None else json.dumps(value).encode();self.reads=[]
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):self.reads.append(n);return self.raw[:n]
class Opener:
 def __init__(self,read_status=200,delete_status=204,create_error=False):self.calls=[];self.read_status=read_status;self.delete_status=delete_status;self.create_error=create_error
 def open(self,r,timeout):
  self.calls.append((r.get_method(),r.full_url,timeout))
  if r.get_method()=='POST':
   if self.create_error:raise OSError('PRIVATE_SENTINEL')
   return Reply(200,{'id':'owned-edit-fixture'})
  if r.get_method()=='DELETE':return Reply(self.delete_status,raw=b'')
  if self.read_status==404:raise HTTPError(r.full_url,404,'PRIVATE_SENTINEL',{},io.BytesIO(json.dumps({'error':{'code':404,'status':'NOT_FOUND','message':'PRIVATE_SENTINEL'}}).encode()))
  return Reply(200,{})
class DiagnosticTests(unittest.TestCase):
 def transport(self,**kwargs):o=Opener(**kwargs);return d.Transport('PUBLIC_DUMMY',opener=o),o
 def test_closed_plan_offline(self):self.assertEqual(d.plan()['package'],'com.kamilunavo.maengelfix');self.assertEqual(len(d.plan()['resources']),10);self.assertEqual(d.plan()['expectedPreviousMaxCode'],8)
 def test_success_reads_exact_ten_then_deletes_owned_edit(self):
  t,o=self.transport();r=d.diagnose(t);self.assertTrue(r['cleanup']['confirmed']);self.assertEqual(r['outcome'],'all_reads_ok_owned_edit_deleted');self.assertEqual([m for m,u,t in o.calls],['POST']+['GET']*10+['DELETE'])
 def test_wrong_package_path_and_mutating_methods_reject_before_network(self):
  t,o=self.transport()
  for method,path,body in [('POST',d.BASE.replace('maengelfix','other'),{}),('GET',d.BASE+'/foreign/tracks',None),('POST',d.BASE+'/owned-edit-fixture:commit',None),('PUT',d.BASE+'/owned-edit-fixture/tracks/production',{}),('GET',d.BASE+'?x=1',None)]:
   with self.subTest(method=method,path=path),self.assertRaises(ValueError):t.request(method,path,body)
  self.assertEqual(o.calls,[])
 def test_http404_reports_only_numeric_and_enum_and_still_cleanup(self):
  t,o=self.transport(read_status=404);r=d.diagnose(t);self.assertEqual(len(r['resources']),10);self.assertTrue(r['cleanup']['confirmed']);self.assertTrue(all(x['httpStatus']==404 and x['apiErrorCode']==404 and x['apiErrorStatus']=='NOT_FOUND'for x in r['resources']));self.assertNotIn('PRIVATE_SENTINEL',json.dumps(r));self.assertNotEqual(r['outcome'],'all_reads_ok_owned_edit_deleted')
 def test_cleanup_failure_is_explicit_and_not_retried(self):
  t,o=self.transport(delete_status=500);r=d.diagnose(t);self.assertFalse(r['cleanup']['confirmed']);self.assertEqual(r['outcome'],'cleanup_failed_or_unknown');self.assertEqual(r['ownedEditId'],'owned-edit-fixture');self.assertEqual(sum(m=='DELETE'for m,u,z in o.calls),1)
 def test_unknown_create_never_retries_and_cannot_claim_cleanup(self):
  t,o=self.transport(create_error=True);r=d.diagnose(t);self.assertFalse(r['ownedEditCreated']);self.assertFalse(r['cleanup']['confirmed']);self.assertEqual(len(o.calls),1)
  with self.assertRaises(ValueError):t.request('POST',d.BASE,{})
 def test_max_byte_response_rejected_no_raw_body_or_url(self):
  t,o=self.transport();t.request('POST',d.BASE,{})
  reply=Reply(200,raw=b'PRIVATE_SENTINEL'+b'x'*d.MAX_RESPONSE);o.open=lambda r,timeout:reply
  r=t.request('GET',d.BASE+'/owned-edit-fixture/bundles');self.assertEqual(r['protocolError'],'RESPONSE_LIMIT');self.assertEqual(reply.reads,[d.MAX_RESPONSE+1]);self.assertNotIn('PRIVATE_SENTINEL',json.dumps(r));self.assertNotIn('https',json.dumps(r))
 def test_error_status_is_allowlisted_not_arbitrary_text(self):
  t,o=self.transport();t.request('POST',d.BASE,{})
  o.open=lambda r,timeout:Reply(400,{'error':{'code':'400','status':'PRIVATE_SENTINEL','message':'PRIVATE_SENTINEL'}})
  r=t.request('GET',d.BASE+'/owned-edit-fixture/apks');self.assertIsNone(r['apiErrorCode']);self.assertIsNone(r['apiErrorStatus']);self.assertNotIn('PRIVATE_SENTINEL',json.dumps(r))
 def test_non_owned_edit_or_resource_never_read_or_delete(self):
  t,o=self.transport();t.request('POST',d.BASE,{})
  for method,path in [('GET',d.BASE+'/other/bundles'),('DELETE',d.BASE+'/other'),('GET',d.BASE+'/owned-edit-fixture/users'),('DELETE',d.BASE+'/owned-edit-fixture/listings/de-DE/icon')]:
   with self.subTest(path=path),self.assertRaises(ValueError):t.request(method,path)
  self.assertEqual(len(o.calls),1)
 def test_interrupted_read_finally_deletes_owned_edit(self):
  t,o=self.transport();original=o.open
  def open_(r,timeout):
   if r.get_method()=='GET':raise KeyboardInterrupt()
   return original(r,timeout)
  o.open=open_
  with self.assertRaises(KeyboardInterrupt):d.diagnose(t)
  self.assertEqual(o.calls[-1][0],'DELETE')
 def test_no_token_or_raw_error_in_safe_report(self):
  t,o=self.transport(read_status=404);r=d.diagnose(t);text=json.dumps(r);self.assertNotIn('PUBLIC_DUMMY',text);self.assertNotIn('Authorization',text);self.assertNotIn('https://',text)
 def test_readonly_context_exact_pins(self):self.assertTrue(d.validate_catalog())
if __name__=='__main__':unittest.main(verbosity=2)

class DurableAndTimeoutTests(unittest.TestCase):
 def test_exclusive_report_or_intent_cannot_be_overwritten(self):
  import tempfile
  with tempfile.TemporaryDirectory(prefix='m-diagnostic-fixture-')as t:
   p=Path(t)/'intent.json';d.save_new(p,{'fixture':True})
   with self.assertRaises(FileExistsError):d.save_new(p,{'fixture':False})
   self.assertEqual(json.loads(p.read_text()),{'fixture':True})
 def test_all_actual_transport_timeouts_are_bounded(self):
  o=Opener();d.diagnose(d.Transport('PUBLIC_DUMMY',opener=o));self.assertEqual([timeout for method,url,timeout in o.calls],[20]*11+[10])
