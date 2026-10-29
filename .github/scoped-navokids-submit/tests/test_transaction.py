"""Original fake-transaction controls, readiness mocked for UNIT-ONLY data; no root/native approval is fabricated."""
import copy, dataclasses, unittest
from fixtures import digest
from unittest.mock import patch
import business_policy
import candidate, publisher

class FakeTransport:
    def __init__(self, c, failures=None):
        self.c=c;self.calls=[];self.edits={};self.sequence=0;self.failures=failures or {};self.commits=0
        app=c.app;self.live={'bundles':{'bundles':[{'versionCode':app['previousMaxCode'],'sha256':'c'*64}]},'apks':{'apks':[]},
            'tracks':{'tracks':[{'track':'production','releases':[{'status':'completed','versionCodes':[str(app['previousProductionCode'])],
                'name':'previous','releaseNotes':[{'language':'de-DE','text':'old'}],'inAppUpdatePriority':2,'countryTargeting':{'countries':['DE','AT'],'includeRestOfWorld':False}}]},
                {'track':'internal','releases':[{'status':'draft','versionCodes':[str(app['previousProductionCode']-1)]}]}]},
            'listings':{'listings':[{'language':'de-DE','title':'Original DE','fullDescription':'keep DE'}, {'language':'en-US','title':'Original EN','fullDescription':'keep EN'}, {'language':'fr-FR','title':'keep FR'}]},
            'details':{'defaultLanguage':'de-DE','contactEmail':'private-support@example.invalid'},
            'countryAvailability/production':{'countries':[{'countryCode':'DE'},{'countryCode':'AT'}],'restOfWorld':False},
            'images':{l:{'phoneScreenshots':[{'sha256':'d'*64}], 'icon':[{'sha256':'e'*64}]}for l in ['de-DE','en-US']}}
    def request(self, method, path, body=None, media=None):
        self.calls.append((method,path,copy.deepcopy(body),digest(media.data)if media else None))
        clean_path=path.split('?')[0]
        if method=='POST'and clean_path.endswith('/edits'):kind='readback_create'if self.commits else'create'
        elif ':commit?'in path:kind='commit'
        elif path.endswith(':validate'):kind='validate'
        elif method=='POST'and clean_path.endswith('/bundles'):kind='upload'
        elif method=='DELETE'and '/listings/'not in path:kind='delete'
        elif method=='PUT':kind='track'
        elif method=='POST'and '/listings/'in path:kind='image'
        else:kind='read'
        override=self.failures.get(kind)
        if isinstance(override,BaseException):raise override
        if callable(override):return override(method,path,body,media)
        if override is not None:return override
        if kind in ['create','readback_create']:
            self.sequence+=1;edit='owned-'+str(self.sequence);self.edits[edit]=copy.deepcopy(self.live);return publisher.Response(200,{'id':edit})
        tail=clean_path.split('/edits/')[1];edit=tail.split('/')[0].split(':')[0];state=self.edits[edit]
        if kind=='delete':del self.edits[edit];return publisher.Response(204)
        if kind=='upload':
            item={'versionCode':self.c.app['newVersionCode'],'sha256':digest(media.data)};state['bundles']['bundles'].append(item);return publisher.Response(200,item)
        if kind=='validate':return publisher.Response(200,{'id':edit})
        if kind=='commit':
            self.live=copy.deepcopy(state);del self.edits[edit];self.commits+=1;return publisher.Response(200,{'id':edit})
        resource=tail.split('/',1)[1]if '/'in tail else''
        if resource.startswith('listings/'):
            _,locale,image_type=resource.split('/');images=state['images'][locale][image_type]
            if method=='DELETE':images.clear();return publisher.Response(204)
            if method=='POST':
                image={'sha256':digest(media.data)};images.append(image);return publisher.Response(200,{'image':image})
            return publisher.Response(200,{'images':copy.deepcopy(images)})
        if kind=='track':
            state['tracks']['tracks']=[t for t in state['tracks']['tracks']if t['track']!='production']+[copy.deepcopy(body)];return publisher.Response(200,copy.deepcopy(body))
        return publisher.Response(200,copy.deepcopy(state[resource]))

class PublisherTests(unittest.TestCase):
    def setUp(self):
        app=business_policy.fixed_apps()['com.kamilunavo.navokids'];app.update(listingLocales=['de-DE','en-US'],localeSnapshotSha256='a'*64,releaseNotes={'de-DE':'Explicit synthetic transaction unit fixture','en-US':'Explicit synthetic transaction unit fixture'},syntheticFixtureOnly=True)
        self.c=candidate.Candidate(app['package'],app,{},b'UNIT_ONLY_NOT_A_REAL_BUNDLE',digest(b'UNIT_ONLY_NOT_A_REAL_BUNDLE'),'b'*64,{l:tuple(candidate.Media('screens/'+l+'/'+str(i)+'.png',digest(bytes([i])),bytes([i]))for i in range(1,5))for l in app['listingLocales']},None,'c'*64)
        self.gate=patch.object(publisher,'require_ready',side_effect=lambda a: self.assertIs(a.get('syntheticFixtureOnly'),True));self.gate.start();self.addCleanup(self.gate.stop)
    def run_submit(self,http=None,checkpoint=None):
        http=http or FakeTransport(self.c);return publisher.submit_candidate(self.c,http,checkpoint),http
    def test_one_own_production_commit_exact_upload_and_preserved_other_payloads(self):
        http=FakeTransport(self.c);before=copy.deepcopy(http.live);report,http=self.run_submit(http)
        self.assertTrue(report['ok']);self.assertEqual(report['status'],'submitted_for_review');self.assertFalse(report['publicReleaseConfirmed'])
        self.assertEqual(http.commits,1);self.assertEqual(http.edits,{})
        commits=[x for x in http.calls if ':commit?'in x[1]];self.assertEqual(len(commits),1)
        self.assertTrue(commits[0][1].endswith(':commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW'))
        self.assertEqual([x[3]for x in http.calls if x[0]=='POST'and x[1].split('?')[0].endswith('/bundles')],[self.c.bundle_sha256])
        for key in ['listings','details','countryAvailability/production']:self.assertEqual(before[key],http.live[key])
        self.assertEqual(before['tracks']['tracks'][1],next(t for t in http.live['tracks']['tracks']if t['track']=='internal'))
        prod=next(t for t in http.live['tracks']['tracks']if t['track']=='production')['releases'][0]
        self.assertEqual(prod['versionCodes'],['9']);self.assertEqual(prod['countryTargeting'],before['tracks']['tracks'][0]['releases'][0]['countryTargeting'])
        for locale in ['de-DE','en-US']:
            self.assertEqual([i['sha256']for i in http.live['images'][locale]['phoneScreenshots']],[i.sha256 for i in self.c.screenshots[locale]])
            self.assertEqual(http.live['images'][locale]['icon'],before['images'][locale]['icon'])
        self.assertTrue(all(c['confirmed']for c in report['cleanup']))
    def test_excluded_package_cannot_create_or_mutate_an_edit(self):
        c=dataclasses.replace(self.c,package='com.kamilunavo.onemorefloor');http=FakeTransport(self.c)
        report=publisher.submit_candidate(c,http);self.assertFalse(report['ok']);self.assertEqual(http.calls,[])
    def test_ambiguous_production_current_or_global_max_stops_before_upload(self):
        for mode in ['different_production','rollout','duplicate_production','future_pending_code','ambiguous_code']:
            h=FakeTransport(self.c);prod=h.live['tracks']['tracks'][0]['releases'][0]
            if mode=='different_production':prod['versionCodes']=['5']
            elif mode=='rollout':prod['status']='inProgress'
            elif mode=='duplicate_production':h.live['tracks']['tracks'].append(copy.deepcopy(h.live['tracks']['tracks'][0]))
            elif mode=='future_pending_code':h.live['tracks']['tracks'][1]['releases'][0]['versionCodes']=['20']
            else:h.live['bundles']['bundles'][0]['versionCode']=True
            report,_=self.run_submit(h)
            with self.subTest(mode=mode):
                self.assertFalse(report['ok']);self.assertFalse(any(x[0]=='POST'and x[1].split('?')[0].endswith('/bundles')for x in h.calls));self.assertEqual(h.edits,{})
    def test_wrong_upload_code_or_raw_sha_rejected_before_track_or_commit(self):
        for data in [{'versionCode':90,'sha256':self.c.bundle_sha256},{'versionCode':9,'sha256':'0'*64}]:
            report,h=self.run_submit(FakeTransport(self.c,{'upload':publisher.Response(200,data)}))
            self.assertFalse(report['ok']);self.assertFalse(any(x[0]=='PUT'or':commit?'in x[1]for x in h.calls));self.assertEqual(h.edits,{})
    def test_pending_review_commit_is_not_cancelled_or_retried_and_owned_edit_deleted(self):
        report,h=self.run_submit(FakeTransport(self.c,{'commit':publisher.Response(400,{'reason':'CHANGES_ALREADY_IN_REVIEW'})}))
        self.assertFalse(report['ok']);self.assertEqual(report['status'],'blocked_in_review');self.assertEqual(h.edits,{})
        self.assertEqual(len([x for x in h.calls if ':commit?'in x[1]]),1)
        self.assertTrue(all('CANCEL'not in x[1]for x in h.calls));self.assertTrue(report['cleanup'][0]['confirmed'])
    def test_unknown_commit_stops_without_delete_or_retry(self):
        for failure in [publisher.TransportError('secret-token'),publisher.Response(408,None),publisher.Response(429,None),publisher.Response(503,None),publisher.Response(200,{})]:
            report,h=self.run_submit(FakeTransport(self.c,{'commit':failure}))
            self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertEqual(report['commit']['outcome'],'unknown')
            self.assertEqual(len([x for x in h.calls if ':commit?'in x[1]]),1);self.assertFalse(any(x[0]=='DELETE'and'/listings/'not in x[1]for x in h.calls))
            self.assertNotIn('secret-token',str(report))
    def test_unknown_upload_deletes_only_owned_edit_and_never_retries_upload(self):
        report,h=self.run_submit(FakeTransport(self.c,{'upload':publisher.TransportError('private body')}))
        self.assertFalse(report['ok']);self.assertEqual(h.edits,{});self.assertEqual(len([x for x in h.calls if x[0]=='POST'and x[1].split('?')[0].endswith('/bundles')]),1)
        self.assertTrue(report['cleanup'][0]['confirmed']);self.assertNotIn('private body',str(report));self.assertFalse(any(':commit?'in x[1]for x in h.calls))
    def test_unknown_create_and_unknown_upload_are_explicit_reconciliation_states(self):
        for key in ['create','upload']:
            report,h=self.run_submit(FakeTransport(self.c,{key:publisher.TransportError('private network detail')}))
            with self.subTest(key=key):self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertNotIn('private network detail',str(report))
    def test_validate_or_image_failure_cleans_owned_edit_without_commit(self):
        for key in ['validate','image']:
            report,h=self.run_submit(FakeTransport(self.c,{key:publisher.Response(400,{})}))
            with self.subTest(key=key):self.assertFalse(report['ok']);self.assertEqual(h.edits,{});self.assertFalse(any(':commit?'in x[1]for x in h.calls))
    def test_every_raw_bundle_and_png_upload_explicitly_uses_simple_media_upload(self):
        report,h=self.run_submit();self.assertTrue(report['ok'])
        media=[x for x in h.calls if x[3]is not None];self.assertEqual(len(media),9)
        self.assertTrue(all(x[1].endswith('?uploadType=media')for x in media))
    def test_cleanup_unknown_cannot_report_safe_failure_or_success(self):
        report,h=self.run_submit(FakeTransport(self.c,{'validate':publisher.Response(400,{}),'delete':publisher.Response(503,None)}))
        self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertFalse(report['cleanup'][0]['confirmed'])
    def test_readback_creation_or_cleanup_failure_after_commit_is_reconciliation(self):
        for key,failure in [('readback_create',publisher.Response(503,None)),('delete',publisher.Response(503,None))]:
            report,h=self.run_submit(FakeTransport(self.c,{key:failure}))
            with self.subTest(key=key):self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertEqual(h.commits,1)
    def test_exact_candidate_already_present_is_readonly_noop_with_confirmed_cleanup(self):
        report,h=self.run_submit();self.assertTrue(report['ok']);h.calls=[]
        again=publisher.submit_candidate(self.c,h)
        self.assertTrue(again['ok']);self.assertEqual(again['status'],'noop_already_present');self.assertEqual(h.commits,1)
        self.assertFalse(any(x[0]=='PUT'or':commit?'in x[1]or(x[0]=='POST'and'/listings/'in x[1])or(x[0]=='POST'and x[1].split('?')[0].endswith('/bundles'))for x in h.calls));self.assertEqual(h.edits,{})
    def test_partly_uploaded_candidate_requires_reconciliation_instead_of_reupload(self):
        h=FakeTransport(self.c);h.live['bundles']['bundles'].append({'versionCode':9,'sha256':self.c.bundle_sha256});report,h=self.run_submit(h)
        self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertFalse(any(x[0]=='POST'and x[1].split('?')[0].endswith('/bundles')for x in h.calls));self.assertEqual(h.edits,{})
    def test_committed_targeting_or_priority_change_does_not_pass_readback(self):
        h=FakeTransport(self.c);original=h.request
        def changed_priority(method,path,body=None,media=None):
            response=original(method,path,body,media)
            if ':commit?'in path:next(t for t in h.live['tracks']['tracks']if t['track']=='production')['releases'][0]['inAppUpdatePriority']=5
            return response
        h.request=changed_priority;report,h=self.run_submit(h)
        self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertEqual(h.commits,1);self.assertEqual(h.edits,{})
    def test_conflicting_already_production_candidate_is_reconciliation(self):
        h=FakeTransport(self.c);h.live['tracks']['tracks'][0]['releases'][0]['versionCodes']=['9'];h.live['bundles']['bundles'].append({'versionCode':9,'sha256':'0'*64})
        report,h=self.run_submit(h);self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertEqual(h.edits,{})
    def test_nonproduction_or_listing_mutation_before_commit_is_detected(self):
        h=FakeTransport(self.c);original=h.request
        def mutating(method,path,body=None,media=None):
            response=original(method,path,body,media)
            if method=='PUT':
                state=next(iter(h.edits.values()));state['listings']['listings'][0]['title']='unexpected mutation'
            return response
        h.request=mutating;report,h=self.run_submit(h);self.assertFalse(report['ok']);self.assertEqual(h.commits,0);self.assertEqual(h.edits,{})
    def test_missing_existing_listing_and_checkpoint_failure_stop_without_provider_payload_writes(self):
        h=FakeTransport(self.c);h.live['listings']['listings']=[];report,h=self.run_submit(h);self.assertFalse(report['ok']);self.assertEqual(h.edits,{})
        def broken(_):raise OSError('private disk error')
        report,h=self.run_submit(checkpoint=broken);self.assertFalse(report['ok']);self.assertFalse(any(x[0]=='POST'and x[1].split('?')[0].endswith('/bundles')for x in h.calls));self.assertNotIn('private disk error',str(report))

    def test_documented_empty_json_delete_acknowledgement_confirms_readback_cleanup(self):
        h=FakeTransport(self.c)
        def delete(method,path,body,media):
            edit=path.split('/edits/')[1];del h.edits[edit];return publisher.Response(200,{})
        h.failures['delete']=delete
        report,_=self.run_submit(h);self.assertTrue(report['ok']);self.assertTrue(report['cleanup'][0]['confirmed']);self.assertEqual(h.edits,{})
