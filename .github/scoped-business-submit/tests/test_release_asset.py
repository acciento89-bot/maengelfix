import copy, unittest
from fixtures import Fixture, Verifier, PACKAGE, NOW, digest
import candidate, release_asset

OWN = 'acciento89-bot/maengelfix'
class GitHub:
    def __init__(self, fixture):
        self.raw=fixture.raw();self.calls=[];self.downloads=[];self.download_contexts=[];self.data={};self.expected_package=fixture.app['package'];self.expected_app=copy.deepcopy(fixture.app)
        a=fixture.app
        self.asset={'id':91,'name':'calculator-candidate-'+PACKAGE+'-1.2.0-'+str(a['newVersionCode'])+'.zip','size':len(self.raw),'state':'uploaded','digest':'sha256:'+digest(self.raw)}
        self.data['/repos/'+OWN]={'full_name':OWN}
        self.data['/repos/'+OWN+'/releases/assets/91']=self.asset
        self.data['/repos/'+OWN+'/releases?per_page=100&page=1']=[{'id':81,'draft':True,'assets':[copy.deepcopy(self.asset)]}]
        for section,kind in [('source','sourceArtifactName'),('signing','signedArtifactName')]:
            p=fixture.manifest[section];repo=p['repository'];run=p['runId'];artifact=p['artifactId']
            self.data[f'/repos/{repo}/actions/runs/{run}']={'id':run,'head_sha':p['commit'],'head_branch':'main','event':'workflow_dispatch','path':p['workflow'],
                'status':'completed','conclusion':'success','repository':{'full_name':repo},'head_repository':{'full_name':repo}}
            self.data[f'/repos/{repo}/actions/artifacts/{artifact}']={'id':artifact,'name':a[kind],'expired':False,'digest':'sha256:'+p['artifactArchiveSha256'],
                'workflow_run':{'id':run,'head_sha':p['commit'],'head_branch':'main'}}
    def json(self,path):self.calls.append(path);return copy.deepcopy(self.data[path])
    def download_asset(self,asset_id,*,package,app,expected_size):
        # Verify transport receives official metadata context, not body-derived size.
        assert package==self.expected_package and app==self.expected_app
        assert type(expected_size)is int and expected_size==self.asset['size']
        self.download_contexts.append({'package':package,'app':copy.deepcopy(app),'expected_size':expected_size})
        self.downloads.append(asset_id);return self.raw

class AssetTests(unittest.TestCase):
    def test_own_draft_asset_id_and_actual_archive_digest_are_bound(self):
        f=Fixture();g=GitHub(f);raw,receipt=release_asset.fetch_candidate_asset(g,91,digest(g.raw),PACKAGE,f.catalog)
        self.assertEqual(raw,g.raw);self.assertEqual(receipt['releaseId'],81);self.assertEqual(receipt['assetId'],91);self.assertEqual(g.downloads,[91]);self.assertEqual(g.download_contexts,[{'package':PACKAGE,'app':f.app,'expected_size':g.asset['size']}])
    def test_unknown_package_and_malformed_asset_identity_do_not_touch_github(self):
        for package,asset in [('com.kamilunavo.onemorefloor',91),(PACKAGE,'91/../../x'),(PACKAGE,True)]:
            f=Fixture();g=GitHub(f)
            with self.subTest(package=package,asset=asset),self.assertRaises(ValueError):release_asset.fetch_candidate_asset(g,asset,digest(g.raw),package,f.catalog)
            self.assertEqual(g.calls,[])
    def test_published_or_unowned_or_duplicate_asset_membership_rejected(self):
        for mode in ['published','not_member','wrong_repo','duplicate']:
            f=Fixture();g=GitHub(f);release=g.data['/repos/'+OWN+'/releases?per_page=100&page=1'][0]
            if mode=='published':release['draft']=False
            elif mode=='not_member':release['assets']=[]
            elif mode=='wrong_repo':g.data['/repos/'+OWN]['full_name']='other/repo'
            else:release['assets']*=2
            with self.subTest(mode=mode),self.assertRaises(ValueError):release_asset.fetch_candidate_asset(g,91,digest(g.raw),PACKAGE,f.catalog)
            self.assertEqual(g.downloads,[])
    def test_asset_name_state_size_digest_and_download_bytes_must_match(self):
        for field,value in [('id',92),('name','arbitrary.zip'),('state','open'),('size',0),('digest','sha256:'+'0'*64)]:
            f=Fixture();g=GitHub(f);g.asset[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):release_asset.fetch_candidate_asset(g,91,digest(g.raw),PACKAGE,f.catalog)
        f=Fixture();g=GitHub(f);expected=digest(g.raw);g.raw+=b'changed'
        with self.assertRaises(ValueError):release_asset.fetch_candidate_asset(g,91,expected,PACKAGE,f.catalog)
    def test_actual_source_and_sign_run_artifact_metadata_are_verified(self):
        f=Fixture();g=GitHub(f);c=candidate.validate_archive(g.raw,digest(g.raw),PACKAGE,f.catalog,Verifier(),NOW)
        self.assertEqual(release_asset.verify_provenance(g,c)['sourceRunId'],42)
        self.assertEqual(len([p for p in g.calls if '/actions/'in p]),4)
    def test_wrong_same_sha_workflow_event_repository_or_digest_fail_closed(self):
        for section,field,value in [('source','path','.github/workflows/unrelated.yml'),('source','event','push'),('signing','head_sha','f'*40),('signing','head_branch','feature'),('source','head_repository',{'full_name':'other/repo'}),('signing','conclusion','failure')]:
            f=Fixture();g=GitHub(f);c=candidate.validate_archive(g.raw,digest(g.raw),PACKAGE,f.catalog,Verifier(),NOW);p=f.manifest[section];g.data[f'/repos/{p["repository"]}/actions/runs/{p["runId"]}'][field]=value
            with self.subTest(section=section,field=field),self.assertRaises(ValueError):release_asset.verify_provenance(g,c)
        for field,value in [('id',99),('expired',True),('name','other artifact'),('digest','sha256:'+'0'*64),('workflow_run',{'id':999,'head_sha':'a'*40,'head_branch':'main'})]:
            f=Fixture();g=GitHub(f);c=candidate.validate_archive(g.raw,digest(g.raw),PACKAGE,f.catalog,Verifier(),NOW);p=f.manifest['signing'];g.data[f'/repos/{p["repository"]}/actions/artifacts/{p["artifactId"]}'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):release_asset.verify_provenance(g,c)

class ExactMaengelfixPushSourceTests(unittest.TestCase):
    """Synthetic official metadata replay; no archive, credentials or provider calls."""
    def case(self):
        import json
        from pathlib import Path
        from types import SimpleNamespace
        app=copy.deepcopy(next(a for a in json.loads((Path(__file__).parents[1]/'business-catalog.json').read_text())['apps']if a['package']=='com.kamilunavo.maengelfix'))
        source={'repository':OWN,'commit':'475cc69fe296a5ee1e484283697efe59144dac1e','workflow':'.github/workflows/android-ci.yml','runId':41033070706,'artifactId':12965814585,'artifactArchiveSha256':'96af56341cdf369aa89f2f5275adae11f565f62a3b3c6c0a2b222ba2def24909'}
        signing={'repository':OWN,'commit':source['commit'],'workflow':'.github/workflows/android-central-signed-bundle.yml','runId':41033586320,'artifactId':12967455452,'artifactArchiveSha256':'a9a83ae55dc6209f2bc06d285a7f54d474078f04646439117a7c37322f486384'}
        c=SimpleNamespace(package=app['package'],app=app,manifest={'versionCode':9,'versionName':'1.1.0','source':source,'signing':signing});data={}
        for section,name in [('source','sourceArtifactName'),('signing','signedArtifactName')]:
            p=c.manifest[section];base='/repos/'+OWN+'/actions/'
            data[base+'runs/'+str(p['runId'])]={'id':p['runId'],'head_sha':p['commit'],'head_branch':'main','event':'push'if section=='source'else'workflow_dispatch','path':p['workflow'],'status':'completed','conclusion':'success','repository':{'full_name':OWN},'head_repository':{'full_name':OWN}}
            data[base+'artifacts/'+str(p['artifactId'])]={'id':p['artifactId'],'name':app[name],'expired':False,'digest':'sha256:'+p['artifactArchiveSha256'],'workflow_run':{'id':p['runId'],'head_sha':p['commit'],'head_branch':'main'}}
        class Replay:
            def __init__(self):self.calls=[]
            def json(self,path):self.calls.append(path);return copy.deepcopy(data.get(path,{}))
        return c,Replay(),data
    def test_exact_root_reviewed_m9_push_source_and_manual_sign_accept(self):
        c,g,data=self.case()
        try:r=release_asset.verify_provenance(g,c,'business12')
        except ValueError as error:self.fail('Exact reviewed M9 push source unexpectedly rejected: '+str(error))
        self.assertEqual(r,{'sourceRunId':41033070706,'sourceArtifactId':12965814585,'signingRunId':41033586320,'signingArtifactId':12967455452});self.assertEqual(len(g.calls),4)
    def test_same_exact_m9_manual_source_still_accepted(self):
        c,g,data=self.case();data['/repos/'+OWN+'/actions/runs/41033070706']['event']='workflow_dispatch';self.assertEqual(release_asset.verify_provenance(g,c,'business12')['sourceRunId'],41033070706)
    def test_push_exception_exact_app_and_manifest_metadata_only(self):
        for target,key,value in [('candidate','package','de.kamilunavo.brennercalc'),('app','newVersionCode',10),('app','newVersionCode',True),('app','reviewedSourceCommit','0'*40),('app','repository','other/repo'),('manifest','versionCode',10),('manifest','versionCode',True),('manifest','versionName','1.2.0')]:
            c,g,data=self.case()
            if target=='candidate':setattr(c,key,value)
            else:(c.app if target=='app'else c.manifest)[key]=value
            with self.subTest(target=target,key=key,value=value),self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
    def test_push_exception_exact_source_run_artifact_digest_path_commit_only(self):
        for key,value in [('runId',41033070707),('artifactId',12965814586),('artifactArchiveSha256','0'*64),('workflow','.github/workflows/other.yml'),('commit','0'*40),('repository','other/repo')]:
            c,g,data=self.case();old=copy.deepcopy(c.manifest['source']);c.manifest['source'][key]=value
            if key=='runId':data['/repos/'+OWN+'/actions/runs/'+str(value)]=copy.deepcopy(data['/repos/'+OWN+'/actions/runs/'+str(old['runId'])]);data['/repos/'+OWN+'/actions/runs/'+str(value)]['id']=value
            with self.subTest(key=key),self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
    def test_official_source_run_guards_remain_exact(self):
        for key,value in [('id',41033070707),('head_sha','0'*40),('head_branch','feature'),('event','pull_request'),('event','workflow_run'),('path','.github/workflows/other.yml'),('status','in_progress'),('conclusion','failure'),('repository',{'full_name':'other/repo'}),('head_repository',{'full_name':'other/repo'})]:
            c,g,data=self.case();data['/repos/'+OWN+'/actions/runs/41033070706'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
    def test_official_artifact_guards_remain_exact(self):
        for key,value in [('id',12965814586),('name','other'),('expired',True),('digest','sha256:'+'0'*64),('workflow_run',{'id':41033070707,'head_sha':'475cc69fe296a5ee1e484283697efe59144dac1e','head_branch':'main'}),('workflow_run',{'id':41033070706,'head_sha':'0'*40,'head_branch':'main'}),('workflow_run',{'id':41033070706,'head_sha':'475cc69fe296a5ee1e484283697efe59144dac1e','head_branch':'feature'})]:
            c,g,data=self.case();data['/repos/'+OWN+'/actions/artifacts/12965814585'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
    def test_signing_push_is_never_exception(self):
        c,g,data=self.case();data['/repos/'+OWN+'/actions/runs/41033586320']['event']='push'
        with self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
    def test_calculator_push_still_rejected(self):
        f=Fixture();g=GitHub(f);c=candidate.validate_archive(g.raw,digest(g.raw),PACKAGE,f.catalog,Verifier(),NOW);p=f.manifest['source'];g.data[f'/repos/{p["repository"]}/actions/runs/{p["runId"]}']['event']='push'
        with self.assertRaises(ValueError):release_asset.verify_provenance(g,c)
    def test_all_other_business_packages_cannot_use_reviewed_m9_push(self):
        import json
        from pathlib import Path
        apps=json.loads((Path(__file__).parents[1]/'business-catalog.json').read_text())['apps']
        checked=[]
        for app in apps:
            if app['package']=='com.kamilunavo.maengelfix':continue
            c,g,data=self.case();c.package=app['package'];c.app=copy.deepcopy(app)
            with self.subTest(package=c.package),self.assertRaises(ValueError):release_asset.verify_provenance(g,c,'business12')
            checked.append(c.package)
        self.assertEqual(len(checked),11)
    def test_actual_exception_expression_rejects_wrong_family_or_section(self):
        import ast
        from pathlib import Path
        tree=ast.parse((Path(__file__).parents[1]/'release_asset.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='verify_provenance');node=next(n for n in ast.walk(fn)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='reviewed_m9_source'for t in n.targets));code=compile(ast.Expression(body=node.value),'actual-reviewed_m9_source-expression','eval')
        c,g,data=self.case();env={'candidate':c,'app':c.app,'part':c.manifest['source'],'family':'business12','section':'source','run_id':41033070706,'artifact_id':12965814585};self.assertIs(eval(code,{},env),True)
        for field,value in [('family','calculator9'),('family','game5'),('family','business13'),('section','signing')]:
            e=dict(env);e[field]=value
            with self.subTest(field=field,value=value):self.assertIs(eval(code,{},e),False)
