import copy, json, unittest
from fixtures import HERE, PACKAGE, NOW
import candidate, locale_inventory, publisher

class ReadOnlyTransport:
    def __init__(self,fail=None):self.calls=[];self.fail=fail;self.edits=set()
    def request(self,method,path,body=None,media=None):
        self.calls.append((method,path,body));self.assert_no_media(media)
        if self.fail=='create_unknown'and method=='POST':raise publisher.TransportError('unit-private-token')
        if method=='POST':
            self.edits.add(path+'/owned');return publisher.Response(200,{'id':'owned'})
        if method=='DELETE':
            if self.fail=='cleanup':return publisher.Response(503,None)
            self.edits.discard(path);return publisher.Response(200,{}) if self.fail=='delete_200' else publisher.Response(204)
        if self.fail=='read':return publisher.Response(500,None)
        languages=['de-DE','en-GB'] if self.fail!='duplicate'else['de-DE','de-DE']
        return publisher.Response(200,{'listings':[{'language':l,'title':'private listing content not retained'}for l in languages]})
    def assert_no_media(self,media):
        if media is not None:raise AssertionError('Inventory attempted media upload')

class InventoryTests(unittest.TestCase):
    def setUp(self):self.catalog={a['package']:a for a in json.loads((HERE/'catalog.json').read_text())['apps']}
    def test_one_package_gets_existing_locale_ids_and_confirmed_owned_delete_only(self):
        h=ReadOnlyTransport();report=locale_inventory.inspect_existing_locales(PACKAGE,self.catalog,h,now=NOW)
        self.assertTrue(report['ok']);self.assertEqual(report['apps'][0]['localeIds'],['de-DE','en-GB']);self.assertEqual(h.edits,set())
        base='/androidpublisher/v3/applications/'+PACKAGE+'/edits'
        self.assertEqual(h.calls,[('POST',base,{}),('GET',base+'/owned/listings',None),('DELETE',base+'/owned',None)])
        self.assertNotIn('private listing content',str(report));self.assertEqual(report['apps'][0]['cleanup']['httpStatus'],204)
    def test_fixed_all_nine_batch_is_serial_and_never_visits_other_apps(self):
        h=ReadOnlyTransport();report=locale_inventory.inspect_existing_locales('all-nine',self.catalog,h,now=NOW)
        self.assertTrue(report['ok']);self.assertEqual(len(report['apps']),9);self.assertEqual(len(h.calls),27)
        self.assertEqual({r['package']for r in report['apps']},set(candidate.EXPECTED));self.assertEqual(h.edits,set())
        self.assertTrue(all([m for m,_,_ in h.calls[i:i+3]]==['POST','GET','DELETE']for i in range(0,27,3)))
    def test_excluded_or_unbounded_selector_fails_without_google_requests(self):
        for selector in ['all','all26','com.kamilunavo.onemorefloor','de.kamilunavo.maengelfix','../listings']:
            h=ReadOnlyTransport();report=locale_inventory.inspect_existing_locales(selector,self.catalog,h,now=NOW)
            with self.subTest(selector=selector):self.assertFalse(report['ok']);self.assertEqual(h.calls,[])
    def test_read_or_ambiguous_locale_response_cleans_own_edit_and_stops_batch(self):
        for failure in ['read','duplicate']:
            h=ReadOnlyTransport(failure);report=locale_inventory.inspect_existing_locales('all-nine',self.catalog,h,now=NOW)
            with self.subTest(failure=failure):self.assertFalse(report['ok']);self.assertEqual(len(report['apps']),1);self.assertEqual(h.edits,set());self.assertTrue(report['apps'][0]['cleanup']['confirmed'])
    def test_unknown_create_or_cleanup_never_claims_safe_inventory_or_continues(self):
        for failure in ['create_unknown','cleanup']:
            h=ReadOnlyTransport(failure);report=locale_inventory.inspect_existing_locales('all-nine',self.catalog,h,now=NOW)
            with self.subTest(failure=failure):self.assertFalse(report['ok']);self.assertEqual(report['status'],'reconciliation_required');self.assertEqual(len(report['apps']),1);self.assertNotIn('unit-private-token',str(report))
    def test_checkpoint_failure_after_create_still_deletes_only_owned_edit(self):
        h=ReadOnlyTransport()
        def checkpoint(report):
            if report['apps']and report['apps'][0].get('editId'):raise OSError('private disk detail')
        report=locale_inventory.inspect_existing_locales(PACKAGE,self.catalog,h,checkpoint,NOW)
        self.assertFalse(report['ok']);self.assertEqual(h.edits,set());self.assertTrue(report['apps'][0]['cleanup']['confirmed']);self.assertNotIn('private disk detail',str(report))

    def test_documented_empty_json_delete_acknowledgement_confirms_cleanup(self):
        h=ReadOnlyTransport('delete_200');report=locale_inventory.inspect_existing_locales(PACKAGE,self.catalog,h,now=NOW)
        self.assertTrue(report['ok']);self.assertTrue(report['apps'][0]['cleanup']['confirmed']);self.assertEqual(h.edits,set())
