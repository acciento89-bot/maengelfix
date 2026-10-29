import copy, unittest
from fixtures import Fixture, Verifier, PACKAGE, NOW, digest
import candidate, release_asset

OWN = 'acciento89-bot/maengelfix'
class GitHub:
    def __init__(self, fixture):
        self.raw=fixture.raw();self.calls=[];self.downloads=[];self.data={}
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
    def download_asset(self,asset_id):self.downloads.append(asset_id);return self.raw

class AssetTests(unittest.TestCase):
    def test_own_draft_asset_id_and_actual_archive_digest_are_bound(self):
        f=Fixture();g=GitHub(f);raw,receipt=release_asset.fetch_candidate_asset(g,91,digest(g.raw),PACKAGE,f.catalog)
        self.assertEqual(raw,g.raw);self.assertEqual(receipt['releaseId'],81);self.assertEqual(receipt['assetId'],91);self.assertEqual(g.downloads,[91])
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
