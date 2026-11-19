"""Small deterministic regression suite for the offline demo engine."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from password_cracker_core import (
    ALPHABET, PasswordInfo, estimate_keyspace, run_attack,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wordlist = Path(self.tmp.name) / "words.txt"
        self.messages = []

    def run_test(self, values, text="", *, path=None, confirm=None, stop=None):
        self.wordlist.write_text(text, encoding="utf-8")
        cases = [PasswordInfo(value) for value in values]
        run_attack(
            cases, path or self.wordlist, log=self.messages.append,
            confirm=confirm or (lambda *_: False),
            should_stop=stop or (lambda: False),
        )
        return cases

    def test_dictionary_duplicate_entries_are_each_reported(self):
        cases = self.run_test(["ab", "ab"], "nope\nab\n")
        self.assertTrue(all(p.cracked for p in cases))
        self.assertEqual([p.attempts for p in cases], [2, 2])
        self.assertIn("Total attempts across all passwords: 4", self.messages)

    def test_mixed_dictionary_and_brute_force_count(self):
        cases = self.run_test(["ab", "b"], "ab\n")
        self.assertEqual([p.attempts for p in cases], [1, 3])
        self.assertTrue(all(p.cracked for p in cases))
        self.assertTrue(any("found by brute force" in m for m in self.messages))
        self.assertTrue(any("Total attempts across all passwords: 4" in m for m in self.messages))

    def test_brute_force_duplicate_targets_share_one_search(self):
        import itertools
        original_product = itertools.product
        with patch("password_cracker_core.itertools.product", wraps=original_product) as guesses:
            cases = self.run_test(["bb", "bb"], "unrelated\n")
        self.assertTrue(all(p.cracked for p in cases))
        self.assertEqual(cases[0].attempts, cases[1].attempts)
        self.assertEqual(guesses.call_count, 2)  # lengths 1, 2; not a second search

    def test_duplicate_large_search_confirms_once(self):
        requested = []
        cases = self.run_test(
            ["aaaaa", "aaaaa"], "unrelated\n",
            confirm=lambda pw, n: requested.append(n) or False,
        )
        self.assertEqual(len(requested), 1)
        self.assertTrue(all(p.skipped for p in cases))

    def test_blank_dictionary_lines_not_counted(self):
        cases = self.run_test(["a"], "\n\n\na\n")
        self.assertEqual(cases[0].attempts, 1)

    def test_single_password_gets_total_line(self):
        self.run_test(["a"], "a\n")
        self.assertIn("Total attempts across all passwords: 1", self.messages)

    def test_missing_dictionary_skips_to_brute_force(self):
        missing = Path(self.tmp.name) / "missing.txt"
        cases = self.run_test(["a"], path=missing)
        self.assertEqual(cases[0].attempts, 1)
        self.assertTrue(cases[0].cracked)

    def test_directory_wordlist_skips_to_brute_force(self):
        cases = self.run_test(["a"], path=Path(self.tmp.name))
        self.assertTrue(cases[0].cracked)
        self.assertTrue(any("must be an existing file" in m for m in self.messages))

    def test_unreadable_wordlist_does_not_crash(self):
        self.wordlist.write_text("a\n")
        cases = [PasswordInfo("a")]
        with patch.object(Path, "open", side_effect=OSError("test read error")):
            run_attack(cases, self.wordlist, log=self.messages.append)
        self.assertTrue(cases[0].cracked)
        self.assertTrue(any("Unable to read dictionary" in m for m in self.messages))

    def test_dictionary_time_is_preserved_after_brute_force(self):
        cases = self.run_test(["b"], "not-b\n")
        self.assertTrue(cases[0].cracked)
        self.assertGreater(cases[0].time_taken, 0)

    def test_brute_force_limit_is_reported(self):
        cases = self.run_test(["aaaaaaaaa"], "z\n")
        self.assertTrue(cases[0].too_long)
        self.assertFalse(cases[0].cracked)
        self.assertEqual(cases[0].attempts, 1)

    def test_big_keyspace_requires_confirmation(self):
        requested = []
        cases = self.run_test(["aaaaa"], "z\n", confirm=lambda pw, n: requested.append(n) or False)
        self.assertTrue(cases[0].skipped)
        self.assertEqual(cases[0].attempts, 1)
        self.assertEqual(requested, [estimate_keyspace(5)])

    def test_keyspace_includes_shorter_attempt_lengths(self):
        self.assertEqual(len(ALPHABET), 68)
        self.assertEqual(estimate_keyspace(2), 68 + 68**2)

    def test_utf8_bom_first_line(self):
        self.wordlist.write_bytes(b"\xef\xbb\xbfa\n")
        cases = [PasswordInfo("a")]
        run_attack(cases, self.wordlist, log=self.messages.append)
        self.assertTrue(cases[0].cracked)
        self.assertEqual(cases[0].attempts, 1)


if __name__ == "__main__":
    unittest.main()
