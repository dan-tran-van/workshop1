import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const reportPath = resolve(process.argv[2] ?? "reports/playwright-results.json");
const summaryPath = resolve(process.argv[3] ?? "reports/summary.md");
const githubSummaryPath = process.env.GITHUB_STEP_SUMMARY;

async function publish(markdown) {
  await mkdir(dirname(summaryPath), { recursive: true });
  await writeFile(summaryPath, markdown, "utf8");
  if (githubSummaryPath) {
    await appendFile(githubSummaryPath, markdown, "utf8");
  } else {
    process.stdout.write(markdown);
  }
}

let reportText;
try {
  reportText = await readFile(reportPath, "utf8");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  await publish("# Frontend E2E results\n\nNo Playwright JSON report was generated. Check the preceding workflow steps.\n");
  process.exitCode = 1;
}

if (reportText !== undefined) {
  let report;
  try {
    report = JSON.parse(reportText);
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
    await publish("# Frontend E2E results\n\nThe Playwright JSON report could not be parsed.\n");
    process.exitCode = 1;
  }

  if (report !== undefined) {
    const stats = report.stats;
    const counts = ["expected", "unexpected", "skipped", "flaky"];
    if (!stats || counts.some((key) => !Number.isFinite(stats[key]))) {
      await publish("# Frontend E2E results\n\nThe Playwright JSON report is missing valid result counts.\n");
      process.exitCode = 1;
    } else {
      const total = stats.expected + stats.unexpected + stats.skipped + stats.flaky;
      const duration = `${(stats.duration / 1000).toFixed(1)} s`;
      const lines = [
        "# Frontend E2E results",
        "",
        `**Result:** ${stats.unexpected === 0 ? "PASS" : "FAIL"}`,
        "",
        "| Total | Passed | Failed | Flaky | Skipped | Duration |",
        "|---:|---:|---:|---:|---:|---:|",
        `| ${total} | ${stats.expected} | ${stats.unexpected} | ${stats.flaky} | ${stats.skipped} | ${duration} |`,
        "",
      ];

      const failed = [];
      const skipped = [];
      const visitSuites = (suites, parents = []) => {
        for (const suite of suites ?? []) {
          const names = suite.title ? [...parents, suite.title] : parents;
          for (const spec of suite.specs ?? []) {
            const title = [...names, spec.title].filter(Boolean).join(" / ");
            for (const test of spec.tests ?? []) {
              const results = test.results ?? [];
              const lastResult = results.at(-1);
              const isSkipped = test.expectedStatus === "skipped"
                || lastResult?.status === "skipped"
                || test.annotations?.some((annotation) => ["skip", "fixme"].includes(annotation.type));
              if (isSkipped) skipped.push(title);
              if (test.outcome === "unexpected" || ["failed", "timedOut", "interrupted"].includes(lastResult?.status)) {
                failed.push(title);
              }
            }
          }
          visitSuites(suite.suites, names);
        }
      };
      visitSuites(report.suites);

      if (failed.length) {
        lines.push("## Failed tests", "", ...failed.map((title) => `- ${title}`), "");
      } else {
        lines.push("No failed tests.", "");
      }

      if (skipped.length) {
        lines.push("## Skipped tests", "", ...skipped.map((title) => `- ${title}`), "");
      }

      lines.push("Playwright E2E tests use mocked API responses; the backend is not part of this run.", "");
      await publish(lines.join("\n"));
      if (stats.unexpected > 0) process.exitCode = 1;
    }
  }
}
