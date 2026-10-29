"""Read-only GitHub ownership/provenance checks. No Google identity or free URLs."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from candidate import EXPECTED, MAX_ARCHIVE, CandidateError, digest, is_digest, numeric_id, require, strict_json

from business_policy import scope, version, fixed_apps, require_ready

OWN_REPOSITORY = 'acciento89-bot/maengelfix'
class AssetError(ValueError): pass

CALCULATOR_REPOSITORIES = frozenset({'acciento89-bot/BrennerCalc','acciento89-bot/HydroCalc',
    'acciento89-bot/MAGCalc','acciento89-bot/SHK','acciento89-bot/AnlagenVolumen'})

def metadata_route(path, family='calculator9'):
    repositories = CALCULATOR_REPOSITORIES if family == 'calculator9' else frozenset(a['repository'] for a in fixed_apps().values())
    scope(family)
    # Diagnostics can echo only these bounded credential-free GET routes.
    own = '/repos/'+OWN_REPOSITORY
    require(isinstance(path,str),'GitHub metadata route outside fixed scope')
    if path == own: return path
    asset = re.fullmatch(re.escape(own)+r'/releases/assets/([1-9][0-9]{0,18})',path)
    if asset: numeric_id(asset[1]); return path
    if re.fullmatch(re.escape(own)+r'/releases\?per_page=100&page=(?:[1-9]|10)',path): return path
    action = re.fullmatch(r'/repos/(acciento89-bot/[A-Za-z0-9_-]+)/actions/(?:runs|artifacts)/([1-9][0-9]{0,18})',path)
    if action and action[1] in repositories: numeric_id(action[2]); return path
    raise CandidateError('GitHub metadata route outside fixed scope')

def metadata_failure(path, status=None):
    code = str(status) if type(status)is int and 100 <= status <= 599 else 'unknown'
    return AssetError('GitHub metadata request failed: HTTP'+code+'; GET '+path)


def fetch_candidate_asset(github, asset_id, archive_sha256, package, catalog, family='calculator9'):
    expected = scope(family)
    require(package in expected and package in catalog and is_digest(archive_sha256), 'Candidate scope/digest invalid')
    asset_id = numeric_id(asset_id); app = catalog[package]
    require(github.json('/repos/'+OWN_REPOSITORY).get('full_name') == OWN_REPOSITORY, 'Candidate repository mismatch')
    asset = github.json('/repos/'+OWN_REPOSITORY+'/releases/assets/'+str(asset_id))
    if family == 'business12': require_ready(app)
    expected_name = ('calculator-candidate-' if family == 'calculator9' else 'business-candidate-')+package+'-'+version(package,family)+'-'+str(app['newVersionCode'])+'.zip'
    require(asset.get('id') == asset_id and type(asset.get('id')) is int and asset.get('name') == expected_name and
        asset.get('state') == 'uploaded' and type(asset.get('size')) is int and 0 < asset['size'] <= MAX_ARCHIVE and
        asset.get('digest') == 'sha256:'+archive_sha256, 'Candidate asset metadata mismatch')
    members = []
    for page in range(1,11):
        releases = github.json('/repos/'+OWN_REPOSITORY+'/releases?per_page=100&page='+str(page))
        require(isinstance(releases, list) and len(releases) <= 100, 'Malformed draft release inventory')
        for release in releases:
            require(isinstance(release, dict) and isinstance(release.get('assets'), list), 'Malformed release asset inventory')
            for member in release['assets']:
                if member.get('id') == asset_id: members.append((release, member))
        if len(releases) < 100: break
    require(len(members) == 1, 'Asset must belong to exactly one own draft release')
    release, member = members[0]
    require(release.get('draft') is True and member.get('name') == expected_name and member.get('size') == asset['size'], 'Asset is published or draft membership differs')
    release_id = numeric_id(release.get('id'))
    raw = github.download_asset(asset_id)
    require(len(raw) == asset['size'] and digest(raw) == archive_sha256, 'Downloaded draft asset differs')
    return raw, {'repository':OWN_REPOSITORY,'releaseId':release_id,'assetId':asset_id,'archiveSha256':archive_sha256}

def verify_provenance(github, candidate, family='calculator9'):
    require(candidate.package in scope(family), 'CI identity outside fixed family')
    if family == 'business12': require_ready(candidate.app)
    app = candidate.app; summary = {}
    sections = [('source','sourceArtifactName'), ('signing','signedArtifactName')] if family == 'calculator9' or candidate.app['route'] == 'central_kms' else [('source','signedArtifactName')]
    for section, name in sections:
        part = candidate.manifest[section]; run_id = numeric_id(part['runId']); artifact_id = numeric_id(part['artifactId'])
        base = '/repos/'+app['repository']+'/actions/'
        run = github.json(base+'runs/'+str(run_id))
        require(run.get('id') == run_id and run.get('head_sha') == app['reviewedSourceCommit'] and run.get('head_branch') == 'main' and
            run.get('event') == 'workflow_dispatch' and run.get('path') == part['workflow'] and run.get('status') == 'completed' and run.get('conclusion') == 'success' and
            run.get('repository',{}).get('full_name') == app['repository'] and run.get('head_repository',{}).get('full_name') == app['repository'], 'Official selected source/sign run mismatch')
        artifact = github.json(base+'artifacts/'+str(artifact_id)); source = artifact.get('workflow_run',{})
        require(type(artifact.get('id')) is int and artifact['id'] == artifact_id and artifact.get('name') == app[name] and artifact.get('expired') is False and
            artifact.get('digest') == 'sha256:'+part['artifactArchiveSha256'] and source.get('id') == run_id and
            source.get('head_sha') == app['reviewedSourceCommit'] and source.get('head_branch') == 'main', 'Official immutable source/sign artifact mismatch')
        summary[section+'RunId'] = run_id; summary[section+'ArtifactId'] = artifact_id
    return summary

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl): return None

class GitHubClient:
    def __init__(self, token, family='calculator9'):
        scope(family); self._family = family
        require(isinstance(token,str) and bool(token), 'Missing GitHub read token')
        self._token = token; self._opener = build_opener(NoRedirect())
    def json(self, path):
        path = metadata_route(path,self._family)
        try:
            request = Request('https://api.github.com'+path, method='GET', headers={'Authorization':'Bearer '+self._token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ScopedCalculatorCandidate'})
            with self._opener.open(request, timeout=20) as response:
                if response.status != 200: raise metadata_failure(path,response.status)
                raw = response.read(8*1024*1024+1)
                if len(raw) > 8*1024*1024: raise metadata_failure(path,response.status)
                try: return strict_json(raw)
                except CandidateError: raise metadata_failure(path,response.status) from None
        except HTTPError as error: raise metadata_failure(path,error.code) from None
        except (URLError, OSError, TimeoutError): raise metadata_failure(path) from None
    def download_asset(self, asset_id):
        asset_id = numeric_id(asset_id)
        url = 'https://api.github.com/repos/'+OWN_REPOSITORY+'/releases/assets/'+str(asset_id)
        request = Request(url, headers={'Authorization':'Bearer '+self._token,'Accept':'application/octet-stream','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ScopedCalculatorCandidate'})
        try:
            try: response = self._opener.open(request, timeout=120)
            except HTTPError as redirect:
                if redirect.code not in (301,302,303,307,308): raise
                location = redirect.headers.get('Location',''); target = urlsplit(location)
                require(target.scheme == 'https' and target.hostname == 'release-assets.githubusercontent.com' and
                    target.port in (None,443) and target.username is None and target.password is None and not target.fragment,
                    'Untrusted GitHub asset redirect')
                # Never send the repository token to a CDN or log its signed URL.
                response = self._opener.open(Request(location,headers={'User-Agent':'ScopedCalculatorCandidate'}),timeout=120)
            with response:
                require(response.status == 200, 'Candidate download HTTP status rejected')
                raw = response.read(MAX_ARCHIVE+1); require(len(raw) <= MAX_ARCHIVE, 'Candidate download too large'); return raw
        except (HTTPError, URLError, OSError, TimeoutError): raise AssetError('GitHub candidate download failed') from None
