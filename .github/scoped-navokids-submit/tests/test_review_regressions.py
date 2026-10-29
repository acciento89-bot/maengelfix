"""Frozen independent review regressions; tiny archives and owned temporary receipts only."""
import io,json,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import candidate,stream_zip,cli,business_policy
LIMIT=16*1024*1024

def archive(count=1):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w')as z:
  for i in range(count):z.writestr('item'+str(i),b'UNIT')
 return b.getvalue()

def zip64_end(raw):
 pos=raw.rfind(b'PK\x05\x06');end=list(struct.unpack('<4s4H2IH',raw[pos:pos+22]));count,size,offset=end[4:7]
 record=struct.pack('<4sQ2H2I4Q',b'PK\x06\x06',44,45,45,0,0,count,count,size,offset)
 locator=struct.pack('<4sIQI',b'PK\x06\x07',0,pos,1)
 end[3]=end[4]=0xffff;end[5]=end[6]=0xffffffff
 return raw[:pos]+record+locator+struct.pack('<4s4H2IH',*end)

class ReviewRegressionTests(unittest.TestCase):
 def test_workflow_both_real_commands_establish_own_import_path(self):
  w=json.loads((business_policy.ROOT.parent/'workflows/navoops-navokids-production-submit.yml').read_text());count=0
  for job in ['inspect','prepare']:
   for step in w['jobs'][job]['steps']:
    if 'unittest discover'in step.get('run',''):
     count+=1;self.assertIn('env PYTHONPATH=.github/scoped-navokids-submit python3 -m unittest',step['run']);self.assertNotIn('/Volumes/',step['run'])
  self.assertEqual(count,2)
 def rejected_before_constructor(self,raw,role='metadata'):
  with tempfile.TemporaryDirectory()as temp:
   if role=='candidate':
    p=Path(temp)/'unit.zip';p.write_bytes(raw);value=stream_zip.FileRef(p,candidate.digest(raw),len(raw),'candidate')
   else:value=raw
   with patch.object(stream_zip.zipfile,'ZipFile',side_effect=AssertionError('stdlib metadata allocation happened before bounds'))as constructor:
    with self.assertRaises(candidate.CandidateError):stream_zip.mapping(value)
    constructor.assert_not_called()
 def test_129_outer_members_rejected_before_stdlib_constructor(self):self.rejected_before_constructor(archive(129),'candidate')
 def test_oversized_central_directory_rejected_before_stdlib_constructor(self):
  raw=bytearray(archive());pos=raw.rfind(b'PK\x05\x06');struct.pack_into('<I',raw,pos+12,100*1024*1024);self.rejected_before_constructor(bytes(raw))
 def test_lying_member_count_rejected_before_stdlib_constructor(self):
  raw=bytearray(archive(2));pos=raw.rfind(b'PK\x05\x06');struct.pack_into('<H',raw,pos+8,1);struct.pack_into('<H',raw,pos+10,1);self.rejected_before_constructor(bytes(raw))
 def test_long_name_extra_comment_metadata_rejected_before_stdlib_constructor(self):
  for offset in [28,30,32]:
   raw=bytearray(archive());c=raw.index(b'PK\x01\x02');struct.pack_into('<H',raw,c+offset,0xffff)
   with self.subTest(offset=offset):self.rejected_before_constructor(bytes(raw))
 def test_bad_central_offset_and_multidisk_rejected_before_constructor(self):
  raw=bytearray(archive());p=raw.rfind(b'PK\x05\x06');struct.pack_into('<I',raw,p+16,0xffffffff);self.rejected_before_constructor(bytes(raw))
  raw=bytearray(archive());p=raw.rfind(b'PK\x05\x06');struct.pack_into('<H',raw,p+4,1);self.rejected_before_constructor(bytes(raw))
 def test_zip32_zip64_end_and_forcezip64_local_stay_compatible(self):
  for raw in [archive(),zip64_end(archive())]:
   z=stream_zip.mapping(raw);self.assertEqual(z['item0'],b'UNIT');z.close()
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w')as z:
   with z.open('local64','w',force_zip64=True)as entry:entry.write(b'UNIT')
  z=stream_zip.mapping(out.getvalue());self.assertEqual(z['local64'],b'UNIT');z.close()
 def test_bad_zip64_locator_rejected_before_constructor(self):
  raw=bytearray(zip64_end(archive()));p=raw.index(b'PK\x06\x07');struct.pack_into('<Q',raw,p+8,2**63);self.rejected_before_constructor(bytes(raw))
 def test_receipt_exact_final_cap_allowed_and_bytes_identical(self):
  overhead=len((json.dumps({'x':''},sort_keys=True,indent=2)+'\n').encode());report={'x':'a'*(LIMIT-overhead)};expected=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode();self.assertEqual(len(expected),LIMIT)
  with tempfile.TemporaryDirectory()as temp:
   p=Path(temp)/'receipt.json';cli.write_receipt(p,report);self.assertEqual(p.read_bytes(),expected)
 def test_compact_under_cap_but_final_cap_plus_one_rejected_preserves_existing(self):
  overhead=len((json.dumps({'x':''},sort_keys=True,indent=2)+'\n').encode());report={'x':'a'*(LIMIT+1-overhead)};self.assertLess(len(json.dumps(report).encode()),LIMIT);self.assertEqual(len((json.dumps(report,sort_keys=True,indent=2)+'\n').encode()),LIMIT+1)
  with tempfile.TemporaryDirectory()as temp:
   p=Path(temp)/'receipt.json';p.write_bytes(b'EXISTING-OWNED-RECEIPT\n')
   with self.assertRaises(candidate.CandidateError):cli.write_receipt(p,report)
   self.assertEqual(p.read_bytes(),b'EXISTING-OWNED-RECEIPT\n');self.assertEqual([q.name for q in Path(temp).iterdir()],['receipt.json'])
 def test_zip64_central_size_and_offset_values_stay_compatible(self):
  raw=archive();c=raw.index(b'PK\x01\x02');e=raw.rfind(b'PK\x05\x06');fixed=bytearray(raw[c:c+46]);name_len=struct.unpack_from('<H',fixed,28)[0];compressed=struct.unpack_from('<I',fixed,20)[0];expanded=struct.unpack_from('<I',fixed,24)[0];offset=struct.unpack_from('<I',fixed,42)[0]
  extra=struct.pack('<HHQQQ',1,24,expanded,compressed,offset);struct.pack_into('<I',fixed,20,0xffffffff);struct.pack_into('<I',fixed,24,0xffffffff);struct.pack_into('<I',fixed,42,0xffffffff);struct.pack_into('<H',fixed,30,len(extra))
  end=bytearray(raw[e:]);old_size=struct.unpack_from('<I',end,12)[0];struct.pack_into('<I',end,12,old_size+len(extra));patched=raw[:c]+bytes(fixed)+raw[c+46:c+46+name_len]+extra+bytes(end)
  z=stream_zip.mapping(patched);self.assertEqual(z['item0'],b'UNIT');z.close()
 def test_oversized_directory_preflight_reads_only_bounded_tail_and_locator(self):
  from zip_preflight import preflight,MAX_TAIL
  raw=bytearray(archive());e=raw.rfind(b'PK\x05\x06');struct.pack_into('<I',raw,e+12,100*1024*1024)
  class Spy(io.BytesIO):
   def __init__(self,value):super().__init__(value);self.reads=[]
   def read(self,n=-1):self.reads.append((self.tell(),n));self_outer.assertTrue(0<=n<=MAX_TAIL);return super().read(n)
  self_outer=self;s=Spy(bytes(raw))
  with patch.object(stream_zip.zipfile,'ZipFile',side_effect=AssertionError('No stdlib allocation'))as constructor,self.assertRaisesRegex(candidate.CandidateError,'Central directory byte limit'):preflight(s,len(raw),'metadata')
  constructor.assert_not_called();self.assertLessEqual(len(s.reads),2);self.assertLessEqual(max(n for _,n in s.reads),MAX_TAIL)
