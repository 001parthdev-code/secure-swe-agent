import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.verification import VerificationError, verify_calculator_fixture

TEST = """import unittest
from calculator import subtract
class CalculatorTest(unittest.TestCase):
    def test_subtract(self):
        self.assertEqual(subtract(8, 3), 5)
"""

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.fixture = self.workspace / 'calculator'
        self.fixture.mkdir()
        (self.fixture / 'test_calculator.py').write_text(TEST)

    def test_failing_then_passing(self):
        source = self.fixture / 'calculator.py'
        source.write_text('def subtract(a, b):\n    return a + b\n')
        self.assertEqual(verify_calculator_fixture(self.workspace)['status'], 'failed')
        source.write_text('def subtract(a, b):\n    return a - b\n')
        self.assertEqual(verify_calculator_fixture(self.workspace)['status'], 'passed')

    def test_missing_fixture_denied(self):
        with self.assertRaises(VerificationError):
            verify_calculator_fixture(self.workspace)

    def test_symlink_denied(self):
        (self.fixture / 'calculator.py').symlink_to(self.fixture / 'test_calculator.py')
        with self.assertRaises(VerificationError):
            verify_calculator_fixture(self.workspace)

if __name__ == '__main__':
    unittest.main()
