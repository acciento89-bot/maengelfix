"""Manual main-only entrypoints. No network or command runs during import."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import stat
import tempfile
from candidate import BundleVerifier, CandidateError, EXPECTED, digest, load_catalog, numeric_id, require, strict_json, validate_archive, listing_locales
from release_asset import AssetError, GitHubClient, OWN_REPOSITORY, fetch_candidate_asset, verify_provenance
from publisher import HttpTransport, Interrupted, submit_candidate
from locale_inventory import inspect_existing_locales

def execution_context(environ):
    require(environ.get('GITHUB_REPOSITORY') == OWN_REPOSITORY and environ.get('GITHUB_REF') == 'refs/heads/main' and
        environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and environ.get('GITHUB_RUN_ATTEMPT') == '1',
        'Only first-attempt manual own-main execution is permitted')
    commit = environ.get('GITHUB_SHA',''); require(re.fullmatch(r'[a-f0-9]{40}',commit), 'Invalid submitter source commit')
    require(environ.get('GITHUB_WORKFLOW_REF') == OWN_REPOSITORY+'/.github/workflows/navoops-calculator-production-submit.yml@refs/heads/main' and
        environ.get('GITHUB_WORKFLOW_SHA') == commit,'Exact manual submitter workflow/main SHA required')
    return {'repository':OWN_REPOSITORY,'commit':commit,'runId':numeric_id(environ.get('GITHUB_RUN_ID'))}

def prepare_candidate(github, asset_id, archive_sha256, package, catalog, catalog_sha256, verifier, output, context, now=None):
    output = Path(output); require(output.is_absolute() and not output.exists() and not output.is_symlink(), 'A fresh absolute transfer folder is required')
    require(package in EXPECTED, 'One exact calculator required for candidate preparation')
    listing_locales(catalog[package])
    raw, asset = fetch_candidate_asset(github,asset_id,archive_sha256,package,catalog)
    candidate = validate_archive(raw,archive_sha256,package,catalog,verifier,now)
    ci = verify_provenance(github,candidate)
    attestation = {'schema':1,'package':package,'archiveSha256':archive_sha256,'bundleSha256':candidate.bundle_sha256,
        'nativeQaSha256':candidate.native_qa_sha256,'catalogSha256':catalog_sha256,'sourceCommit':candidate.app['reviewedSourceCommit'],
        'submitterRepository':context['repository'],'submitterCommit':context['commit'],'submitterRunId':context['runId'],
        'asset':asset,'ci':ci,'verifiedAtUTC':(now or datetime.now(timezone.utc)).isoformat()}
    output.mkdir(parents=True)
    (output/'candidate.zip').write_bytes(raw)
    (output/'attestation.json').write_text(json.dumps(attestation,sort_keys=True,indent=2)+'\n')
    return attestation

def verify_transfer(directory, archive_sha256, attestation_sha256, package, catalog, catalog_sha256, verifier, context, now=None):
    directory = Path(directory)
    require(directory.is_absolute() and directory.is_dir() and not directory.is_symlink() and
        {p.name for p in directory.iterdir()} == {'candidate.zip','attestation.json'}, 'Transfer folder must contain exactly two owned files')
    for file in directory.iterdir():
        info = file.lstat(); require(stat.S_ISREG(info.st_mode) and not file.is_symlink() and info.st_nlink == 1, 'Transfer link/special file rejected')
    attestation_raw = (directory/'attestation.json').read_bytes()
    require(len(attestation_raw) <= 128*1024 and digest(attestation_raw) == attestation_sha256, 'Transfer attestation SHA mismatch')
    attestation = strict_json(attestation_raw)
    require(attestation.get('schema') == 1 and attestation.get('package') == package and attestation.get('archiveSha256') == archive_sha256 and
        attestation.get('catalogSha256') == catalog_sha256 and attestation.get('submitterRepository') == context['repository'] and
        attestation.get('submitterCommit') == context['commit'] and attestation.get('submitterRunId') == context['runId'], 'Transfer identity/run/catalog mismatch')
    raw = (directory/'candidate.zip').read_bytes()
    candidate = validate_archive(raw,archive_sha256,package,catalog,verifier,now)
    require(attestation.get('bundleSha256') == candidate.bundle_sha256 and attestation.get('nativeQaSha256') == candidate.native_qa_sha256 and
        attestation.get('sourceCommit') == candidate.app['reviewedSourceCommit'], 'Transferred verified candidate bytes differ')
    return candidate

def write_receipt(path, report):
    path = Path(path); require(path.is_absolute() and not path.is_symlink(), 'Absolute owned receipt path required')
    if path.exists(): require(path.is_file() and path.stat().st_nlink == 1, 'Receipt link/special file rejected')
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.receipt-',delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(report,stream,sort_keys=True,indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        except Exception: temporary.unlink(missing_ok=True); raise
    try: os.replace(temporary,path)
    finally: temporary.unlink(missing_ok=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description='One approved calculator production candidate, manual main only')
    parser.add_argument('mode',choices=('inspect','prepare','verify-transfer','submit'))
    parser.add_argument('--package',required=True,choices=['all-nine']+sorted(EXPECTED)); parser.add_argument('--archive-sha256')
    parser.add_argument('--catalog',default=str(Path(__file__).with_name('catalog.json'))); parser.add_argument('--catalog-sha256',required=True)
    parser.add_argument('--bundletool'); parser.add_argument('--bundletool-sha256')
    parser.add_argument('--report',required=True); parser.add_argument('--asset-id'); parser.add_argument('--output')
    parser.add_argument('--directory'); parser.add_argument('--attestation-sha256')
    args = parser.parse_args(argv); report = {'ok':False,'status':args.mode+'_rejected','package':args.package}
    def interrupted(signum, frame): raise Interrupted('interrupted')
    signal.signal(signal.SIGTERM,interrupted); signal.signal(signal.SIGINT,interrupted)
    try:
        context = execution_context(os.environ)
        catalog = load_catalog(args.catalog,args.catalog_sha256)
        expected_operation = 'inspect' if args.mode == 'inspect' else 'submit'
        require(os.environ.get('SCOPED_CALCULATOR_OPERATION','inspect') == expected_operation,'Explicit matching workflow operation required')
        if args.mode == 'inspect':
            require(not any((args.archive_sha256,args.bundletool,args.bundletool_sha256,args.asset_id,args.output,args.directory,args.attestation_sha256)), 'Inspection accepts no candidate or write arguments')
            metadata = {'catalogSha256':args.catalog_sha256,'submitter':context}
            report = inspect_existing_locales(args.package,catalog,HttpTransport(os.environ.get('TOKEN'),catalog,inspect_only=True),
                lambda value:write_receipt(args.report,{**value,**metadata}))
            report.update(metadata)
        else:
            require(args.package in EXPECTED and args.archive_sha256 and args.bundletool and args.bundletool_sha256,'One exact calculator and full verification arguments required')
            listing_locales(catalog[args.package])
            verifier = BundleVerifier(args.bundletool,args.bundletool_sha256)
        if args.mode == 'prepare':
            require(args.asset_id and args.output and not args.directory and not args.attestation_sha256,'Prepare arguments incomplete')
            attestation = prepare_candidate(GitHubClient(os.environ.get('GH_TOKEN')),args.asset_id,args.archive_sha256,args.package,catalog,args.catalog_sha256,verifier,args.output,context)
            attestation_sha = digest((Path(args.output)/'attestation.json').read_bytes())
            report = {'ok':True,'status':'candidate_prepared_no_google_identity','package':args.package,'attestation':attestation,'attestationSha256':attestation_sha}
            output = os.environ.get('GITHUB_OUTPUT')
            if output:
                with open(output,'a') as stream:
                    stream.write('archive_sha256='+args.archive_sha256+'\nattestation_sha256='+attestation_sha+'\n')
        elif args.mode != 'inspect':
            require(args.directory and args.attestation_sha256 and not args.asset_id and not args.output,'Transfer arguments incomplete')
            candidate = verify_transfer(args.directory,args.archive_sha256,args.attestation_sha256,args.package,catalog,args.catalog_sha256,verifier,context)
            if args.mode == 'verify-transfer': report = {'ok':True,'status':'same_candidate_verified_before_google_identity','package':args.package,'bundleSha256':candidate.bundle_sha256}
            else:
                report = submit_candidate(candidate,HttpTransport(os.environ.get('TOKEN'),catalog,inspect_only=False),lambda value:write_receipt(args.report,value))
    except Exception as error:
        report = {'ok':False,'status':args.mode+'_rejected','package':args.package,'errorType':type(error).__name__}
        if isinstance(error,(CandidateError,AssetError)): report['reason'] = str(error)
    write_receipt(args.report,report)
    return 0 if report.get('ok') else 2

if __name__ == '__main__': raise SystemExit(main())
