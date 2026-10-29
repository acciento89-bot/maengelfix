"""Closed NavoKids file-backed archives. No whole candidate/AAB/APK byte allocation."""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib,io,os,re,shutil,stat,tempfile,zipfile
from pathlib import Path
from candidate import CandidateError,require,safe_name
CHUNK=1024*1024
OUTER_MAX=1280*1024*1024
PINS={'aab':('24f9665f6cc495bf103bcb54a26782f9c7f983d3348fe73c6c05bc3d2173d561',350780306,10232),
      'apk':('35bd5d1fbf0812ecd05974a904065cd4f7a82e96a1396dd15f928098ddb48b3a',377068846,10196),
      'ci':('138aa405318e0a6c6952395c214603133a3c871ff2ceea4dc6ac3fccfe033363',349228029,4)}
_STORE=ContextVar('navokids_stream_store',default=None)
_CACHE=ContextVar('navokids_stream_cache',default=None)

def regular(path):
 p=Path(path);s=p.lstat();require(stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_nlink==1,'Archive link/special file rejected');return p,s

def signature(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def hash_path(path):
 p,s=regular(path);h=hashlib.sha256();count=0
 with p.open('rb')as stream:
  require(signature(os.fstat(stream.fileno()))==signature(s),'Archive changed before hash')
  for chunk in iter(lambda:stream.read(CHUNK),b''):h.update(chunk);count+=len(chunk)
  require(signature(os.fstat(stream.fileno()))==signature(s),'Archive changed during hash')
 require(count==s.st_size,'Archive size changed');return h.hexdigest(),signature(s)

class FileRef:
 def __init__(self,path,sha256,size,role):
  self.path,s=regular(path);require(type(size)is int and s.st_size==size and re.fullmatch('[a-f0-9]{64}',sha256)is not None,'Pinned archive size/hash invalid')
  if role in PINS:require((sha256,size)==PINS[role][:2],'Unknown NavoKids binary')
  else:require(role in('candidate','proof'),'Unknown stream role')
  observed,self._stat=hash_path(self.path);require(observed==sha256,'Pinned original archive SHA mismatch')
  self.sha256=sha256;self.size=size;self.role=role;self._body=None
 def stable(self):require(signature(regular(self.path)[1])==self._stat,'Pinned archive changed')
 def __len__(self):self.stable();return self.size
 def __eq__(self,other):
  if not isinstance(other,FileRef):return False
  self.stable();other.stable();return(self.sha256,self.size)==(other.sha256,other.size)
 def read(self,size=-1):
  require(type(size)is int and 0<=size<=CHUNK,'Unbounded large body read rejected');self.stable()
  if self._body is None:self._body=self.path.open('rb')
  return self._body.read(size)
 def close(self):
  if self._body is not None:self._body.close();self._body=None
 def copy_to(self,path):
  self.stable();target=Path(path)
  with self.path.open('rb')as source,target.open('xb')as out:shutil.copyfileobj(source,out,CHUNK)
  self.stable();require(hash_path(target)[0]==self.sha256,'Copied archive differs')

@contextmanager
def stream_store(base):
 base=Path(base);base.mkdir(parents=True,exist_ok=True);require(not base.is_symlink(),'Unsafe scratch directory')
 with tempfile.TemporaryDirectory(prefix='navokids-stream-',dir=base)as temp:
  token=_STORE.set(Path(temp));cache_token=_CACHE.set({})
  try:yield
  finally:_CACHE.reset(cache_token);_STORE.reset(token)

def zip_errors(fn):
 def guarded(*args,**kwargs):
  try:return fn(*args,**kwargs)
  except (zipfile.BadZipFile,RuntimeError,OSError,NotImplementedError):raise CandidateError('Invalid ZIP member')from None
 return guarded

class ZipMap(Mapping):
 def __init__(self,raw):
  self.raw=raw;self.cache={};self.role=raw.role if isinstance(raw,FileRef)else'metadata'
  if isinstance(raw,FileRef):
   raw.stable();require(self.role in('aab','apk','ci','candidate'),'Opaque proof ZIP cannot acquire parser privileges')
   if self.role=='candidate':require(0<len(raw)<=OUTER_MAX,'Candidate size outside closed limit')
   from zip_preflight import preflight
   with raw.path.open('rb')as directory_stream:self.preflight=preflight(directory_stream,len(raw),self.role)
   raw.stable();self.z=zipfile.ZipFile(raw.path)
  else:
   require(isinstance(raw,bytes)and 0<len(raw)<=16*1024*1024,'Small metadata ZIP size outside bounds')
   from zip_preflight import preflight
   self.preflight=preflight(io.BytesIO(raw),len(raw),self.role);self.z=zipfile.ZipFile(io.BytesIO(raw))
  infos=self.z.infolist();max_count=11000 if self.role in('aab','apk')else 128 if self.role=='candidate'else 5000
  require(0<len(infos)<=max_count,'Archive entry count outside bounds')
  if self.role in PINS:require(len(infos)==PINS[self.role][2],'Pinned binary entry count differs')
  self.info={};folded=set();total=0
  for i in infos:
   n=i.filename.rstrip('/')if i.is_dir()else i.filename
   if self.role in('aab','apk'):
    from business_binary import binary_name
    binary_name(n)
   else:safe_name(n)
   require(n.casefold()not in folded,'Duplicate or ambiguous ZIP entry');folded.add(n.casefold())
   mode=i.external_attr>>16;require(not stat.S_ISLNK(mode)and stat.S_IFMT(mode)in(0,stat.S_IFREG,stat.S_IFDIR),'ZIP link/special file rejected')
   require(not i.flag_bits&1 and i.compress_type in(zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'Encrypted/unsupported ZIP entry')
   cap=128*1024*1024
   if self.role=='candidate':
    role={'bundle/app.aab':'aab','qa/tested.apk':'apk','provenance/recovered-ci-artifact.zip':'ci'}.get(n)
    if role:require(i.file_size==PINS[role][1],'Large candidate member size differs');cap=PINS[role][1]
    elif n.startswith(('screens/','raw/')):cap=20*1024*1024
    elif n=='qa/root-native-original.zip':cap=128*1024*1024
    else:cap=16*1024*1024
   elif self.role=='ci':
    require(n in{'actual-manifest.xml','app-release.aab','provenance.json','upload-certificate.txt'},'Unexpected original CI member')
    cap=PINS['aab'][1]if n=='app-release.aab'else 16*1024*1024
    if n=='app-release.aab':require(i.file_size==PINS['aab'][1],'Original CI AAB member exact size differs')
   total+=i.file_size
   require(i.file_size<=cap and total<=(OUTER_MAX if self.role=='candidate'else 512*1024*1024),'Expanded archive too large')
   require(i.file_size<=max(i.compress_size,1)*500,'ZIP expansion ratio outside bounds')
   if not i.is_dir():self.info[n]=i
  if self.role=='ci':require(set(self.info)=={'actual-manifest.xml','app-release.aab','provenance.json','upload-certificate.txt'},'Missing original CI member')
 def __iter__(self):return iter(self.info)
 def __len__(self):return len(self.info)
 @zip_errors
 def entry_hash(self,name):
  h=hashlib.sha256();count=0
  with self.z.open(self.info[name])as source:
   for chunk in iter(lambda:source.read(CHUNK),b''):h.update(chunk);count+=len(chunk)
  require(count==self.info[name].file_size,'ZIP member expanded size differs');return h.hexdigest()
 @zip_errors
 def __getitem__(self,name):
  i=self.info[name]
  if i.file_size<=20*1024*1024:return self.z.read(i)
  if name in self.cache:self.cache[name].stable();return self.cache[name]
  cache=_CACHE.get();cache_key=(str(getattr(self.raw,'path','metadata')),getattr(self.raw,'sha256',''),name)
  if cache is not None and cache_key in cache:cache[cache_key].stable();self.cache[name]=cache[cache_key];return self.cache[name]
  role=({'bundle/app.aab':'aab','qa/tested.apk':'apk','provenance/recovered-ci-artifact.zip':'ci'}.get(name)if self.role=='candidate'else'aab'if self.role=='ci'and name=='app-release.aab'else'proof'if self.role=='candidate'and name=='qa/root-native-original.zip'else None)
  require(role is not None,'Unapproved large member');store=_STORE.get();require(store is not None,'Owned streaming scratch scope required')
  target=store/(hashlib.sha256((str(getattr(self.raw,'path','metadata'))+'!'+name).encode()).hexdigest()+'.bin');h=hashlib.sha256();count=0
  with self.z.open(i)as source,target.open('xb')as out:
   for chunk in iter(lambda:source.read(CHUNK),b''):count+=len(chunk);require(count<=i.file_size,'ZIP expansion overflow');h.update(chunk);out.write(chunk)
  require(count==i.file_size,'Truncated ZIP member');observed=h.hexdigest()
  if role in PINS:require(observed==PINS[role][0],'Large pinned member SHA differs')
  self.cache[name]=FileRef(target,observed,count,role)
  if cache is not None:cache[cache_key]=self.cache[name]
  return self.cache[name]
 def close(self):self.z.close()

def mapping(raw):
 try:return ZipMap(raw)
 except (zipfile.BadZipFile,RuntimeError,OSError,NotImplementedError):raise CandidateError('Invalid ZIP')from None
