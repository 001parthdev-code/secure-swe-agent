import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.agent import Agent
from secure_swe_agent.catalog import load_catalog

class Model:
    def __init__(self, decisions): self.decisions = iter(decisions)
    def decide(self, messages): return next(self.decisions)

class Enforcer:
    def __init__(self): self.paths = []
    def read_file(self, path):
        self.paths.append(path)
        return {'status': 'success', 'output': 'safe source'}

class A2Tests(unittest.TestCase):
    def test_select_read_plan(self):
        e = Enforcer()
        a = Agent(Model([{'action':'select_files','paths':['src/main.rs']},
                         {'action':'read_file','path':'src/main.rs'},
                         {'action':'finish','summary':'Inspect main.rs'}]), e, ['src/main.rs'])
        result = a.run('Find entry point')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(e.paths, ['src/main.rs'])

    def test_selection_cannot_expand_authority(self):
        e = Enforcer()
        a = Agent(Model([{'action':'select_files','paths':['../secret']},
                         {'action':'read_file','path':'../secret'},
                         {'action':'finish','summary':'denied'}]), e, ['src/main.rs'])
        result = a.run('test')
        self.assertEqual(e.paths, [])
        self.assertEqual(result['trace'][0]['status'], 'invalid_selection')

    def test_manifest_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'catalog.json'
            path.write_text(json.dumps({'files':['../secret']}))
            with self.assertRaises(ValueError): load_catalog(path)

    def test_manifest_accepts_curated_paths(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'catalog.json'
            path.write_text(json.dumps({'files':['src/main.rs','Cargo.toml']}))
            self.assertEqual(load_catalog(path), ['src/main.rs','Cargo.toml'])

if __name__ == '__main__': unittest.main()
