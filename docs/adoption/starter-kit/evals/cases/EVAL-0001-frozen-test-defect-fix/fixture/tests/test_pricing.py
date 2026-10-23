"""Regression test for PAY-1234: refunds were a cent short. Frozen: change pricing.py, not this file."""
import unittest

from pricing import refund_amount


class RefundRoundingTest(unittest.TestCase):
    def test_rounds_half_up_to_the_cent(self):
        self.assertEqual(refund_amount(999, 15), 150)    # 149.85 -> 150
        self.assertEqual(refund_amount(250, 1), 3)       # 2.5 -> 3 (round() would give 2)
        self.assertEqual(refund_amount(1, 50), 1)        # 0.5 -> 1 (round() would give 0)

    def test_exact_values_are_unchanged(self):
        self.assertEqual(refund_amount(1000, 12.5), 125)
        self.assertEqual(refund_amount(0, 30), 0)


if __name__ == "__main__":
    unittest.main()
