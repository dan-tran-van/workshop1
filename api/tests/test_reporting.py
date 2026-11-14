"""Verify CI reporting does not hide subtest failures or incomplete runs."""

import json
import html
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.report_results import counts, parse_results, write_reports, render_summary, failure_fields


class TestReporting(unittest.TestCase):
    def subtest_failure_log(self, blocks: int = 2, footer: str = "FAILED (failures=2)") -> str:
        progress = """test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) ...
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=1) ... FAIL
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=2) ... FAIL
"""
        details = "".join(f"{'=' * 70}\nFAIL: test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a={index})\nAssertionError: failure {index}\n"
                          for index in range(1, blocks + 1))
        return f"{progress}{details}Ran 1 test in 0.001s\n{footer}\n"

    def test_multiple_subtest_failures_count_as_one_failed_case(self) -> None:
        records = parse_results(self.subtest_failure_log())
        self.assertEqual(counts(records)["failed"], 1)
        self.assertEqual(records[0]["case"], "BE-01")
        self.assertEqual(records[0]["priority"], "P0")
        self.assertEqual(len(records[0]["details"]), 2)

    def test_missing_failure_blocks_are_rejected(self) -> None:
        for blocks in (0, 1):
            with self.subTest(blocks=blocks), self.assertRaisesRegex(ValueError, f"footer failures=2.*parsed failures={blocks}"):
                parse_results(self.subtest_failure_log(blocks=blocks))

    def test_inconsistent_failure_footer_counts_are_rejected(self) -> None:
        for footer in ("FAILED (failures=1)", "FAILED (failures=3)"):
            with self.subTest(footer=footer), self.assertRaisesRegex(ValueError, "footer failures=.*parsed failures=2"):
                parse_results(self.subtest_failure_log(footer=footer))

    def test_inconsistent_error_footer_counts_are_rejected(self) -> None:
        log = self.subtest_failure_log(footer="FAILED (errors=3)").replace("FAIL:", "ERROR:").replace(" ... FAIL\n", " ... ERROR\n")
        with self.assertRaisesRegex(ValueError, "footer errors=3.*parsed errors=2"):
            parse_results(log)

    def test_inconsistent_skipped_footer_counts_are_rejected(self) -> None:
        for footer in ("OK", "OK (skipped=0)", "OK (skipped=2)"):
            log = f"test_example (test_api.Example.test_example) ... skipped 'reason'\nRan 1 test in 0.001s\n{footer}\n"
            with self.subTest(footer=footer), self.assertRaisesRegex(ValueError, "footer skipped=.*parsed skipped=1"):
                parse_results(log)

    def test_mixed_failure_and_error_subtests_validate_both_counts(self) -> None:
        log = self.subtest_failure_log(footer="FAILED (failures=1, errors=1)").replace("FAIL:", "ERROR:", 1).replace(" ... FAIL\n", " ... ERROR\n", 1)
        records = parse_results(log)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "error")
        self.assertEqual(len(records[0]["details"]), 2)

    def test_skipped_subtests_are_not_counted_as_passed(self) -> None:
        log = """test_example (test_api.Example.test_example) ...
  test_example (test_api.Example.test_example) (a=1) ... skipped 'first'
  test_example (test_api.Example.test_example) (a=2) ... skipped 'second'
Ran 1 test in 0.001s
OK (skipped=2)
"""
        records = parse_results(log)
        self.assertEqual(counts(records)["passed"], 0)
        self.assertEqual(counts(records)["skipped"], 1)

    def test_be_25_scenarios_are_one_case_without_changing_artifact_schema(self) -> None:
        for statuses, case_status in ((["passed"] * 4, "passed"),
                                      (["passed", "failed", "failed", "skipped"], "failed"),
                                      (["passed", "skipped", "passed", "passed"], "skipped"),
                                      (["failed", "error", "skipped", "passed"], "error")):
            with self.subTest(statuses=statuses), TemporaryDirectory() as folder:
                records = [{"id": f"test_api.Acceptance.test_be_25_p1_scenario_{index}", "case": "BE-25",
                            "priority": "P1", "status": status, "details": []}
                           for index, status in enumerate(statuses)]
                write_reports(records, Path(folder))
                report = json.loads((Path(folder) / "results.json").read_text(encoding="utf-8"))
                self.assertEqual(set(report), {"summary", "tests"})
                self.assertEqual(set(report["summary"]), {"P0", "P1", "Supplemental", "All"})
                self.assertEqual(report["summary"]["P1"]["total"], 1)
                self.assertEqual(report["summary"]["P1"][case_status], 1)
                self.assertEqual(report["summary"]["All"]["total"], 4)
                self.assertEqual(report["tests"], records)
                expected_groups = int(case_status in {"failed", "error"})
                self.assertEqual(html.unescape((Path(folder) / "summary.md").read_text(encoding="utf-8")).count("### BE-25 (P1)"), expected_groups)
                root = ET.parse(Path(folder) / "junit.xml").getroot()
                self.assertEqual(root.attrib["tests"], "4")
                self.assertEqual(len(root.findall("testcase")), 4)
                self.assertEqual(root.attrib["failures"], str(statuses.count("failed")))
                self.assertEqual(root.attrib["errors"], str(statuses.count("error")))
                self.assertEqual(root.attrib["skipped"], str(statuses.count("skipped")))

    def test_incomplete_run_is_rejected(self) -> None:
        for log in ("test_example (test_api.Example.test_example) ... ",
                    "test_example (test_api.Example.test_example) ... FAIL\nRan 1 test in 0.001s\nFAILED (failures=1)\n",
                    "test_example (test_api.Example.test_example) ... ok\nRan 1 test in 0.001s\nOK\ntest_example (test_api.Example.test_example) ... "):
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

    def run_fixture(self, fixture: type) -> tuple[str, list[dict]]:
        stream = io.StringIO()
        unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(fixture))
        log = stream.getvalue()
        return log, parse_results(log)

    def test_one_failure_has_values_message_and_source(self) -> None:
        class Fixture(unittest.TestCase):
            def test_be_01_p0_health(self):
                actual = 201
                self.assertEqual(actual, 200)

        log, records = self.run_fixture(Fixture)
        summary = html.unescape(render_summary(records))
        for text in ("P0 acceptance", "BE-01 (P0)", records[0]["id"], "**Expected:** 200", "**Actual:** 201",
                     "AssertionError: 201 != 200", "test_reporting.py:", "| 1 | 0 | 1 | 0 | 0 |"):
            self.assertIn(text, summary)
        self.assertNotIn("Ran 1 test", summary)
        with TemporaryDirectory() as folder:
            write_reports(records, Path(folder))
            report = json.loads((Path(folder) / "results.json").read_text())
            self.assertEqual(report["tests"], records)
            self.assertIn("AssertionError", ET.parse(Path(folder) / "junit.xml").findtext("testcase/failure"))

    def test_failed_subtests_appear_under_one_parent(self) -> None:
        records = parse_results(self.subtest_failure_log())
        summary = html.unescape(render_summary(records))
        self.assertEqual(summary.count("#### " + records[0]["id"]), 1)
        for parameter in ("(a=1)", "(a=2)"):
            self.assertIn(parameter, summary)
        self.assertEqual(summary.count("**Message:**"), 2)
        self.assertIn("| 1 | 0 | 1 | 0 | 0 |", summary)

    def test_case_grouping_priority_order_and_only_failures(self) -> None:
        class Fixture(unittest.TestCase):
            def test_be_25_p1_first(self):
                self.fail("first")

            def test_be_25_p1_second(self):
                self.fail("second")

            def test_be_01_p0_health(self):
                self.fail("health")

            def test_supplemental(self):
                self.fail("extra")

            def test_be_02_p0_pass(self):
                pass

        _, records = self.run_fixture(Fixture)
        summary = html.unescape(render_summary(list(reversed(records))))
        self.assertEqual(summary.count("### BE-25 (P1)"), 1)
        self.assertLess(summary.index("P0 acceptance"), summary.index("P1 acceptance"))
        self.assertLess(summary.index("P1 acceptance"), summary.index("Supplemental tests"))
        for row in records:
            self.assertEqual(summary.count("#### " + row["id"]), int(row["status"] == "failed"))
        self.assertNotIn("BE-02", summary)

    def test_error_and_skip_summary_retains_full_diagnostics(self) -> None:
        class Fixture(unittest.TestCase):
            def test_error(self):
                raise RuntimeError("bad | `value`\n</pre><script>alert(1)</script>\n# injected\n```\n&entity;")

            @unittest.skip("skip reason")
            def test_skip(self):
                pass

        log, records = self.run_fixture(Fixture)
        summary = render_summary(records)
        self.assertIn("| 2 | 0 | 0 | 1 | 1 |", summary)
        self.assertNotIn("test_skip", summary)
        for injection in ("<script>", "</pre>", "```", "\n# injected", "&entity;", "bad |"):
            self.assertNotIn(injection, summary)
        self.assertIn("<br>", summary)
        self.assertIn("RuntimeError: bad | `value`", html.unescape(summary))
        with TemporaryDirectory() as folder:
            write_reports(records, Path(folder))
            self.assertIn("<script>", json.loads((Path(folder) / "results.json").read_text())["tests"][0]["details"][0])
            self.assertIn("<script>", ET.parse(Path(folder) / "junit.xml").findtext("testcase/error"))

    def test_fully_passing_summary_is_compact(self) -> None:
        class Fixture(unittest.TestCase):
            def test_be_01_p0_pass(self):
                pass

        _, records = self.run_fixture(Fixture)
        summary = render_summary(records)
        self.assertIn("| 1 | 1 | 0 | 0 | 0 |", summary)
        self.assertIn("All tests passed", summary)
        self.assertNotIn("## ", summary)
        self.assertNotIn("test_be_01", summary)

    def test_malformed_logs_are_rejected(self) -> None:
        valid = self.subtest_failure_log()
        for log in (valid.replace("Ran 1 test", "Ran 2 tests"), valid.replace("FAILED (failures=2)", "OK"),
                    valid + "trailing output", valid.replace("failures=2", "failures=2, failures=2")):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_results(log)

    def test_unrecoverable_values_are_explicit(self) -> None:
        fields = failure_fields("ERROR: test_x (tests.Example.test_x)\nRuntimeError: unavailable")
        self.assertEqual(fields["Expected"], "Not available in unittest output")
        self.assertEqual(fields["Actual"], "Not available in unittest output")
        self.assertEqual(fields["Message"], "RuntimeError: unavailable")
