"""Run isolated MySQL integration suites, stopping on the first failure."""

import json
import os
from pathlib import Path
import subprocess
import sys

SUITES = (
    "auth",
    "catalog",
    "scheduling",
    "amendments",
    "documents",
    "reports",
    "notifications",
)
root = Path(__file__).resolve().parent
result_dir = Path(
    os.getenv("TEST_RESULT_DIR", str(root.parent / "verification"))
).resolve()
result_dir.mkdir(parents=True, exist_ok=True)
summary_file = result_dir / "summary.json"
summary_file.unlink(missing_ok=True)
for name in SUITES:
    subprocess.run(
        [sys.executable, str(root / f"test_{name}.py")], cwd=root, check=True
    )
summary = []
for name in SUITES:
    result = json.loads((result_dir / f"{name}-result.json").read_text())
    if result["passed"] != result["total"] or result["total"] != len(result["tests"]):
        raise SystemExit("Invalid verification result: " + name)
    summary.append(dict(suite=name, passed=result["passed"], total=result["total"]))
value = dict(
    status="PASS",
    passed=sum(s["passed"] for s in summary),
    total=sum(s["total"] for s in summary),
    suites=summary,
    scope="Isolated MySQL + FastAPI ASGI and loopback SMTP. Not a real external mailbox, browser, Docker Desktop or LAN acceptance result.",
)
summary_file.write_text(json.dumps(value, ensure_ascii=False, indent=2))
print(json.dumps(value, ensure_ascii=False), flush=True)
