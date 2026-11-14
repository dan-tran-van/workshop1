"""Regression checks for traceability, diagnostic evidence, and CI exit status."""
from copy import deepcopy
import html
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import report_results as report
from tests.report_results import counts, parse_results, write_reports, render_summary, failure_fields


class TestReporting(unittest.TestCase):
    def setUp(self):
        self.manifest = report.load_manifest()
        self.method = self.manifest[0]['methods'][0]

    def row(self, method=None, status='passed', details=None):
        return dict(id=method or self.method, case=None, priority=None,
                    status=status, details=details or [])

    def fixture(self, error=None, skip=False, subtests=False):
        class Fixture(unittest.TestCase):
            def test_example(self):
                if error:
                    raise error
                if subtests:
                    for actual in (201, 202):
                        with self.subTest(actual=actual):
                            self.assertEqual(actual, 200)
        if skip:
            Fixture.test_example = unittest.skip('reason')(Fixture.test_example)
        stream = io.StringIO()
        unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixture))
        return stream.getvalue()

    def test_all_pass_compact_and_four_suites(self):
        rows = [self.row(m) for c in self.manifest for m in c['methods']]
        summary = report.render_summary(rows)
        self.assertIn('| Total | 17/17 | 8/8 |', summary)
        for suite in report.SUITES:
            self.assertIn(suite, summary)
        self.assertNotIn('Failures', summary)
        self.assertNotIn(self.method, summary)

    def test_many_to_many_and_missing_execution(self):
        manifest = deepcopy(self.manifest)
        manifest[0]['methods'].append('test_api.Extra.test_extra')
        manifest[1]['methods'] = [self.method]
        cases = report.acceptance_cases([self.row()], manifest)
        self.assertEqual(cases[0]['status'], 'not_executed')
        self.assertEqual(cases[1]['status'], 'passed')
        for status in ('failed', 'error', 'skipped'):
            with self.subTest(status=status):
                self.assertEqual(report.acceptance_cases([self.row(status=status)], manifest)[1]['status'], status)
        manifest[0]['methods'] = []
        self.assertEqual(report.acceptance_cases([], manifest)[0]['status'], 'not_executed')

    def test_failure_order_grouping_and_multiple_ids_once(self):
        manifest = deepcopy(self.manifest)
        manifest[3]['methods'].append(self.method)
        rows = [self.row('extra.test_x', 'failed'), self.row(manifest[3]['methods'][0], 'error'), self.row(status='failed')]
        summary = html.unescape(report.render_summary(rows, manifest))
        self.assertLess(summary.index('P0 Acceptance Failures'), summary.index('P1 Acceptance Failures'))
        self.assertLess(summary.index('P1 Acceptance Failures'), summary.index('Supplemental Test Failures'))
        self.assertEqual(summary.count('#### '+self.method), 1)
        self.assertIn('BE-01', summary)
        self.assertIn('BE-04', summary)
        self.assertIn('### Restaurant API', summary)

    def test_subtests_unique_parent_and_values_source(self):
        records = report.parse_results(self.fixture(subtests=True))
        self.assertEqual(report.counts(records)['failed'], 1)
        self.assertEqual(len(records[0]['details']), 2)
        summary = html.unescape(report.render_summary(records))
        self.assertEqual(summary.count('#### '), 1)
        for value in ('actual=201', 'actual=202', '**Expected:** 200', '**Actual:** 201', 'test_reporting.py:', 'AssertionError'):
            self.assertIn(value, summary)

    def test_assertion_vs_exception_and_skip(self):
        for error, status in ((AssertionError('bad'), 'failed'), (RuntimeError('bad'), 'error'), (None, 'passed')):
            self.assertEqual(report.parse_results(self.fixture(error))[0]['status'], status)
        skipped = report.parse_results(self.fixture(skip=True))
        self.assertEqual(skipped[0]['status'], 'skipped')
        rows = report.parse_results(self.fixture()) + report.parse_results(self.fixture(RuntimeError('bad'))) + skipped
        # Use distinct names to represent three methods.
        for i, r in enumerate(rows):
            r['id'] += str(i)
        self.assertEqual(report.counts(rows), dict(total=3, passed=1, failed=0, error=1, skipped=1, not_executed=0))
        self.assertNotIn('#### '+skipped[0]['id'], report.render_summary(rows))

    def test_unknown_duplicate_and_invalid_manifest(self):
        for kind in ('unknown', 'duplicate', 'method', 'suite', 'missing'):
            cases = deepcopy(self.manifest)
            if kind == 'unknown': cases[0]['case'] = 'BE-99'
            if kind == 'duplicate': cases.append(cases[0])
            if kind == 'method': cases[0]['methods'] *= 2
            if kind == 'suite': cases[0]['suite'] = 'unknown'
            if kind == 'missing': cases.pop()
            with self.subTest(kind=kind), TemporaryDirectory() as folder:
                path = Path(folder)/'manifest.json'
                path.write_text(json.dumps(cases))
                with self.assertRaises(ValueError): report.load_manifest(path)

    def test_zero_incomplete_and_inconsistent_logs(self):
        valid = self.fixture(subtests=True)
        for log in ('Ran 0 tests in 0.001s\nOK\n', '', valid.replace('failures=2', 'failures=1'), valid.replace('Ran 1 test', 'Ran 2 tests'), valid+'trailing', valid.replace('FAILED (failures=2)', 'OK')):
            with self.subTest(log=log), self.assertRaises(ValueError): report.parse_results(log)
        self.assertIn('No test methods executed', report.render_summary([]))
        self.assertNotIn('All tests passed', report.render_summary([]))

    def test_markdown_escaping_and_unavailable_values(self):
        summary = report.render_summary(report.parse_results(self.fixture(RuntimeError('<script> | `x`\n# injected'))))
        self.assertNotIn('<script>', summary)
        self.assertNotIn('\n# injected', summary)
        self.assertIn('<script> | `x`', html.unescape(summary))
        fields = report.failure_fields('ERROR: test_x (test.Example.test_x)\nRuntimeError: bad')
        self.assertEqual(fields['Expected'], 'Not available in unittest output')
        self.assertEqual(fields['Actual'], 'Not available in unittest output')

    def test_cli_exit_and_artifacts(self):
        for log, status in ((self.fixture(), 'passed'),
                            (self.fixture(subtests=True), 'failed'),
                            (self.fixture(RuntimeError('bad')), 'error'),
                            (self.fixture(skip=True), 'skipped')):
            with self.subTest(status=status), TemporaryDirectory() as folder:
                path = Path(folder)
                (path/'log').write_text(log)
                result = subprocess.run([sys.executable, report.__file__, str(path/'log'), '--output', str(path/'reports')], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for artifact in ('results.json', 'junit.xml', 'summary.md'):
                    self.assertTrue((path/'reports'/artifact).is_file())
                results = json.loads((path/'reports'/'results.json').read_text())
                self.assertEqual(results['tests'][0]['status'], status)
                self.assertEqual(results['summary']['All'][status], 1)
                self.assertEqual(results['summary']['All']['total'], 1)
                root = ET.parse(path/'reports'/'junit.xml').getroot()
                self.assertEqual(root.attrib['tests'], '1')
                tag = {'failed': 'failure', 'error': 'error', 'skipped': 'skipped'}.get(status)
                if tag:
                    self.assertIsNotNone(root.find('testcase/'+tag))
                summary = (path/'reports'/'summary.md').read_text(encoding='utf-8')
                self.assertEqual(summary.count('#### '), int(status in ('failed', 'error')))

    def test_cli_rejects_invalid_missing_and_empty_logs(self):
        for log in ('invalid', '', 'Ran 0 tests in 0.001s\nOK\n',
                    self.fixture(subtests=True).replace('failures=2', 'failures=1'), None):
            with self.subTest(log=log), TemporaryDirectory() as folder:
                path = Path(folder)
                if log is not None:
                    (path/'log').write_text(log)
                result = subprocess.run([sys.executable, report.__file__, str(path/'log'), '--output', str(path/'reports')], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr)
                self.assertFalse((path/'reports'/'summary.md').exists())

    def test_cli_output_failure_is_nonzero(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'log').write_text(self.fixture())
            (path/'reports').write_text('A file cannot be an output directory')
            result = subprocess.run([sys.executable, report.__file__, str(path/'log'), '--output', str(path/'reports')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr)

    def test_unexpected_reporter_exception_is_not_suppressed(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/'log'
            path.write_text(self.fixture())
            with patch.object(sys, 'argv', [report.__file__, str(path)]), \
                    patch.object(report, 'write_reports', side_effect=RuntimeError('reporter bug')):
                with self.assertRaisesRegex(RuntimeError, 'reporter bug'):
                    report.main()

    def test_manifest_methods_exist_and_counts(self):
        import ast
        tree = ast.parse(Path(__file__).with_name('test_api.py').read_text())
        methods = {'test_api.'+cls.name+'.'+m.name for cls in tree.body if isinstance(cls, ast.ClassDef) for m in cls.body if isinstance(m, ast.FunctionDef)}
        self.assertEqual(len(self.manifest), 25)
        self.assertEqual(sum(c['priority'] == 'P0' for c in self.manifest), 17)
        for c in self.manifest:
            self.assertTrue(set(c['methods']) <= methods)


class TestParserRegressions(unittest.TestCase):

    def subtest_failure_log(self, blocks: int = 2, footer: str = "FAILED (failures=2)") -> str:
        progress = """test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) ...
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=1) ... FAIL
  test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a=2) ... FAIL
"""
        details = "".join(f"{'=' * 70}\nFAIL: test_be_01_p0_health (test_api.Acceptance.test_be_01_p0_health) (a={index})\nAssertionError: failure {index}\n"
                          for index in range(1, blocks + 1))
        return f"{progress}{details}Ran 1 test in 0.001s\n{footer}\n"

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
