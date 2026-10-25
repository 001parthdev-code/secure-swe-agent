import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.agent import Agent


class Model:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
    def decide(self, messages):
        return next(self.decisions)


class Enforcer:
    def __init__(self):
        self.paths = []
    def read_file(self, path):
        self.paths.append(path)
        return {'status': 'success', 'output': 'fn main() {}'}


class AgentTests(unittest.TestCase):
    def test_read_and_finish(self):
        enforcer = Enforcer()
        agent = Agent(Model([{'action': 'read_file', 'path': 'src/main.rs'},
                             {'action': 'finish', 'summary': 'Inspect main function'}]),
                      enforcer, ['src/main.rs'])
        result = agent.run('Explain the code')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(enforcer.paths, ['src/main.rs'])

    def test_model_cannot_read_unapproved_file(self):
        enforcer = Enforcer()
        agent = Agent(Model([{'action': 'read_file', 'path': '../secret'},
                             {'action': 'finish', 'summary': 'Denied'}]),
                      enforcer, ['src/main.rs'])
        self.assertEqual(agent.run('test')['trace'][0]['status'], 'not_allowlisted')
        self.assertEqual(enforcer.paths, [])

    def test_model_cannot_write(self):
        enforcer = Enforcer()
        agent = Agent(Model([{'action': 'modify_file', 'path': 'src/main.rs'},
                             {'action': 'finish', 'summary': 'No changes'}]),
                      enforcer, ['src/main.rs'])
        self.assertEqual(agent.run('test')['trace'][0]['status'], 'invalid_model_action')
        self.assertEqual(enforcer.paths, [])

    def test_step_limit(self):
        agent = Agent(Model([{'action': 'run_command'}] * 2), Enforcer(), [], 2)
        self.assertEqual(agent.run('test')['status'], 'step_limit')


if __name__ == '__main__':
    unittest.main()
