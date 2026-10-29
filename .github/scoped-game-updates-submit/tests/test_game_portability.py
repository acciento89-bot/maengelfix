"""Run the actual installed CI suite in an isolated repository copy with external artifacts denied."""
import os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from fixtures import HERE

class GamePortabilityTests(unittest.TestCase):
    def test_copied_repository_suite_needs_no_private_manifest_or_mac_binary_paths(self):
        with tempfile.TemporaryDirectory(prefix='game-portable-repo-')as temp:
            root=Path(temp);code=root/'.github/scoped-game-updates-submit';code.parent.mkdir();shutil.copytree(HERE,code,ignore=shutil.ignore_patterns('__pycache__'));workflows=code.parent/'workflows';workflows.mkdir()
            for name in ['navoops-calculator-production-submit.yml','navoops-game-updates-production-submit.yml']:shutil.copy2(HERE.parent/'workflows'/name,workflows/name)
            self.assertFalse((root/'source-evidence-originals.json').exists())
            driver=r"""
import builtins,os,sys,unittest
from pathlib import Path
root=Path(sys.argv[1]).resolve();tests=root/'.github/scoped-game-updates-submit/tests';sys.path.insert(0,str(tests))
original_path_open=Path.open;original_open=builtins.open
def deny_external(path):
    if isinstance(path,(str,bytes,os.PathLike)):
        value=os.fsdecode(path)
        if value.startswith('/Volumes/')and not Path(value).resolve().is_relative_to(root):raise AssertionError('CI attempted outside Mac artifact access: '+value)
def path_open(path,*args,**kwargs):deny_external(path);return original_path_open(path,*args,**kwargs)
def plain_open(path,*args,**kwargs):deny_external(path);return original_open(path,*args,**kwargs)
Path.open=path_open;builtins.open=plain_open
suite=unittest.defaultTestLoader.discover(str(tests))
def selected(node):
    if isinstance(node,unittest.TestSuite):return unittest.TestSuite(selected(item)for item in node)
    # Exclude only this outer subprocess driver, avoiding recursion; no product/input test is skipped.
    if node.id().endswith('GamePortabilityTests.test_copied_repository_suite_needs_no_private_manifest_or_mac_binary_paths'):return unittest.TestSuite()
    return node
result=unittest.TextTestRunner(verbosity=1).run(selected(suite));assert result.testsRun>=100 and not result.skipped
raise SystemExit(0 if result.wasSuccessful() else 2)
"""
            result=subprocess.run([sys.executable,'-c',driver,str(root)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            self.assertEqual(result.returncode,0,result.stdout)
            print('Isolated copied-repository CI suite (external Mac inputs blocked):\n'+result.stdout)
