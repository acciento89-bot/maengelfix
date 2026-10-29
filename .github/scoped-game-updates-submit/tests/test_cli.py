import json, os, tempfile, unittest
from pathlib import Path
from fixtures import Fixture, Verifier, PACKAGE, NOW, digest
from test_release_asset import GitHub
from unittest.mock import patch
from fixtures import HERE
from test_locale_inventory import ReadOnlyTransport
import cli

CTX={'repository':'acciento89-bot/maengelfix','commit':'e'*40,'runId':123}
class CliTests(unittest.TestCase):
    def test_only_first_manual_main_own_repository_execution_allowed(self):
        good={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-calculator-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40}
        self.assertEqual(cli.execution_context(good),CTX)
        for key,value in [('GITHUB_REPOSITORY','other/repo'),('GITHUB_REF','refs/heads/feature'),('GITHUB_EVENT_NAME','push'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_WORKFLOW_REF','acciento89-bot/maengelfix/.github/workflows/unrelated.yml@refs/heads/main'),('GITHUB_WORKFLOW_SHA','f'*40),('GITHUB_SHA','not-sha'),('GITHUB_RUN_ID','1;exit')]:
            with self.subTest(key=key),self.assertRaises(ValueError):cli.execution_context({**good,key:value})
    def test_transfer_uses_exact_two_owned_files_and_binds_all_metadata(self):
        f=Fixture();g=GitHub(f)
        with tempfile.TemporaryDirectory()as temp:
            dest=Path(temp)/'fresh';att=cli.prepare_candidate(g,91,digest(g.raw),PACKAGE,f.catalog,'f'*64,Verifier(),dest,CTX,NOW)
            self.assertEqual(set(p.name for p in dest.iterdir()),{'candidate.zip','attestation.json'})
            c=cli.verify_transfer(dest,digest(g.raw),digest((dest/'attestation.json').read_bytes()),PACKAGE,f.catalog,'f'*64,Verifier(),CTX,NOW)
            self.assertEqual(c.bundle_sha256,digest(f.aab));self.assertEqual(att['submitterRunId'],123)
            with self.assertRaises(ValueError):cli.prepare_candidate(g,91,digest(g.raw),PACKAGE,f.catalog,'f'*64,Verifier(),dest,CTX,NOW)
    def test_modified_archive_attestation_wrong_package_catalog_and_previous_run_fail(self):
        for mode in ['archive','attestation','package','catalog','run','extra_file','symlink']:
            f=Fixture();g=GitHub(f)
            with tempfile.TemporaryDirectory()as temp:
                dest=Path(temp)/'fresh';cli.prepare_candidate(g,91,digest(g.raw),PACKAGE,f.catalog,'f'*64,Verifier(),dest,CTX,NOW)
                attsha=digest((dest/'attestation.json').read_bytes());pkg=PACKAGE;catsha='f'*64;context=CTX
                if mode=='archive':(dest/'candidate.zip').write_bytes(g.raw+b'changed')
                elif mode=='attestation':(dest/'attestation.json').write_bytes(b'{}')
                elif mode=='package':pkg='de.kamilunavo.hydrocalc'
                elif mode=='catalog':catsha='0'*64
                elif mode=='run':context={**CTX,'runId':124}
                elif mode=='extra_file':(dest/'unexpected').write_bytes(b'x')
                else:(dest/'candidate.zip').unlink();(dest/'candidate.zip').symlink_to(Path(temp)/'outside.zip')
                with self.subTest(mode=mode),self.assertRaises(ValueError):cli.verify_transfer(dest,digest(g.raw),attsha,pkg,f.catalog,catsha,Verifier(),context,NOW)

    def test_inspect_needs_no_candidate_download_java_or_submit_and_preserves_report(self):
        environ={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-calculator-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_CALCULATOR_OPERATION':'inspect','TOKEN':'unit-only'}
        with tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,environ,clear=True),patch.object(cli,'BundleVerifier',side_effect=AssertionError('Java prohibited')),patch.object(cli,'GitHubClient',side_effect=AssertionError('GitHub download prohibited')),patch.object(cli,'submit_candidate',side_effect=AssertionError('Submit prohibited')),patch.object(cli,'HttpTransport',return_value=ReadOnlyTransport())as http:
            report=Path(temp)/'inventory.json'
            result=cli.main(['inspect','--package','all-nine','--catalog-sha256',digest((HERE/'catalog.json').read_bytes()),'--report',str(report)])
            self.assertEqual(result,0);data=json.loads(report.read_text());self.assertTrue(data['ok']);self.assertEqual(len(data['apps']),9)
            self.assertEqual(http.call_args.kwargs,{'inspect_only':True})
    def test_missing_explicit_submit_or_batch_submit_never_downloads_candidate(self):
        environ={'GITHUB_REPOSITORY':CTX['repository'],'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'123','GITHUB_WORKFLOW_REF':'acciento89-bot/maengelfix/.github/workflows/navoops-calculator-production-submit.yml@refs/heads/main','GITHUB_WORKFLOW_SHA':'e'*40,'SCOPED_CALCULATOR_OPERATION':'inspect'}
        for operation,package in [('inspect',PACKAGE),('submit','all-nine')]:
            with self.subTest(operation=operation,package=package),tempfile.TemporaryDirectory()as temp,patch.dict(os.environ,{**environ,'SCOPED_CALCULATOR_OPERATION':operation},clear=True),patch.object(cli,'GitHubClient',side_effect=AssertionError('Must not download'))as github:
                result=cli.main(['prepare','--package',package,'--catalog-sha256',digest((HERE/'catalog.json').read_bytes()),'--report',str(Path(temp)/'receipt.json')])
                self.assertEqual(result,2);github.assert_not_called()
