import unittest
from scripts.utils.naming import parse_orig_filename, build_friendly_filename, get_clock_emoji


class TestNaming(unittest.TestCase):
    def test_parse_orig_filename_valid(self):
        year, mon = parse_orig_filename("2026_06.pdf")
        self.assertEqual(year, 2026)
        self.assertEqual(mon, 6)

    def test_parse_orig_filename_invalid(self):
        with self.assertRaises(ValueError):
            parse_orig_filename("invalid.pdf")
        with self.assertRaises(ValueError):
            parse_orig_filename("2026_13.pdf")

    def test_build_friendly_filename(self):
        name = build_friendly_filename("2026_06.pdf")
        self.assertIn("किशोर", name)
        self.assertIn("जून", name)
        self.assertIn("June 2026", name)

    def test_clock_emoji(self):
        self.assertEqual(get_clock_emoji(0), "🕛")
        self.assertEqual(get_clock_emoji(12), "🕛")
        self.assertEqual(get_clock_emoji(1), "🕐")


if __name__ == "__main__":
    unittest.main()
