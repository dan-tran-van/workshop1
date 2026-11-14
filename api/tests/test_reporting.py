"""Verify CI reporting does not hide subtest failures or incomplete runs."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.report_results import counts, parse_results, write_reports


class TestReporting(unittest.TestCase):
    def test_multiple_subtest_failures_count_as_one_failed_case(self) -> None:
        log = """test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) ...
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=1) ... FAIL
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=2) ... FAIL
======================================================================
FAIL: test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=1)
AssertionError: first failure
======================================================================
FAIL: test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=2)
AssertionError: second failure
Ran 1 test in 0.001s
FAILED (failures=2)
"""
        records = parse_results(log)
        self.assertEqual(counts(records)["failed"], 1)
        self.assertEqual(records[0]["case"], "BE-01")
        self.assertEqual(records[0]["priority"], "P0")
        self.assertEqual(len(records[0]["details"]), 2)

    def test_incomplete_run_is_rejected(self) -> None:
        for log in ("test_example (test_api.Example.test_example) ... ",
                    "test_example (test_api.Example.test_example) ... FAIL\nRan 1 test in 0.001s\nFAILED (failures=1)\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_results(log)

    def test_skipped_test_is_not_counted_as_passed(self) -> None:
        records = parse_results("test_example (test_api.Example.test_example) ... skipped 'reason'\nRan 1 test in 0.001s\nOK (skipped=1)\n")
        self.assertEqual(counts(records)["passed"], 0)
        self.assertEqual(counts(records)["skipped"], 1)

    def test_artifacts_preserve_error_status(self) -> None:
        records = parse_results("test_example (test_api.Example.test_example) ... ERROR\n======================================================================\nERROR: test_example (test_api.Example.test_example)\nRuntimeError: example\nRan 1 test in 0.001s\nFAILED (errors=1)\n")
        with TemporaryDirectory() as folder:
            write_reports(records, Path(folder))
            root = ET.parse(Path(folder) / "junit.xml").getroot()
            self.assertEqual(root.attrib["errors"], "1")
            self.assertIsNotNone(root.find("testcase/error"))
            self.assertTrue((Path(folder) / "results.json").is_file())
            self.assertTrue((Path(folder) / "summary.md").is_file())
