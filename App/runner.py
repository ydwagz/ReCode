"""Runs player code against test inputs in a separate, resource-limited process.

The harness only receives the *inputs*; expected outputs never leave Django, so
player code cannot read the answers out of the harness's memory. Results are
printed after a random marker so ordinary ``print`` calls cannot spoof them.

This is a process-level sandbox (rlimits, timeouts, empty env, temp dir).
For a public deployment, run it inside a container / nsjail as well.
"""

import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

WALL_TIMEOUT_SECONDS = 10
CPU_LIMIT_SECONDS = 8
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
OUTPUT_LIMIT_BYTES = 1024 * 1024

PYTHON_HARNESS = r'''
import io, json, sys, time, resource, contextlib
payload = json.loads(sys.stdin.read())
marker = payload["marker"]
real_stdout = sys.stdout
namespace = {"__name__": "solution"}
results = []
def emit(data):
    real_stdout.write("\n" + marker + json.dumps(data) + "\n")
    real_stdout.flush()
captured = io.StringIO()
try:
    with contextlib.redirect_stdout(captured):
        exec(compile(payload["code"], "solution.py", "exec"), namespace)
except BaseException as exc:
    emit({"compile_error": f"{type(exc).__name__}: {exc}", "stdout": captured.getvalue()[-2000:]})
    sys.exit(0)
fn = namespace.get(payload["function"])
if not callable(fn):
    emit({"compile_error": f"Function '{payload['function']}' is not defined", "stdout": captured.getvalue()[-2000:]})
    sys.exit(0)
for case in payload["cases"]:
    out = io.StringIO()
    entry = {}
    try:
        best = None
        reps = 0
        while True:
            args = json.loads(json.dumps(case["args"]))
            with contextlib.redirect_stdout(out):
                start = time.perf_counter()
                value = fn(*args)
                elapsed = (time.perf_counter() - start) * 1000
            best = elapsed if best is None else min(best, elapsed)
            reps += 1
            if not case.get("perf") or reps >= 3 or best > 200:
                break
        try:
            entry["value"] = json.loads(json.dumps(value))
        except (TypeError, ValueError):
            entry["error"] = f"Return value is not JSON serialisable: {type(value).__name__}"
        entry["ms"] = best
    except BaseException as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
    entry["stdout"] = out.getvalue()[-1000:]
    results.append(entry)
emit({"results": results, "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
'''

JS_HARNESS = r'''
const fs = require("fs");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const marker = payload.marker;
const realLog = console.log;
let buffer = [];
const capture = (...a) => buffer.push(a.map(x => typeof x === "string" ? x : JSON.stringify(x)).join(" "));
const emit = (data) => process.stdout.write("\n" + marker + JSON.stringify(data) + "\n");
let fn;
console.log = capture;
try {
  fn = new Function(payload.code + `\nreturn typeof ${payload.function} === "function" ? ${payload.function} : undefined;`)();
} catch (e) {
  emit({compile_error: String(e), stdout: buffer.join("\n").slice(-2000)});
  process.exit(0);
}
if (typeof fn !== "function") {
  emit({compile_error: `Function '${payload.function}' is not defined`, stdout: buffer.join("\n").slice(-2000)});
  process.exit(0);
}
const results = [];
for (const c of payload.cases) {
  buffer = [];
  const entry = {};
  try {
    let best = null, reps = 0, value;
    while (true) {
      const args = JSON.parse(JSON.stringify(c.args));
      const start = process.hrtime.bigint();
      value = fn(...args);
      const ms = Number(process.hrtime.bigint() - start) / 1e6;
      best = best === null ? ms : Math.min(best, ms);
      reps++;
      if (!c.perf || reps >= 3 || best > 200) break;
    }
    entry.value = value === undefined ? null : JSON.parse(JSON.stringify(value));
    entry.ms = best;
  } catch (e) {
    entry.error = String(e);
  }
  entry.stdout = buffer.join("\n").slice(-1000);
  results.push(entry);
}
console.log = realLog;
emit({results, max_rss_kb: Math.round(process.memoryUsage().rss / 1024)});
'''


@dataclass
class CaseResult:
    passed: bool
    value: object = None
    expected: object = None
    error: str = ""
    stdout: str = ""
    ms: float = 0.0


@dataclass
class RunResult:
    status: str  # accepted | wrong | error | timeout
    cases: list = field(default_factory=list)
    error: str = ""
    stdout: str = ""
    memory_kb: int = 0

    @property
    def passed_count(self):
        return sum(1 for c in self.cases if c.passed)

    @property
    def total_runtime_ms(self):
        return sum(c.ms for c in self.cases)


def available_languages():
    langs = ["python"]
    if shutil.which("node"):
        langs.append("javascript")
    return langs


def _limit_resources(language):
    def apply():
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_LIMIT_BYTES, OUTPUT_LIMIT_BYTES))
        if language == "python":  # V8 reserves huge virtual ranges, so only cap Python's address space
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        os.setsid()

    return apply


def execute(language, code, function_name, cases):
    """Run ``code`` and call ``function_name`` with each case's args.

    ``cases`` is a list of dicts: {"args": [...], "perf": bool}.
    Returns the raw harness output dict (``results`` or ``compile_error``),
    or {"timeout": True} / {"crash": "..."}.
    """
    marker = "@@RECODE-" + secrets.token_hex(16) + "@@"
    payload = json.dumps({"marker": marker, "code": code, "function": function_name, "cases": cases})
    workdir = tempfile.mkdtemp(prefix="recode-run-")
    try:
        if language == "javascript":
            node = shutil.which("node")
            if not node:
                return {"crash": "JavaScript runtime is not installed on this server."}
            script = os.path.join(workdir, "harness.js")
            with open(script, "w") as fh:
                fh.write(JS_HARNESS)
            cmd = [node, "--max-old-space-size=256", "--stack-size=4096", script]
        else:
            script = os.path.join(workdir, "harness.py")
            with open(script, "w") as fh:
                fh.write(PYTHON_HARNESS)
            cmd = [sys.executable, "-I", "-S", script]
        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                text=True,
                cwd=workdir,
                env={"PATH": "/usr/bin:/bin", "HOME": workdir, "PYTHONIOENCODING": "utf-8"},
                timeout=WALL_TIMEOUT_SECONDS,
                preexec_fn=_limit_resources(language),
            )
        except subprocess.TimeoutExpired:
            return {"timeout": True}
        stdout = proc.stdout or ""
        idx = stdout.rfind(marker)
        if idx == -1:
            if proc.returncode in (-9, -24, 137, 152):  # SIGKILL / SIGXCPU
                return {"timeout": True}
            err = (proc.stderr or "").strip().splitlines()
            return {"crash": "\n".join(err[-8:]) or f"Process exited with code {proc.returncode}"}
        user_output = stdout[:idx].strip()
        data = json.loads(stdout[idx + len(marker):].strip().splitlines()[0])
        data.setdefault("stdout", user_output[-2000:])
        return data
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def values_equal(got, expected):
    if isinstance(expected, float) or isinstance(got, float):
        if isinstance(got, (int, float)) and isinstance(expected, (int, float)) and not isinstance(got, bool):
            return math.isclose(got, expected, rel_tol=1e-6, abs_tol=1e-6)
        return False
    if isinstance(expected, list) and isinstance(got, list):
        return len(got) == len(expected) and all(values_equal(g, e) for g, e in zip(got, expected))
    if isinstance(expected, dict) and isinstance(got, dict):
        return got.keys() == expected.keys() and all(values_equal(got[k], expected[k]) for k in expected)
    if isinstance(got, bool) != isinstance(expected, bool):
        return False
    return got == expected


def run_tests(language, code, function_name, tests):
    """Run code against TestCase-like objects (with .args, .expected, .is_performance)."""
    tests = list(tests)
    cases = [{"args": t.args, "perf": t.is_performance} for t in tests]
    raw = execute(language, code, function_name, cases)
    if raw.get("timeout"):
        return RunResult(status="timeout", error=f"Time limit exceeded ({CPU_LIMIT_SECONDS}s CPU).")
    if "crash" in raw:
        return RunResult(status="error", error=raw["crash"])
    if "compile_error" in raw:
        return RunResult(status="error", error=raw["compile_error"], stdout=raw.get("stdout", ""))

    result = RunResult(status="accepted", stdout=raw.get("stdout", ""), memory_kb=int(raw.get("max_rss_kb") or 0))
    for test, entry in zip(tests, raw["results"]):
        if "error" in entry:
            case = CaseResult(passed=False, expected=test.expected, error=entry["error"], stdout=entry.get("stdout", ""))
        else:
            case = CaseResult(
                passed=values_equal(entry.get("value"), test.expected),
                value=entry.get("value"),
                expected=test.expected,
                stdout=entry.get("stdout", ""),
                ms=entry.get("ms") or 0.0,
            )
        result.cases.append(case)
    if any(c.error for c in result.cases):
        result.status = "error"
    elif result.passed_count < len(tests):
        result.status = "wrong"
    return result


def compute_expected(reference_code, function_name, args_list):
    """Use the reference solution to produce expected outputs for a list of arg lists."""
    raw = execute("python", reference_code, function_name, [{"args": a, "perf": False} for a in args_list])
    if "results" not in raw:
        raise ValueError(raw.get("compile_error") or raw.get("crash") or "Reference solution timed out")
    outputs = []
    for entry in raw["results"]:
        if "error" in entry:
            raise ValueError(f"Reference solution failed: {entry['error']}")
        outputs.append(entry["value"])
    return outputs
