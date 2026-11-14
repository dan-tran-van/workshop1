"""Turn standard unittest verbose output into per-case CI artifacts.

Count a test with multiple failing subtests once. Incomplete logs are rejected
instead of implying that unexecuted cases passed. No application import occurs.
"""

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def parse_results(log: str) -> list[dict]:
    log = log.replace("\r\n", "\n")
    starts = re.findall(r"^test_\w+ \(([^)]+)\) \.\.\.([^\n]*)", log, re.MULTILINE)
    records = {}
    for test_id, _tail in starts:
        match = re.search(r"\.test_be_(\d+)_(p[01])_", test_id)
        records[test_id] = {
            "id": test_id,
            "case": f"BE-{match[1]}" if match else None,
            "priority": match[2].upper() if match else None,
            "status": "passed",
            "details": [],
        }
    skipped = re.findall(r"^[ \t]*test_\w+ \(([^)]+)\)[^\n]* \.\.\. skipped(?: .*)?$", log, re.MULTILINE)
    for test_id in skipped:
        if test_id not in records:
            raise ValueError(f"Skip has no matching test start: {test_id}")
        records[test_id]["status"] = "skipped"
    detail_counts = Counter({"failures": 0, "errors": 0, "skipped": len(skipped)})
    for block in re.split(r"(?=^={20,}\n(?:FAIL|ERROR):)", log, flags=re.MULTILINE):
        match = re.search(r"^(FAIL|ERROR): test_\w+ \(([^)]+)\)", block, re.MULTILINE)
        if match:
            kind, test_id = match.groups()
            detail_counts["failures" if kind == "FAIL" else "errors"] += 1
            if test_id not in records:
                raise ValueError(f"Failure has no matching test start: {test_id}")
            record = records[test_id]
            if record["status"] != "error":
                record["status"] = "error" if kind == "ERROR" else "failed"
            record["details"].append(block.strip())
    ran = re.search(r"^Ran (\d+) tests? in ", log, re.MULTILINE)
    if not ran or int(ran[1]) != len(records) or not records:
        raise ValueError("Incomplete unittest log: discovered starts do not match the final run count")
    outcomes = list(re.finditer(r"^(OK|FAILED)(?: \(([^)\n]*)\))?[ \t]*$", log, re.MULTILINE))
    if len(outcomes) != 1 or log[outcomes[0].end():].strip():
        raise ValueError("Incomplete unittest log: expected one final outcome at the end")
    outcome = outcomes[0]
    footer_counts = {}
    for item in outcome[2].split(", ") if outcome[2] else ():
        counter = re.fullmatch(r"(failures|errors|skipped)=(\d+)", item)
        if not counter or counter[1] in footer_counts:
            raise ValueError(f"Invalid or unsupported unittest footer counter: {item}")
        footer_counts[counter[1]] = int(counter[2])
    for name, actual in detail_counts.items():
        expected = footer_counts.get(name, 0)
        if expected != actual:
            raise ValueError(f"Unittest footer {name}={expected} does not match parsed {name}={actual}")
    has_failures = any(row["status"] in {"failed", "error"} for row in records.values())
    if (outcome[1] == "FAILED") != has_failures:
        raise ValueError("Unittest outcome does not match parsed failure details")
    return list(records.values())


def counts(records: list[dict]) -> dict:
    outcomes = Counter(row["status"] for row in records)
    return {"total": len(records), **{key: outcomes[key] for key in ("passed", "failed", "error", "skipped")}}


def acceptance_cases(records: list[dict]) -> list[dict]:
    """A case passes only when all its scenario methods pass."""
    severity = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}
    cases = {}
    for row in records:
        if row["case"]:
            case = cases.setdefault(row["case"], {"case": row["case"], "priority": row["priority"], "status": "passed"})
            if severity[row["status"]] > severity[case["status"]]:
                case["status"] = row["status"]
    return list(cases.values())


def summary_text(value: str) -> str:
    """Encode all punctuation and line breaks as inert HTML text."""
    return "<br>".join("".join(char if char.isalnum() or char == " " else f"&#{ord(char)};"
                              for char in line) for line in str(value).splitlines())


def failure_fields(detail: str) -> dict:
    """Extract evidence without evaluating test code or guessing operand order."""
    body = re.split(r"\n-{20,}\nRan \d+ tests? in |\nRan \d+ tests? in ", detail)[0]
    header = re.search(r"^(?:FAIL|ERROR): test_\w+ \([^)]+\)([^\n]*)", body, re.MULTILINE)
    frames = re.findall(r'^  File "([^"]+)", line (\d+)[^\n]*\n(?:    ([^\n]+))?', body, re.MULTILINE)
    # The test frame identifies the assertion call; the last frame may be library code.
    frame = next((item for item in reversed(frames) if Path(item[0]).name.startswith("test")), frames[-1] if frames else None)
    diagnostic = body[header.end():].lstrip("\n") if header else body
    exception = re.search(r"^[\w.]+(?:Error|Exception|Interrupt|Exit|Failure)(?::|$)[^\n]*(?:\n[\s\S]*)?", diagnostic, re.MULTILINE)
    if exception is None:
        exception = re.search(r"^[\w.]+: .*(?:\n[\s\S]*)?", diagnostic, re.MULTILINE)
    message = exception[0].strip() if exception else diagnostic.strip()
    expected = actual = "Not available in unittest output"
    comparison = re.match(r"AssertionError: (.+?) != (.+?)(?: : .*|\n|$)", message)
    if frame and frame[2]:
        try:
            call = ast.parse(frame[2].strip()).body[0].value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                if call.func.attr in {"assertEqual", "assertEquals"} and len(call.args) >= 2:
                    # unittest has no expected/actual convention. Only label the
                    # operands when the source gives one literal reference value.
                    left, right = call.args[:2]
                    if isinstance(right, ast.Constant) and not isinstance(left, ast.Constant):
                        expected = ast.unparse(right)
                        if comparison:
                            actual = comparison[1]
                    elif isinstance(left, ast.Constant) and not isinstance(right, ast.Constant):
                        expected = ast.unparse(left)
                        if comparison:
                            actual = comparison[2]
                elif call.func.attr in {"assertTrue", "assertFalse"}:
                    expected = "True" if call.func.attr == "assertTrue" else "False"
                    match = re.match(r"AssertionError: (.+?) is not (?:true|false)", message)
                    if match:
                        actual = match[1]
        except (SyntaxError, AttributeError, IndexError):
            pass
    return {"Subtest parameters": header[1].strip() if header and header[1].strip() else "Not applicable",
            "Expected": expected, "Actual": actual, "Message": message,
            "Source": f"{frame[0]}:{frame[1]}" if frame else "Not available in unittest output"}


def render_summary(records: list[dict]) -> str:
    values = counts(records)
    lines = ["# Backend automation results", "",
             "| Total test methods | Passed methods | Failed methods | Errors | Skipped |",
             "| ---: | ---: | ---: | ---: | ---: |",
             f"| {values['total']} | {values['passed']} | {values['failed']} | {values['error']} | {values['skipped']} |", ""]
    failures = [row for row in records if row["status"] in {"failed", "error"}]
    if not failures:
        lines += ["All tests passed." if not values["skipped"] else "No test failures; some tests were skipped.", ""]
    for priority, title in (("P0", "P0 acceptance"), ("P1", "P1 acceptance"), (None, "Supplemental tests")):
        grouped = {}
        for row in failures:
            if (row["priority"] if row["case"] else None) == priority:
                grouped.setdefault(row["case"], []).append(row)
        if not grouped:
            continue
        lines += [f"## {title}", ""]
        for case_id, methods in grouped.items():
            if case_id:
                lines += [f"### {summary_text(case_id)} ({priority})", ""]
            for row in methods:
                lines += [f"#### {summary_text(row['id'])}", "", f"Status: {row['status']}", ""]
                for index, detail in enumerate(row["details"], 1):
                    lines += [f"Diagnostic {index}:", ""]
                    for label, value in failure_fields(detail).items():
                        lines.append(f"- **{label}:** {summary_text(value)}")
                    lines.append("")
    return "\n".join(lines)


def write_reports(records: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    cases = acceptance_cases(records)
    groups = {"P0": [row for row in cases if row["priority"] == "P0"],
              "P1": [row for row in cases if row["priority"] == "P1"],
              "Supplemental": [row for row in records if row["case"] is None]}
    summary = {name: counts(rows) for name, rows in {**groups, "All": records}.items()}
    (output / "results.json").write_text(json.dumps({"summary": summary, "tests": records}, indent=2), encoding="utf-8")
    root = ET.Element("testsuite", name="Backend automation", tests=str(len(records)),
                      failures=str(summary["All"]["failed"]), errors=str(summary["All"]["error"]),
                      skipped=str(summary["All"]["skipped"]))
    for row in records:
        classname, name = row["id"].rsplit(".", 1)
        case = ET.SubElement(root, "testcase", classname=classname, name=name)
        if row["status"] in {"failed", "error", "skipped"}:
            tag = {"failed": "failure", "error": "error", "skipped": "skipped"}[row["status"]]
            ET.SubElement(case, tag).text = "\n\n".join(row["details"])
    ET.indent(root)
    ET.ElementTree(root).write(output / "junit.xml", encoding="utf-8", xml_declaration=True)
    (output / "summary.md").write_text(render_summary(records), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    write_reports(parse_results(args.log.read_text(encoding="utf-8-sig")), args.output)


if __name__ == "__main__":
    main()
