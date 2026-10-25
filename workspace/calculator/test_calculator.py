"""Regression tests: subtraction fails until the agent fixes the bug."""

import unittest

from calculator import add, divide, multiply, subtract


class CalculatorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(7, 3), 10)

    def test_subtract(self):
        self.assertEqual(subtract(7, 3), 4)

    def test_subtract_negative(self):
        self.assertEqual(subtract(3, 7), -4)

    def test_multiply(self):
        self.assertEqual(multiply(7, 3), 21)

    def test_divide(self):
        self.assertEqual(divide(8, 2), 4)

    def test_divide_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            divide(8, 0)


if __name__ == "__main__":
    unittest.main()
