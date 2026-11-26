"""Ambiguous input and release traversal regression fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from rdc_operator.common import KitError, read_json
from rdc_operator.core import execute_request
from scripts import build_release

class ReviewTests(unittest.TestCase):
    def test_json_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.json'
            for raw in ('{"a":1,"a":2}', '{"a":{"b":1,"b":2}}','{"a":NaN}','{"a":Infinity}','{"a":1e999}','{"a":-1e999}'):
                with self.subTest(raw=raw):
                    path.write_text(raw,encoding='utf-8')
                    with self.assertRaises(KitError): read_json(path)
            path.write_text('{"a":1.25,"b":"中文"}',encoding='utf-8-sig')
            self.assertEqual(read_json(path),{'a':1.25,'b':'中文'})
    def test_stdin_duplicate_rejected_before_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cfg=root/'config.json';cfg.write_text('{"schema_version":1}')
            run=subprocess.run([sys.executable,'-m','rdc_operator','--config',str(cfg),'--state',str(root/'state'),'call','-'],input='{"request_id":"one","request_id":"two","action":"terminal.snapshot","args":{}}',capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,2);self.assertEqual(json.loads(run.stderr)['error']['code'],'invalid_json');self.assertFalse((root/'state').exists())
    def test_bool_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state'
            with self.assertRaises(KitError) as error: execute_request({'request_id':'one','action':'terminal.snapshot','args':{}},{'schema_version':True},state)
            self.assertEqual(error.exception.code,'invalid_config');self.assertFalse(state.exists())
    def test_pruned_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in ('README.md','rdc_operator/b.py','rdc_operator/A.py','site/.nojekyll','.venv-mcp/lib/private.py','evidence/private.json','site/evidence/private.json'):
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(rel)
            original=Path.iterdir
            def guarded(path):
                if any(x in {'.venv-mcp','evidence'} for x in path.relative_to(root).parts): raise AssertionError('excluded tree visited')
                return original(path)
            with patch.object(build_release,'ROOT',root),patch.object(Path,'rglob',side_effect=AssertionError('global traversal')),patch.object(Path,'iterdir',guarded):
                self.assertEqual([name for name,_ in build_release.source_files()],['README.md','rdc_operator/A.py','rdc_operator/b.py','site/.nojekyll'])
    def test_source_link_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'private').mkdir();(root/'private/x.py').write_text('fixture')
            try:(root/'site').symlink_to(root/'private',target_is_directory=True)
            except OSError:self.skipTest('symlink unavailable')
            with patch.object(build_release,'ROOT',root):
                with self.assertRaises(ValueError):list(build_release.source_files())
