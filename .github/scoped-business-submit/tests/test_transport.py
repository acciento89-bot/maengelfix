import io, json, unittest
from urllib.error import HTTPError, URLError
from fixtures import PACKAGE, Fixture
import publisher, release_asset

class Stream:
    status=200
    def __init__(self,raw):self.raw=raw
    def read(self,size):return self.raw[:size]
    def __enter__(self):return self
    def __exit__(self,*args):pass
class Opener:
    def __init__(self,location=None,raw=b'{}'):self.location=location;self.raw=raw;self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        if self.location and len(self.calls)==1:raise HTTPError(request.full_url,302,'redirect',{'Location':self.location},io.BytesIO())
        return Stream(self.raw)

class TransportTests(unittest.TestCase):
    def test_google_token_only_reaches_fixed_origin_raw_media_query_and_bounded_timeout(self):
        client=publisher.HttpTransport('unit-google-token',Fixture().catalog,inspect_only=False);opener=Opener();client._opener=opener
        path='/upload/androidpublisher/v3/applications/'+PACKAGE+'/edits/owned/bundles?uploadType=media'
        client.request('POST',path,media=publisher.MediaPayload(b'unit-aab','application/octet-stream'))
        request,timeout=opener.calls[0];self.assertEqual(request.full_url,'https://androidpublisher.googleapis.com'+path)
        self.assertEqual(request.data,b'unit-aab');self.assertEqual(timeout,120);self.assertEqual(request.get_header('Authorization'),'Bearer unit-google-token')
    def test_duplicate_provider_json_identity_is_not_interpreted_as_successful_metadata(self):
        client=publisher.HttpTransport('unit-token',Fixture().catalog,inspect_only=False);client._opener=Opener(raw=b'{"id":"first","id":"second"}')
        response=client.request('POST','/androidpublisher/v3/applications/'+PACKAGE+'/edits',{})
        self.assertIsNone(response.data)
    def test_google_transport_denies_other_apps_nonproduction_default_or_cancel_commit(self):
        client=publisher.HttpTransport('unit-token',Fixture().catalog,inspect_only=False);opener=Opener();client._opener=opener;base='/androidpublisher/v3/applications/'+PACKAGE+'/edits/owned'
        cases=[('POST',base+':commit'),('POST',base+':commit?changesInReviewBehavior=CANCEL_IN_REVIEW_AND_SUBMIT'),('PUT',base+'/tracks/internal'),
            ('POST','/androidpublisher/v3/applications/com.kamilunavo.onemorefloor/edits'),('POST','https://evil.invalid/upload'),('DELETE',base+'/listings/fr-FR/phoneScreenshots')]
        for method,path in cases:
            with self.subTest(path=path),self.assertRaises(Exception):client.request(method,path)
        self.assertEqual(opener.calls,[])
    def test_github_token_is_not_forwarded_to_official_release_cdn(self):
        client=release_asset.GitHubClient('unit-github-token');opener=Opener('https://release-assets.githubusercontent.com/file?signature=unit-private',b'archive');client._opener=opener
        self.assertEqual(client.download_asset(91),b'archive')
        self.assertEqual(opener.calls[0][0].get_header('Authorization'),'Bearer unit-github-token')
        self.assertIsNone(opener.calls[1][0].get_header('Authorization'))
    def test_github_untrusted_redirects_never_receive_a_followup_request(self):
        for location in ['http://release-assets.githubusercontent.com/file','https://evil.invalid/file','https://user@release-assets.githubusercontent.com/file','https://release-assets.githubusercontent.com:444/file']:
            client=release_asset.GitHubClient('unit-token');opener=Opener(location);client._opener=opener
            with self.subTest(location=location),self.assertRaises(ValueError):client.download_asset(91)
            self.assertEqual(len(opener.calls),1)

    def test_default_inventory_transport_only_allows_owned_create_listings_delete(self):
        client=publisher.HttpTransport('unit-token',Fixture().catalog);opener=Opener(raw=b'{"id":"owned"}');client._opener=opener
        base='/androidpublisher/v3/applications/'+PACKAGE+'/edits'
        for method,path,body in [('GET',base+'/unowned/listings',None),('DELETE',base+'/unowned',None),('POST',base+'/owned:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW',None),('GET',base+'/owned/bundles',None)]:
            with self.subTest(path=path),self.assertRaises(Exception):client.request(method,path,body)
        self.assertEqual(opener.calls,[])
        client.request('POST',base,{})
        client.request('GET',base+'/owned/listings')
        opener.raw=b''
        client.request('DELETE',base+'/owned')
        self.assertEqual(len(opener.calls),3);self.assertEqual([timeout for _,timeout in opener.calls],[20,20,10])
        with self.assertRaises(Exception):client.request('POST','/upload'+base+'/owned/bundles?uploadType=media',media=publisher.MediaPayload(b'unit','application/octet-stream'))
        self.assertEqual(len(opener.calls),3)

    def test_github_http_failure_exposes_only_bounded_status_and_exact_metadata_route(self):
        class Reject:
            def open(self,request,timeout):
                raise HTTPError('https://private.invalid/?signed=DO_NOT_LOG_URL',404,'DO_NOT_LOG_REASON',{'Authorization':'DO_NOT_LOG_HEADER'},io.BytesIO(b'DO_NOT_LOG_BODY'))
        client=release_asset.GitHubClient('DO_NOT_LOG_TOKEN');client._opener=Reject()
        route='/repos/acciento89-bot/maengelfix/releases/assets/688778313'
        with self.assertRaises(release_asset.AssetError)as failure:client.json(route)
        self.assertIn('HTTP404',str(failure.exception));self.assertIn('GET '+route,str(failure.exception));self.assertNotIn('DO_NOT_LOG',str(failure.exception));self.assertNotIn('private.invalid',str(failure.exception))
        client._opener=Opener(raw=b'{"secret":"DO_NOT_LOG_BODY","secret":"duplicate"}')
        with self.assertRaises(release_asset.AssetError)as invalid:client.json(route)
        self.assertIn('HTTP200',str(invalid.exception));self.assertIn('GET '+route,str(invalid.exception));self.assertNotIn('DO_NOT_LOG',str(invalid.exception))
    def test_github_network_failure_reports_unknown_status_without_exception_or_url_details(self):
        class Offline:
            def open(self,request,timeout):raise URLError('DO_NOT_LOG_TRANSPORT')
        client=release_asset.GitHubClient('DO_NOT_LOG_TOKEN');client._opener=Offline();route='/repos/acciento89-bot/BrennerCalc/actions/runs/40872881757'
        with self.assertRaises(release_asset.AssetError)as failure:client.json(route)
        self.assertIn('HTTPunknown',str(failure.exception));self.assertIn('GET '+route,str(failure.exception));self.assertNotIn('DO_NOT_LOG',str(failure.exception))
    def test_github_metadata_get_only_routes_bound_queries_repositories_and_identifiers(self):
        client=release_asset.GitHubClient('unit-token');opener=Opener();client._opener=opener
        allowed=['/repos/acciento89-bot/maengelfix','/repos/acciento89-bot/maengelfix/releases/assets/688778313','/repos/acciento89-bot/maengelfix/releases?per_page=100&page=10','/repos/acciento89-bot/SHK/actions/artifacts/42','/repos/acciento89-bot/AnlagenVolumen/actions/runs/43']
        for route in allowed:client.json(route)
        self.assertTrue(all(request.get_method()=='GET'and request.data is None for request,_ in opener.calls))
        denied=['/repos/acciento89-bot/maengelfix/releases?per_page=100&page=11','/repos/acciento89-bot/maengelfix/releases?access_token=DO_NOT_LOG','/repos/acciento89-bot/maengelfix/git/refs','/repos/acciento89-bot/OneMoreFloor/actions/runs/1','/repos/other/repo/actions/runs/1','/repos/acciento89-bot/BrennerCalc/actions/runs/0','/repos/acciento89-bot/BrennerCalc/actions/runs/9223372036854775808','https://evil.invalid/path','/repos/acciento89-bot/maengelfix/releases/assets/1%3Ftoken']
        for route in denied:
            with self.subTest(route=route),self.assertRaises(ValueError):client.json(route)
        self.assertEqual(len(opener.calls),len(allowed))
