"""One M9 diagnostic: own edit create, ten fixed reads, own edit DELETE. No retry.
Default plan is offline. No arbitrary package/resource/upload/update/commit route.
Reports contain only fixed labels, HTTP status, numeric API code and RPC status enum.
"""
import argparse,hashlib,json,os,re,sys
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import HTTPRedirectHandler,Request,build_opener
PACKAGE='com.kamilunavo.maengelfix';BASE='/androidpublisher/v3/applications/'+PACKAGE+'/edits'
ROOT=Path(__file__).resolve().parent
CATALOG_SHA='ff7cf7b296c1fd84f758d26fc0cb27d546fbf997c41540ca697bcecf1270a958'
SOURCE_SHA='2bf664da1574d2e4291ed274a0e2cb562f7a5cb48c076e33b542f6fe8c4a8908'
MAX_RESPONSE=2*1024*1024
RESOURCES=('bundles','apks','tracks','listings','details','countryAvailability/production','listings/de-DE/phoneScreenshots','listings/de-DE/icon','listings/en-US/phoneScreenshots','listings/en-US/icon')
RPC_STATUSES=frozenset(('OK','CANCELLED','UNKNOWN','INVALID_ARGUMENT','DEADLINE_EXCEEDED','NOT_FOUND','ALREADY_EXISTS','PERMISSION_DENIED','RESOURCE_EXHAUSTED','FAILED_PRECONDITION','ABORTED','OUT_OF_RANGE','UNIMPLEMENTED','INTERNAL','UNAVAILABLE','DATA_LOSS','UNAUTHENTICATED'))
def check(v,message):
    if not v:raise ValueError(message)
def _unique(pairs):
    d={}
    for k,v in pairs:check(k not in d,'Duplicate JSON field');d[k]=v
    return d

def validate_catalog():
    for name,expected in [('business-catalog.json',CATALOG_SHA),('business-source-manifest.json',SOURCE_SHA)]:
        p=ROOT/name;check(p.is_file()and not p.is_symlink()and p.stat().st_size<=2*1024*1024,'Pinned metadata missing');raw=p.read_bytes();check(hashlib.sha256(raw).hexdigest()==expected,'Pinned metadata SHA mismatch')
        value=json.loads(raw,object_pairs_hook=_unique);check(type(value)is dict and type(value.get('schema'))is int and value['schema']==1,'Pinned metadata schema mismatch')
        if name=='business-catalog.json':
            apps=value.get('apps');check(type(apps)is list and len(apps)==12,'Closed twelve-app baseline missing');rows=[a for a in apps if a.get('package')==PACKAGE];check(len(rows)==1,'Exact M identity missing');app=rows[0]
            check(type(app.get('previousMaxCode'))is int and app['previousMaxCode']==8 and type(app.get('newVersionCode'))is int and app['newVersionCode']==9 and app.get('newVersionName')=='1.1.0'and app.get('reviewedSourceCommit')=='475cc69fe296a5ee1e484283697efe59144dac1e','Exact M8 to9 source identity mismatch')
    return True

def plan():return {'schema':1,'operation':'one_owned_edit_fixed_reads_delete_only','package':PACKAGE,'expectedPreviousMaxCode':8,'targetCode':9,'catalogSha256':CATALOG_SHA,'sourceManifestSha256':SOURCE_SHA,'resources':list(RESOURCES),'responseLimitBytes':MAX_RESPONSE,'readTimeoutSeconds':20,'deleteTimeoutSeconds':10,'retryAllowed':False,'uploadUpdateCommitAllowed':False,'providerObservedCodeClaim':False}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):return None

class Transport:
    def __init__(self,token,opener=None):
        check(type(token)is str and 0<len(token)<=16384 and '\r'not in token and '\n'not in token,'Missing access token');self._token=token;self._opener=opener if opener is not None else build_opener(NoRedirect());self._owned=None;self._created=False;self._deleted=False
    @property
    def owned(self):return self._owned
    def request(self,method,path,body=None):
        create=method=='POST'and path==BASE and body=={}and not self._created
        own=BASE+'/'+self._owned if self._owned else None
        read=method=='GET'and own is not None and body is None and path in {own+'/'+r for r in RESOURCES}
        delete=method=='DELETE'and own is not None and body is None and path==own and not self._deleted
        check(create or read or delete,'Method/package/resource outside dedicated M diagnostic')
        if create:self._created=True
        if delete:self._deleted=True
        request=Request('https://androidpublisher.googleapis.com'+path,data=b'{}'if create else None,method=method,headers={'Authorization':'Bearer '+self._token,'Content-Type':'application/json'})
        result={'httpStatus':None,'apiErrorCode':None,'apiErrorStatus':None,'protocolError':None}
        response=None
        try:
            try:response=self._opener.open(request,timeout=10 if delete else 20)
            except HTTPError as e:response=e
            status=getattr(response,'status',getattr(response,'code',None));check(type(status)is int and 100<=status<=599,'Invalid HTTP status');result['httpStatus']=status
            raw=response.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE:result['protocolError']='RESPONSE_LIMIT';return result
            if raw:
                try:value=json.loads(raw,object_pairs_hook=_unique)
                except (ValueError,UnicodeError):result['protocolError']='INVALID_JSON';return result
            else:value=None
            if type(value)is dict:
                error=value.get('error')
                if type(error)is dict:
                    code=error.get('code');rpc=error.get('status')
                    if type(code)is int and 100<=code<=599:result['apiErrorCode']=code
                    if type(rpc)is str and rpc in RPC_STATUSES:result['apiErrorStatus']=rpc
                if create and status==200:
                    owned=value.get('id')
                    if type(owned)is str and re.fullmatch(r'[A-Za-z0-9_-]{1,200}',owned):self._owned=owned
                    else:result['protocolError']='INVALID_EDIT_ID'
            elif create and status==200:result['protocolError']='INVALID_EDIT_ID'
            return result
        except (URLError,OSError,TimeoutError):result['protocolError']='NETWORK_ERROR';return result
        except ValueError:result['protocolError']='INVALID_RESPONSE';return result
        finally:
            if response is not None:
                close=getattr(response,'close',None)
                if close:close()

def diagnose(transport,report=None):
    report={}if report is None else report;report.update(plan());report.update(ownedEditCreated=False,resources=[],cleanup={'attempted':False,'confirmed':False,'httpStatus':None},outcome='create_failed_or_unknown')
    try:
        created=transport.request('POST',BASE,{})
        report['create']=created;report['ownedEditCreated']=transport.owned is not None
        if transport.owned is not None:report['ownedEditId']=transport.owned  # bounded own edit identity only, for manual cleanup if DELETE fails
        if transport.owned is None:return report
        for resource in RESOURCES:report['resources'].append({'resource':resource,**transport.request('GET',BASE+'/'+transport.owned+'/'+resource)})
        report['outcome']='all_reads_ok_owned_edit_deleted'if all(r['httpStatus']==200 and r['protocolError']is None for r in report['resources'])else'read_failed_owned_edit_deleted'
        return report
    finally:
        if transport.owned is not None:
            report['cleanup']['attempted']=True
            deleted=transport.request('DELETE',BASE+'/'+transport.owned);report['cleanup'].update(deleted);report['cleanup']['confirmed']=deleted['httpStatus']==204 and deleted['protocolError']is None
            if not report['cleanup']['confirmed']:report['outcome']='cleanup_failed_or_unknown'

def save_new(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode();check(len(raw)<=64*1024,'Safe report size bound');fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',nargs='?',choices=('plan','diagnose-once'),default='plan');parser.add_argument('--report',type=Path);args=parser.parse_args(argv)
    if args.mode=='plan':check(args.report is None,'Plan accepts no output path');print(json.dumps(plan(),indent=2));return 0
    check(args.report is not None and args.report.is_absolute(),'Absolute owned report path required');report_path=args.report;report_path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);check(not report_path.parent.is_symlink(),'Unsafe report directory');intent=report_path.parent/'diagnostic-intent.json';check(not report_path.exists()and not report_path.is_symlink()and not intent.exists()and not intent.is_symlink(),'Existing/unknown diagnostic; no retry')
    validate_catalog();check(os.environ.get('GITHUB_REPOSITORY')=='acciento89-bot/maengelfix'and os.environ.get('GITHUB_REF')=='refs/heads/main'and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'and os.environ.get('GITHUB_RUN_ATTEMPT')=='1'and re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')),'Only exact-main first manual diagnostic allowed')
    transport=Transport(os.environ.get('TOKEN',''));save_new(intent,{'schema':1,'status':'ONE_M_DIAGNOSTIC_CONSUMED_NO_RETRY','package':PACKAGE,'sourceCommit':os.environ['GITHUB_SHA'],'runId':os.environ.get('GITHUB_RUN_ID'),'catalogSha256':CATALOG_SHA,'targetCode':9})
    report={'schema':1,'sourceCommit':os.environ['GITHUB_SHA'],'runId':os.environ.get('GITHUB_RUN_ID')}
    try:diagnose(transport,report)
    except BaseException:report['interrupted']=True;report['outcome']='interrupted_cleanup_confirmed'if report.get('cleanup',{}).get('confirmed')else'cleanup_failed_or_unknown'
    save_new(report_path,report);print(json.dumps({'schema':1,'package':PACKAGE,'outcome':report['outcome'],'cleanupConfirmed':report['cleanup']['confirmed']}));return 0 if report['outcome']=='all_reads_ok_owned_edit_deleted'else 2
if __name__=='__main__':raise SystemExit(main())
