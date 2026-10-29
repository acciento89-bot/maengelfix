"""Read-only GitHub ownership/provenance checks. No Google identity or free URLs."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from candidate import EXPECTED, MAX_ARCHIVE, CandidateError, digest, is_digest, numeric_id, require, strict_json

OWN_REPOSITORY = 'acciento89-bot/maengelfix'
class AssetError(ValueError): pass

def fetch_candidate_asset(github, asset_id, archive_sha256, package, catalog):
    require(package in EXPECTED and package in catalog and is_digest(archive_sha256), 'Candidate scope/digest invalid')
    asset_id = numeric_id(asset_id); app = catalog[package]
    require(github.json('/repos/'+OWN_REPOSITORY).get('full_name') == OWN_REPOSITORY, 'Candidate repository mismatch')
    asset = github.json('/repos/'+OWN_REPOSITORY+'/releases/assets/'+str(asset_id))
    expected_name = 'calculator-candidate-'+package+'-1.2.0-'+str(app['newVersionCode'])+'.zip'
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

def verify_provenance(github, candidate):
    app = candidate.app; summary = {}
    for section, name in [('source','sourceArtifactName'), ('signing','signedArtifactName')]:
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
    def __init__(self, token):
        require(isinstance(token,str) and bool(token), 'Missing GitHub read token')
        self._token = token; self._opener = build_opener(NoRedirect())
    def json(self, path):
        require(path.startswith('/repos/acciento89-bot/') and '\\' not in path and '..' not in path and '\n' not in path, 'GitHub API path outside owner scope')
        try:
            request = Request('https://api.github.com'+path, headers={'Authorization':'Bearer '+self._token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ScopedCalculatorCandidate'})
            with self._opener.open(request, timeout=20) as response:
                require(response.status == 200, 'GitHub metadata HTTP status rejected')
                raw = response.read(8*1024*1024+1); require(len(raw) <= 8*1024*1024, 'GitHub metadata too large')
                return strict_json(raw)
        except (HTTPError, URLError, OSError, TimeoutError): raise AssetError('GitHub metadata request failed') from None
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
