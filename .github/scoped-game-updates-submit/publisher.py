"""Single fixed production edit, no retries and no arbitrary endpoint inputs."""
import copy
from dataclasses import dataclass
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from candidate import EXPECTED, digest, is_digest, require, strict_json, listing_locales
from game_policy import scope, version, require_ready, allows_reserved_game_step

@dataclass
class Response:
    status: int
    data: object = None
class TransportError(Exception): pass
class Interrupted(Exception): pass
class PolicyError(Exception): pass
class JournalError(Exception): pass
class UnknownWrite(Exception): pass

@dataclass(frozen=True)
class MediaPayload:
    data: bytes
    content_type: str

def check(value, reason):
    if not value: raise PolicyError(reason)

def code(value):
    check(type(value) in (int,str) and re.fullmatch(r'[1-9][0-9]{0,9}',str(value)) is not None, 'ambiguous_version_code')
    result = int(value); check(result <= 2100000000, 'version_code_out_of_range'); return result

def array(data, field):
    check(isinstance(data,dict) and isinstance(data.get(field,[]),list), 'malformed_'+field)
    return data.get(field,[])

def ok(response): return isinstance(response,Response) and type(response.status) is int and 200 <= response.status < 300

def deletion_confirmed(response):
    return isinstance(response,Response) and (response.status in (204,404) or
        (response.status == 200 and response.data == {}))

def definite_rejection(response):
    # Timeouts, throttling and unknown status classes never prove a mutating call was rejected.
    return isinstance(response,Response) and response.status in (400,401,403,404,409,412,413,415,422)

class ScopedPublisher:
    def __init__(self, candidate, transport, family='calculator9'):
        expected = scope(family)
        if family == 'game5':
            require_ready(candidate.app)
            check(candidate.bundle_sha256 == candidate.app['signedAabSha256'] and digest(candidate.aab) == candidate.app['signedAabSha256'], 'unknown_game_binary')
        check(candidate.package in expected and candidate.app.get('package') == candidate.package and
            candidate.app.get('newVersionCode') == expected[candidate.package][1] and candidate.app.get('newVersionName') == version(candidate.package,family), 'excluded_candidate_scope')
        self.candidate = candidate; self.transport = transport; self.owned = {}
        self.locales = listing_locales(candidate.app)
        self.base = '/androidpublisher/v3/applications/'+candidate.package+'/edits'
    def create(self, phase):
        try: response = self.transport.request('POST',self.base,{})
        except (TransportError,Interrupted,OSError,TimeoutError): raise UnknownWrite('edit_create_outcome_unknown') from None
        if not ok(response):
            if definite_rejection(response): raise PolicyError('edit_create_rejected')
            raise UnknownWrite('edit_create_outcome_unknown')
        edit = response.data.get('id') if isinstance(response.data,dict) else None
        if not isinstance(edit,str) or re.fullmatch(r'[A-Za-z0-9_-]{1,200}',edit) is None or edit in self.owned:
            raise UnknownWrite('edit_create_identity_unknown')
        self.owned[edit] = phase; return edit
    def path(self, edit, suffix=''):
        check(edit in self.owned,'unowned_edit'); return self.base+'/'+edit+suffix
    def read(self, edit, resource):
        allowed = {'bundles','apks','tracks','listings','details','countryAvailability/production'} | {
            'listings/'+locale+'/'+kind for locale in self.locales for kind in ('phoneScreenshots','icon')}
        check(resource in allowed,'read_resource_outside_scope')
        response = self.transport.request('GET',self.path(edit,'/'+resource))
        check(ok(response),'read_failed'); check(isinstance(response.data,dict),'malformed_read'); return response.data
    def write(self, method, edit, resource, body=None, media=None):
        allowed = (method == 'POST' and resource == 'bundles') or (method == 'PUT' and resource == 'tracks/production') or (
            method in ('POST','DELETE') and resource in {'listings/'+l+'/'+k for l in self.locales for k in ('phoneScreenshots','icon')})
        check(allowed,'write_resource_outside_scope')
        path = self.path(edit,'/'+resource)
        if media is not None: path = '/upload'+path+'?uploadType=media'
        try: response = self.transport.request(method,path,body,media)
        except (TransportError,Interrupted,OSError,TimeoutError): raise UnknownWrite('provider_write_outcome_unknown') from None
        if not ok(response):
            if definite_rejection(response): raise PolicyError('provider_write_rejected')
            raise UnknownWrite('provider_write_outcome_unknown')
        return response.data
    def validate(self, edit):
        check(ok(self.transport.request('POST',self.path(edit,':validate'))),'edit_validate_failed')
    def commit(self, edit):
        # No alternate behavior, omitted query or retry path exists.
        return self.transport.request('POST',self.path(edit,':commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW'))
    def delete(self, edit):
        response = self.transport.request('DELETE',self.path(edit))
        confirmed = deletion_confirmed(response)
        if confirmed: del self.owned[edit]
        return confirmed, response.status if isinstance(response,Response) else None

def snapshot(publisher, edit):
    state = {key:publisher.read(edit,key) for key in ('bundles','apks','tracks','listings','details','countryAvailability/production')}
    codes = []; bundle_hashes = {}
    for resource in ('bundles','apks'):
        seen = set()
        for item in array(state[resource],resource):
            check(isinstance(item,dict),'malformed_upload_entry'); number = code(item.get('versionCode'))
            check(number not in seen,'duplicate_upload_code'); seen.add(number); codes.append(number)
            binary = item if resource == 'bundles' else item.get('binary',{})
            check(isinstance(binary,dict),'malformed_upload_hash')
            value = binary.get('sha256')
            check(value is None or is_digest(value),'malformed_upload_digest')
            if resource == 'bundles': bundle_hashes[number] = value
    tracks = {}; production = None
    for track in array(state['tracks'],'tracks'):
        check(isinstance(track,dict) and isinstance(track.get('track'),str) and track['track'] not in tracks,'ambiguous_track')
        tracks[track['track']] = track
        for release in array(track,'releases'):
            check(isinstance(release,dict) and release.get('status') in ('draft','inProgress','halted','completed'),'malformed_release')
            values = [code(v) for v in array(release,'versionCodes')]; check(values and len(values) == len(set(values)),'ambiguous_release_codes'); codes.extend(values)
        if track['track'] == 'production': production = track
    check(production is not None and len(array(production,'releases')) == 1,'ambiguous_production_release')
    current = production['releases'][0]
    check(current.get('status') == 'completed' and len(current['versionCodes']) == 1,'production_not_single_completed')
    listings = array(state['listings'],'listings'); languages = [x.get('language') for x in listings if isinstance(x,dict)]
    check(len(languages) == len(listings) and len(languages) == len(set(languages)) and all(l in languages for l in publisher.locales),'existing_selected_listings_required')
    state['listings'] = sorted(listings,key=lambda x:x['language'])
    state['nonproduction'] = {name:track for name,track in tracks.items() if name != 'production'}
    state['production'] = production; state['productionCode'] = code(current['versionCodes'][0]); state['maxCode'] = max(codes)
    state['bundleHashes'] = bundle_hashes
    state['images'] = {}
    for locale in publisher.locales:
        state['images'][locale] = {}
        for kind in ('phoneScreenshots','icon'):
            images = array(publisher.read(edit,'listings/'+locale+'/'+kind),'images')
            check(all(isinstance(i,dict) and is_digest(i.get('sha256')) for i in images),'missing_image_hash')
            state['images'][locale][kind] = [i['sha256'] for i in images]
    return state

def desired_track(candidate, previous):
    result = copy.deepcopy(previous)
    release = result['releases'][0]
    release.update(versionCodes=[str(candidate.app['newVersionCode'])],name=candidate.app['newVersionName']+' ('+str(candidate.app['newVersionCode'])+')',status='completed',
        releaseNotes=[{'language':l,'text':candidate.app['releaseNotes'][l]} for l in listing_locales(candidate.app)])
    return result

def candidate_present(candidate, state):
    target = candidate.app['newVersionCode']; expected_notes = [{'language':l,'text':candidate.app['releaseNotes'][l]} for l in listing_locales(candidate.app)]
    release = state['production']['releases'][0]
    return state['productionCode'] == target and state['bundleHashes'].get(target) == candidate.bundle_sha256 and release.get('releaseNotes') == expected_notes and all(
        state['images'][l]['phoneScreenshots'] == [m.sha256 for m in candidate.screenshots[l]] and
        (candidate.icon is None or state['images'][l]['icon'] == [candidate.icon.sha256]) for l in listing_locales(candidate.app))

def check_preserved(candidate, previous, current):
    for key in ('listings','details','countryAvailability/production','nonproduction'):
        check(previous[key] == current[key],'unrelated_payload_changed')
    if candidate.icon is None:
        check(all(previous['images'][l]['icon'] == current['images'][l]['icon'] for l in listing_locales(candidate.app)),'unrequested_icon_changed')

def submit_candidate(candidate, transport, checkpoint=None, family='calculator9'):
    report = {'ok':False,'status':'started','package':candidate.package,'versionName':'1.2.0' if family == 'calculator9' else candidate.app.get('newVersionName'),'versionCode':candidate.app.get('newVersionCode'),
        'archiveSha256':candidate.archive_sha256,'bundleSha256':candidate.bundle_sha256,'nativeQaSha256':candidate.native_qa_sha256,
        'sourceCommit':candidate.app.get('reviewedSourceCommit'),'publicReleaseConfirmed':False,'steps':[],
        'commit':{'attempted':False,'outcome':'not_attempted'},'cleanup':[],'readbackVerified':False}
    publisher = None; uncertain_commit = None; committed = False
    def save(stage):
        report['steps'].append(stage)
        if checkpoint:
            try: checkpoint(copy.deepcopy(report))
            except OSError: raise JournalError('receipt_write_failed') from None
    try:
        publisher = ScopedPublisher(candidate,transport,family); save('scope_verified')
        edit = publisher.create('initial'); report['editId'] = edit; save('owned_edit_created')
        before = snapshot(publisher,edit); save('fresh_snapshot_read')
        target = candidate.app['newVersionCode']
        if before['productionCode'] == target:
            if not candidate_present(candidate,before): raise UnknownWrite('existing_candidate_state_mismatch')
            report['ok'] = True; report['status'] = 'noop_already_present'
        else:
            if before['maxCode'] >= target: raise UnknownWrite('candidate_or_newer_code_already_exists')
            check(before['productionCode'] == candidate.app['previousProductionCode'] and before['maxCode'] == candidate.app['previousMaxCode'] and
                (target == before['maxCode']+1 or allows_reserved_game_step(candidate.app,before['maxCode'],family)),'fresh_previous_code_or_max_mismatch')
            save('before_bundle_upload')
            uploaded = publisher.write('POST',edit,'bundles',media=MediaPayload(candidate.aab,'application/octet-stream'))
            check(isinstance(uploaded,dict) and code(uploaded.get('versionCode')) == target and uploaded.get('sha256') == candidate.bundle_sha256,'uploaded_bundle_identity_mismatch')
            for locale in publisher.locales:
                save('before_'+locale+'_images')
                for kind,images in [('phoneScreenshots',candidate.screenshots[locale])] + ([('icon',(candidate.icon,))] if candidate.icon else []):
                    publisher.write('DELETE',edit,'listings/'+locale+'/'+kind)
                    for image in images:
                        response = publisher.write('POST',edit,'listings/'+locale+'/'+kind,media=MediaPayload(image.data,'image/png'))
                        check(isinstance(response,dict) and isinstance(response.get('image'),dict) and response['image'].get('sha256') == image.sha256,'uploaded_image_hash_mismatch')
            track = desired_track(candidate,before['production']); save('before_production_track')
            check(publisher.write('PUT',edit,'tracks/production',track) == track,'production_track_response_mismatch')
            staged = snapshot(publisher,edit); check_preserved(candidate,before,staged)
            check(candidate_present(candidate,staged) and staged['production'] == track,'staged_candidate_mismatch')
            publisher.validate(edit); save('validated_before_commit')
            report['commit']['attempted'] = True; report['commit']['outcome'] = 'unknown'
            # Journal before the one irreversible API call. A failed journal never sends it.
            save('commit_about_to_send')
            uncertain_commit = edit
            response = publisher.commit(edit)
            if ok(response) and isinstance(response.data,dict) and response.data.get('id') == edit:
                committed = True; uncertain_commit = None; del publisher.owned[edit]
                report['commit']['outcome'] = 'acknowledged'; save('commit_acknowledged')
            elif definite_rejection(response):
                uncertain_commit = None; report['commit']['outcome'] = 'rejected'
                if isinstance(response.data,dict) and response.data.get('reason') == 'CHANGES_ALREADY_IN_REVIEW':
                    report['status'] = 'blocked_in_review'
                raise PolicyError('commit_rejected')
            else: raise UnknownWrite('commit_outcome_unknown')
            readback = publisher.create('readback'); report['readbackEditId'] = readback; save('owned_readback_created')
            after = snapshot(publisher,readback); check_preserved(candidate,before,after)
            check(candidate_present(candidate,after) and after['production'] == track,'committed_readback_mismatch')
            report['readbackVerified'] = True; report['ok'] = True; report['status'] = 'submitted_for_review'
    except Exception as error:
        report['ok'] = False
        report['stopReason'] = str(error) if isinstance(error,(PolicyError,UnknownWrite,JournalError)) else type(error).__name__
        if uncertain_commit or committed or isinstance(error,UnknownWrite): report['status'] = 'reconciliation_required'
        elif report['status'] != 'blocked_in_review': report['status'] = 'stopped'
    finally:
        if publisher:
            for edit,phase in list(publisher.owned.items()):
                if edit == uncertain_commit:
                    report['cleanup'].append({'editId':edit,'phase':phase,'attempted':False,'confirmed':False,'reason':'commit_outcome_unknown_do_not_delete'})
                    continue
                item = {'editId':edit,'phase':phase,'attempted':True,'confirmed':False,'httpStatus':None}
                try: item['confirmed'],item['httpStatus'] = publisher.delete(edit)
                except Exception: item['reason'] = 'cleanup_transport_unknown'
                report['cleanup'].append(item)
            if any(not x['confirmed'] for x in report['cleanup']): report['ok'] = False; report['status'] = 'reconciliation_required'
        try: save('finished')
        except JournalError:
            report['ok'] = False; report['status'] = 'reconciliation_required' if committed or uncertain_commit else 'stopped'; report['stopReason'] = 'receipt_write_failed'
    return report

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl): return None

class HttpTransport:
    def __init__(self, token, catalog, inspect_only=True, family='calculator9'):
        self._expected = scope(family); self._family = family
        require(set(catalog) == set(self._expected) and type(inspect_only) is bool,'Transport catalog/mode outside fixed scope')
        self._catalog = catalog; self._inspect_only = inspect_only; self._owned_inspection_edits = set()
        require(isinstance(token,str) and bool(token),'Missing Google access token')
        self._token = token; self._opener = build_opener(NoRedirect())
    def request(self, method, path, body=None, media=None):
        match = re.fullmatch(r'(/upload)?/androidpublisher/v3/applications/([^/]+)/edits(?:/([A-Za-z0-9_-]{1,200})(.*))?',path)
        check(match is not None and match[2] in self._expected,'publisher_path_outside_fixed_scope')
        upload,package,edit,tail = match.groups(); tail = tail or ''
        locales = () if self._inspect_only else listing_locales(self._catalog[package])
        images = {'/listings/'+l+'/'+kind for l in locales for kind in ('phoneScreenshots','icon')}
        allowed = False
        if self._inspect_only:
            allowed = upload is None and media is None and ((edit is None and method == 'POST' and body == {}) or
                ((package,edit) in self._owned_inspection_edits and body is None and
                 ((method == 'GET' and tail == '/listings') or (method == 'DELETE' and tail == ''))))
        elif upload:
            resource = tail.removesuffix('?uploadType=media')
            allowed = bool(edit) and method == 'POST' and tail == resource+'?uploadType=media' and (resource == '/bundles' or resource in images) and body is None and isinstance(media,MediaPayload)
            if allowed:
                allowed = isinstance(media.data,bytes) and 0 < len(media.data) <= 128*1024*1024 and media.content_type == ('application/octet-stream' if resource == '/bundles' else 'image/png')
        elif media is None:
            if edit is None: allowed = method == 'POST' and body == {}
            elif method == 'GET': allowed = body is None and tail in {'/bundles','/apks','/tracks','/listings','/details','/countryAvailability/production'} | images
            elif method == 'DELETE': allowed = body is None and (tail == '' or tail in images)
            elif method == 'POST': allowed = body is None and tail in (':validate',':commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW')
            elif method == 'PUT' and tail == '/tracks/production' and isinstance(body,dict):
                releases = body.get('releases')
                allowed = set(body) == {'track','releases'} and body.get('track') == 'production' and isinstance(releases,list) and len(releases) == 1 and isinstance(releases[0],dict)
                if allowed:
                    release = releases[0]; notes = release.get('releaseNotes')
                    allowed = release.get('versionCodes') == [str(self._expected[package][1])] and release.get('status') == 'completed' and release.get('name') == version(package,self._family)+' ('+str(self._expected[package][1])+')' and isinstance(notes,list) and len(notes) == len(locales) and all(isinstance(n,dict) and set(n) == {'language','text'} and isinstance(n['text'],str) and 1 <= len(n['text']) <= 500 for n in notes) and {n['language'] for n in notes} == set(locales)
        check(allowed,'publisher_method_resource_or_commit_behavior_outside_scope')
        data = media.data if media else json.dumps(body,separators=(',',':')).encode() if body is not None else None
        headers = {'Authorization':'Bearer '+self._token,'Content-Type':media.content_type if media else 'application/json'}
        request = Request('https://androidpublisher.googleapis.com'+path,data=data,method=method,headers=headers)
        try:
            with self._opener.open(request,timeout=10 if method == 'DELETE' else 20 if self._inspect_only else 120 if method in ('POST','PUT') else 20) as response:
                raw = response.read(4*1024*1024+1)
                if len(raw) > 4*1024*1024: return Response(response.status,None)
                try: value = strict_json(raw) if raw else None
                except (ValueError,UnicodeError): value = None
                if self._inspect_only and method == 'POST' and edit is None and response.status == 200 and isinstance(value,dict):
                    owned = value.get('id')
                    if isinstance(owned,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}',owned): self._owned_inspection_edits.add((package,owned))
                if self._inspect_only and method == 'DELETE' and deletion_confirmed(Response(response.status,value)): self._owned_inspection_edits.discard((package,edit))
                return Response(response.status,value)
        except HTTPError as error:
            # Only this public, fixed reason is retained; never raw provider/credential bodies.
            reason = None
            try:
                value = json.loads(error.read(64*1024))
                if any(x.get('reason') == 'CHANGES_ALREADY_IN_REVIEW' for x in value.get('error',{}).get('details',[]) if isinstance(x,dict)):
                    reason = 'CHANGES_ALREADY_IN_REVIEW'
            except (ValueError,UnicodeError,AttributeError,TypeError,OSError): pass
            return Response(error.code,{'reason':reason})
        except (URLError,OSError,TimeoutError): raise TransportError('Publisher transport failed') from None
