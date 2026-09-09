#!/bin/bash
set -uo pipefail

ROOT="${NEXUS_ROOT:-$HOME/Developer/nexus}"
WORKSPACE="${NEXUS_ACCEPTANCE_WORKSPACE:-$HOME/.nexus/acceptance-workspace}"
GLOBAL="$HOME/.nexus"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$GLOBAL/acceptance"
REPORT="${NEXUS_ACCEPTANCE_REPORT:-$REPORT_DIR/NEXUS_CORE_ACCEPTANCE_$STAMP.txt}"
TMPROOT="${NEXUS_ACCEPTANCE_TMP:-/tmp/nexus_core_acceptance_$STAMP}"

export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p \
    "$REPORT_DIR" \
    "$TMPROOT"

PASS=0
FAIL=0
WARN=0

pass() {
    PASS=$((PASS+1))
    echo "PASS  $*" | tee -a "$REPORT"
}

fail() {
    FAIL=$((FAIL+1))
    echo "FAIL  $*" | tee -a "$REPORT"
}

warn() {
    WARN=$((WARN+1))
    echo "WARN  $*" | tee -a "$REPORT"
}

section() {
    echo | tee -a "$REPORT"
    echo "============================================================" | tee -a "$REPORT"
    echo "$*" | tee -a "$REPORT"
    echo "============================================================" | tee -a "$REPORT"
}

run_ok() {
    local name="$1"
    shift

    if "$@" >/tmp/nexus_core_cmd.txt 2>&1; then
        pass "$name"
    else
        cat /tmp/nexus_core_cmd.txt | tee -a "$REPORT"
        fail "$name"
    fi
}

source "$ROOT/.venv/bin/activate"

{
    echo "NEXUS CORE CANONICAL ACCEPTANCE"
    echo "DATE=$(date)"
    echo "ROOT=$ROOT"
    echo "WORKSPACE=$WORKSPACE"
} > "$REPORT"

# ============================================================
# 1. SOURCE / COMPILE
# ============================================================

section "1. SOURCE / COMPILE"

if python -m compileall -q "$ROOT/nexus"; then
    pass "Full Python compile"
else
    fail "Full Python compile"
fi

# ============================================================
# 2. CLI SURFACE
# ============================================================

section "2. CLI SURFACE"

if nexus --version >/tmp/nexus_core_version.txt 2>&1; then
    pass "nexus --version"
else
    fail "nexus --version"
fi

nexus --help >/tmp/nexus_core_help.txt 2>&1 || true

for command in \
    chat \
    run \
    auto \
    doctor \
    models \
    providers \
    tools \
    mcp \
    memory \
    plugins \
    permissions \
    runs \
    resume \
    logs \
    jobs
do
    if grep -q "$command" /tmp/nexus_core_help.txt; then
        pass "CLI command: $command"
    else
        fail "CLI command missing: $command"
    fi
done

# ============================================================
# 3. DOCTOR / MODEL
# ============================================================

section "3. DOCTOR / LOCAL MODEL"

if nexus doctor >/tmp/nexus_core_doctor.txt 2>&1 \
    && grep -q "NEXUS_DOCTOR=PASS" /tmp/nexus_core_doctor.txt
then
    pass "Nexus doctor"
else
    cat /tmp/nexus_core_doctor.txt | tee -a "$REPORT"
    fail "Nexus doctor"
fi

if command -v ollama >/dev/null 2>&1; then
    pass "Ollama installed"
else
    fail "Ollama installed"
fi

if curl -fsS \
    http://127.0.0.1:11434/api/tags \
    >/tmp/nexus_core_ollama.json
then
    pass "Ollama API"
else
    fail "Ollama API"
fi

python - <<'PY' >/tmp/nexus_core_model.txt 2>&1
import subprocess
from nexus.config import effective_config

cfg = effective_config(
    "$WORKSPACE"
)

model = cfg["model"]

print("MODEL=", model)

r = subprocess.run(
    ["ollama", "show", model],
    capture_output=True,
    text=True,
)

assert r.returncode == 0

print("MODEL_EXISTS=PASS")
PY

if grep -q "MODEL_EXISTS=PASS" /tmp/nexus_core_model.txt; then
    pass "Configured model exists"
else
    cat /tmp/nexus_core_model.txt | tee -a "$REPORT"
    fail "Configured model exists"
fi

# ============================================================
# 4. WORKSPACE INDEPENDENCE
# ============================================================

section "4. WORKSPACE INDEPENDENCE"

TEMP_WS="$TMPROOT/workspace"
mkdir -p "$TEMP_WS"

(
    cd "$TEMP_WS"
    nexus init
) >/tmp/nexus_core_init.txt 2>&1

if test -f "$TEMP_WS/.nexus/workspace.yaml"; then
    pass "Fresh workspace initialization"
else
    cat /tmp/nexus_core_init.txt | tee -a "$REPORT"
    fail "Fresh workspace initialization"
fi

if (
    cd "$TEMP_WS"
    nexus doctor
) >/tmp/nexus_core_temp_doctor.txt 2>&1
then
    pass "Doctor works outside the active workspace"
else
    cat /tmp/nexus_core_temp_doctor.txt | tee -a "$REPORT"
    warn "Fresh workspace doctor"
fi

# ============================================================
# 5. SANDBOX
# ============================================================

section "5. WORKSPACE SANDBOX"

python - <<'PY' >/tmp/nexus_core_sandbox.txt 2>&1
from nexus.tools import Tools

t = Tools(
    "$WORKSPACE",
    "architect",
    "core_sandbox",
)

result = t.read_file(
    "../europa-park-planner/index.html"
)

print(result)

assert (
    "WORKSPACE_SANDBOX_BLOCK" in str(result)
    or "SAFETY_BLOCK" in str(result)
)

print("SANDBOX=PASS")
PY

if grep -q "SANDBOX=PASS" /tmp/nexus_core_sandbox.txt; then
    pass "Sibling workspace blocked"
else
    cat /tmp/nexus_core_sandbox.txt | tee -a "$REPORT"
    fail "Sibling workspace blocked"
fi

# ============================================================
# 6. PERMISSIONS
# ============================================================

section "6. PERMISSION ENGINE"

python - <<'PY' >/tmp/nexus_core_permissions.txt 2>&1
from nexus.runtime.permissions import PermissionEngine

qa = PermissionEngine("qa")

assert qa.allowed("read")
assert not qa.allowed(
    "network",
    "web_fetch",
)

scoped = PermissionEngine(
    "qa",
    task_grants={
        "web_fetch"
    },
)

assert scoped.allowed(
    "network",
    "web_fetch",
)

assert not scoped.allowed(
    "process",
    "shell",
)

print("PERMISSIONS=PASS")
PY

if grep -q "PERMISSIONS=PASS" /tmp/nexus_core_permissions.txt; then
    pass "Task-scoped permissions"
else
    cat /tmp/nexus_core_permissions.txt | tee -a "$REPORT"
    fail "Task-scoped permissions"
fi

# ============================================================
# 7. ANTI-STUB / ACCEPTANCE
# ============================================================

section "7. ACCEPTANCE INTEGRITY"

set +e

nexus acceptance verify \
    --name "Canonical real implementation" \
    --real \
    --executed \
    --command "python real.py" \
    --exit-code 0 \
    --evidence "This is a stub by design." \
    >/tmp/nexus_core_stub.txt 2>&1

STUB_RC=$?

set -e

if [ "$STUB_RC" -ne 0 ]; then
    pass "Stub rejected for real implementation"
else
    fail "Stub incorrectly accepted"
fi

# ============================================================
# 8. NODE COMPLETION NEGATIVE TESTS
# ============================================================

section "8. NODE COMPLETION"

python - <<'PY' >/tmp/nexus_core_completion.txt 2>&1
from nexus.runtime.node_acceptance import (
    evaluate_node_completion,
)

clarification = """
Could you please specify what you want?

NEXUS_EVIDENCE_SUMMARY={"tool_calls":0,"successful":0,"failed":0,"tools":[]}
"""

ok, reason = evaluate_node_completion(
    "researcher",
    "Research official website",
    ["Obtain web evidence"],
    clarification,
)

assert ok is False

zero = """
I think the answer is probably correct.

NEXUS_EVIDENCE_SUMMARY={"tool_calls":0,"successful":0,"failed":0,"tools":[]}
"""

ok, reason = evaluate_node_completion(
    "researcher",
    "Research official website using authoritative web evidence",
    ["Obtain exact result"],
    zero,
)

assert ok is False

print("NODE_COMPLETION=PASS")
PY

if grep -q "NODE_COMPLETION=PASS" /tmp/nexus_core_completion.txt; then
    pass "Incomplete nodes cannot PASS"
else
    cat /tmp/nexus_core_completion.txt | tee -a "$REPORT"
    fail "Node completion integrity"
fi

# ============================================================
# 9. QA EVIDENCE INTEGRITY
# ============================================================

section "9. QA EVIDENCE INTEGRITY"

python - <<'PY' >/tmp/nexus_core_evidence.txt 2>&1
from nexus.runtime.evidence_integrity import (
    independent_evidence_passed,
)

fake = """
Verification PASS
NEXUS_EVIDENCE_SUMMARY={"tool_calls":1,"successful":1,"failed":0,"tools":[{"tool":"acceptance_verify","success":true}]}
"""

ok, reason = independent_evidence_passed(
    "qa",
    "Independently verify result",
    ["verification completed"],
    fake,
)

assert ok is False

real = """
Verified independently
NEXUS_EVIDENCE_SUMMARY={"tool_calls":2,"successful":2,"failed":0,"tools":[{"tool":"web_fetch","success":true},{"tool":"acceptance_verify","success":true}]}
"""

ok, reason = independent_evidence_passed(
    "qa",
    "Independently verify result",
    ["verification completed"],
    real,
)

assert ok is True

print("EVIDENCE_INTEGRITY=PASS")
PY

if grep -q "EVIDENCE_INTEGRITY=PASS" /tmp/nexus_core_evidence.txt; then
    pass "Independent QA evidence integrity"
else
    cat /tmp/nexus_core_evidence.txt | tee -a "$REPORT"
    fail "Independent QA evidence integrity"
fi

# ============================================================
# 10. FAST PLANNER
# ============================================================

section "10. FAST PLANNER"

python - <<'PY' >/tmp/nexus_core_fastplanner.txt 2>&1
from nexus.planning.fast import (
    simple_web_research_plan,
)

request = (
    "Research the official Python homepage and "
    "determine its exact page title using web evidence. "
    "Then have independent QA verify it."
)

plan = simple_web_research_plan(
    request
)

assert plan
assert len(plan["tasks"]) == 2

t1 = plan["tasks"][0]
t2 = plan["tasks"][1]

assert t1["role"] == "researcher"
assert t2["role"] == "qa"
assert "Python" in t1["objective"]
assert "page title" in t1["objective"]
assert "Python" in t2["objective"]
assert t2["dependencies"] == ["T1"]

print("FAST_PLANNER=PASS")
PY

if grep -q "FAST_PLANNER=PASS" /tmp/nexus_core_fastplanner.txt; then
    pass "Deterministic fast planner"
else
    cat /tmp/nexus_core_fastplanner.txt | tee -a "$REPORT"
    fail "Deterministic fast planner"
fi

# ============================================================
# 11. COMPLEX LLM PLANNER
# ============================================================

section "11. COMPLEX LLM PLANNER"

python - <<'PY' >/tmp/nexus_core_complex_planner.txt 2>&1
import time

from nexus.orchestration.autonomous import (
    AutonomousOrchestrator,
)

runtime = AutonomousOrchestrator(
    "$WORKSPACE",
    live=False,
)

started = time.time()

plan = runtime.plan(
    "Inspect repository architecture read-only, "
    "identify one hypothetical implementation task, "
    "and define independent QA acceptance. "
    "Do not modify anything."
)

elapsed = time.time() - started

assert plan.tasks

print(
    "COMPLEX_PLANNER_SECONDS=",
    round(elapsed, 3),
)

print(
    "COMPLEX_PLANNER_TASKS=",
    len(plan.tasks),
)

print("COMPLEX_PLANNER=PASS")
PY

if grep -q "COMPLEX_PLANNER=PASS" /tmp/nexus_core_complex_planner.txt; then
    cat /tmp/nexus_core_complex_planner.txt | tee -a "$REPORT"
    pass "Complex LLM planner"
else
    cat /tmp/nexus_core_complex_planner.txt | tee -a "$REPORT"
    fail "Complex LLM planner"
fi

# ============================================================
# 12. TOOL REGISTRY
# ============================================================

section "12. TOOL REGISTRY"

nexus tools list >/tmp/nexus_core_tools.txt 2>&1

for tool in \
    read_file \
    shell \
    web_search \
    web_fetch \
    browser_run \
    memory_search \
    process_start
do
    if grep -q "$tool" /tmp/nexus_core_tools.txt; then
        pass "Tool registered: $tool"
    else
        fail "Tool missing: $tool"
    fi
done

# ============================================================
# 13. SCHEMA / DISPATCH PARITY
# ============================================================

section "13. SCHEMA / DISPATCH PARITY"

python - <<'PY' >/tmp/nexus_core_registry.txt 2>&1
from nexus.runtime.tool_factory import (
    build_registry,
)

registry, _ = build_registry(
    "$WORKSPACE",
    "researcher",
    "canonical_registry",
    include_mcp=False,
)

names = set(
    registry.names()
)

schema_names = {
    item["function"]["name"]
    for item in registry.schemas()
}

assert names == schema_names

for name in names:
    assert registry.get(name) is not None

print("REGISTRY_PARITY=PASS")
PY

if grep -q "REGISTRY_PARITY=PASS" /tmp/nexus_core_registry.txt; then
    pass "Schema / dispatcher parity"
else
    cat /tmp/nexus_core_registry.txt | tee -a "$REPORT"
    fail "Schema / dispatcher parity"
fi

# ============================================================
# 14. WEB / BROWSER
# ============================================================

section "14. WEB / BROWSER"

python - <<'PY' >/tmp/nexus_core_web.txt 2>&1
from nexus.runtime.tool_factory import (
    build_registry,
)

workspace = (
    "$WORKSPACE"
)

registry, permissions = build_registry(
    workspace,
    "researcher",
    "canonical_web",
    task_grants={
        "web_fetch",
        "browser_run",
    },
    include_mcp=False,
)

for name in (
    "web_fetch",
    "browser_run",
):
    tool = registry.get(name)

    assert tool is not None

    permissions.enforce(
        tool.permission,
        name,
    )

fetch = registry.execute(
    "web_fetch",
    {
        "url": "https://www.python.org/",
        "max_chars": 1000,
    },
)

assert "Python" in str(fetch)

title = registry.execute(
    "browser_run",
    {
        "url": "https://www.python.org/",
        "action": "title",
    },
)

assert "Python" in str(title)

print("WEB_BROWSER=PASS")
PY

if grep -q "WEB_BROWSER=PASS" /tmp/nexus_core_web.txt; then
    pass "Web fetch + browser title"
else
    cat /tmp/nexus_core_web.txt | tee -a "$REPORT"
    fail "Web fetch + browser title"
fi

# ============================================================
# 15. MCP LAZY + EXPLICIT
# ============================================================

section "15. MCP"

python - <<'PY' >/tmp/nexus_core_lazy_mcp.txt 2>&1
from nexus.runtime.tool_factory import (
    build_registry,
)

registry, _ = build_registry(
    "$WORKSPACE",
    "researcher",
    "canonical_lazy_mcp",
    include_mcp=False,
)

assert not any(
    name.startswith("mcp_")
    for name in registry.names()
)

print("LAZY_MCP=PASS")
PY

if grep -q "LAZY_MCP=PASS" /tmp/nexus_core_lazy_mcp.txt; then
    pass "Lazy MCP"
else
    fail "Lazy MCP"
fi

if nexus mcp test robridge >/tmp/nexus_core_mcp.txt 2>&1 \
    && ! grep -q "MCP_LIST_ERROR" /tmp/nexus_core_mcp.txt
then
    pass "Explicit MCP path"
else
    cat /tmp/nexus_core_mcp.txt | tee -a "$REPORT"
    fail "Explicit MCP path"
fi

# ============================================================
# 16. MEMORY
# ============================================================

section "16. MEMORY"

MEMORY_MARKER="CORE_ACCEPTANCE_$STAMP"

if nexus memory add \
    "$MEMORY_MARKER" \
    --kind acceptance \
    >/tmp/nexus_core_memory_add.txt 2>&1 \
    && nexus memory search "$MEMORY_MARKER" \
    >/tmp/nexus_core_memory_search.txt 2>&1 \
    && grep -q "$MEMORY_MARKER" \
    /tmp/nexus_core_memory_search.txt
then
    pass "Persistent memory"
else
    fail "Persistent memory"
fi

# ============================================================
# 17. TOOL CACHE
# ============================================================

section "17. TOOL CACHE"

python - <<'PY' >/tmp/nexus_core_cache.txt 2>&1
from nexus.runtime.tool_cache import (
    ToolCallCache,
)

cache = ToolCallCache()

args = {
    "name": "canonical",
    "description": "canonical",
}

assert cache.get(
    "acceptance_verify",
    args,
) is None

cache.put(
    "acceptance_verify",
    args,
    "PASS",
)

assert cache.get(
    "acceptance_verify",
    args,
) == "PASS"

cache.put(
    "write_file",
    {"path": "x"},
    "BAD",
)

assert cache.get(
    "write_file",
    {"path": "x"},
) is None

print("TOOL_CACHE=PASS")
PY

if grep -q "TOOL_CACHE=PASS" /tmp/nexus_core_cache.txt; then
    pass "Safe tool-call cache"
else
    fail "Safe tool-call cache"
fi

# ============================================================
# 18. DURABLE JOB BASIC
# ============================================================

section "18. DURABLE JOB BASIC"

JOB_DIR="$TMPROOT/jobs"
mkdir -p "$JOB_DIR"

JOB_ID="$(
python - <<PY
from nexus.jobs import JobStore

s = JobStore("$WORKSPACE")

jid = s.create_job(
    "canonical-basic",
    [
        {
            "name": "one",
            "command": (
                "echo ONE > "
                "$JOB_DIR/one.txt"
            ),
        },
        {
            "name": "two",
            "command": (
                "echo TWO > "
                "$JOB_DIR/two.txt"
            ),
        },
    ],
)

print(jid)
PY
)"

if nexus jobs run \
    --workspace "$WORKSPACE" \
    "$JOB_ID" \
    >/tmp/nexus_core_job.txt 2>&1 \
    && test -f "$JOB_DIR/one.txt" \
    && test -f "$JOB_DIR/two.txt"
then
    pass "Durable sequential job"
else
    cat /tmp/nexus_core_job.txt | tee -a "$REPORT"
    fail "Durable sequential job"
fi

# ============================================================
# 19. JOB RETRY
# ============================================================

section "19. DURABLE JOB RETRY"

RETRY_FILE="$JOB_DIR/retry_count"
rm -f "$RETRY_FILE"

JOB_RETRY="$(
python - <<PY
from nexus.jobs import JobStore

s = JobStore("$WORKSPACE")

cmd = r'''
COUNT=0

if [ -f "$RETRY_FILE" ]; then
    COUNT=\$(cat "$RETRY_FILE")
fi

COUNT=\$((COUNT+1))
echo "\$COUNT" > "$RETRY_FILE"

if [ "\$COUNT" -lt 2 ]; then
    exit 7
fi
'''

jid = s.create_job(
    "canonical-retry",
    [
        {
            "name": "retry",
            "command": cmd,
        }
    ],
    max_retries=2,
)

print(jid)
PY
)"

if nexus jobs run \
    --workspace "$WORKSPACE" \
    "$JOB_RETRY" \
    >/tmp/nexus_core_retry.txt 2>&1 \
    && [ "$(cat "$RETRY_FILE")" = "2" ]
then
    pass "Durable retry"
else
    cat /tmp/nexus_core_retry.txt | tee -a "$REPORT"
    fail "Durable retry"
fi

# ============================================================
# 20. RESOURCE CLEANUP
# ============================================================

section "20. RESOURCE CLEANUP"

set +e

PYTHONWARNINGS="error::ResourceWarning" \
nexus run \
    --workspace "$WORKSPACE" \
    "Do not use tools. Reply exactly RESOURCE_CLEANUP_PASS." \
    >/tmp/nexus_core_resources.txt 2>&1

RESOURCE_RC=$?

set -e

if [ "$RESOURCE_RC" -eq 0 ] \
    && ! grep -qi "unclosed database" \
        /tmp/nexus_core_resources.txt
then
    pass "SQLite/resource cleanup"
else
    cat /tmp/nexus_core_resources.txt | tee -a "$REPORT"
    fail "SQLite/resource cleanup"
fi

# ============================================================
# 21. PACKAGING / CLEAN VENV
# ============================================================

section "21. PACKAGING SMOKE"

VENV="$TMPROOT/package_venv"

python3 -m venv "$VENV"

"$VENV/bin/python" -m pip install \
    --quiet \
    --upgrade pip \
    >/tmp/nexus_core_pip_upgrade.txt 2>&1

if "$VENV/bin/python" -m pip install \
    --quiet \
    "$ROOT" \
    >/tmp/nexus_core_package_install.txt 2>&1
then
    pass "Fresh venv package install"
else
    cat /tmp/nexus_core_package_install.txt | tee -a "$REPORT"
    fail "Fresh venv package install"
fi

if "$VENV/bin/nexus" --version \
    >/tmp/nexus_core_package_version.txt 2>&1
then
    pass "Installed nexus executable"
else
    cat /tmp/nexus_core_package_version.txt | tee -a "$REPORT"
    fail "Installed nexus executable"
fi

if "$VENV/bin/nexus" --help \
    >/tmp/nexus_core_package_help.txt 2>&1
then
    pass "Installed nexus --help"
else
    fail "Installed nexus --help"
fi

# ============================================================
# 22. WARM AUTONOMOUS WEB E2E
# ============================================================

section "22. AUTONOMOUS WEB E2E"

# Warm model first.
python - <<'PY' >/tmp/nexus_core_warm.txt 2>&1
from nexus.config import effective_config
from nexus.runtime.ollama_profile import chat

cfg = effective_config(
    "$WORKSPACE"
)

chat(
    cfg["model"],
    [
        {
            "role": "user",
            "content": "Reply READY",
        }
    ],
    num_predict=8,
    keep_alive="30m",
)

print("WARM=PASS")
PY

START="$(
python - <<'PY'
import time
print(time.time())
PY
)"

set +e

nexus auto \
    --workspace "$WORKSPACE" \
    "Research the official Python homepage and determine its exact page title using real web evidence. Then have an independent QA specialist verify T1's finding using its own official-site evidence. QA must not pass based only on T1. Do not inspect project files, do not use shell, and do not use MCP." \
    >/tmp/nexus_core_e2e.txt 2>&1

E2E_RC=$?

set -e

END="$(
python - <<'PY'
import time
print(time.time())
PY
)"

E2E_SECONDS="$(
python - <<PY
print(
    round(
        float("$END")
        - float("$START"),
        3,
    )
)
PY
)"

echo "WEB_E2E_SECONDS=$E2E_SECONDS" \
    | tee -a "$REPORT"

if [ "$E2E_RC" -eq 0 ] \
    && grep -q '"status": "PASS"' \
        /tmp/nexus_core_e2e.txt \
    && grep -qi 'Welcome to Python.org' \
        /tmp/nexus_core_e2e.txt \
    && grep -q \
        'REASON=INDEPENDENT_SOURCE_EVIDENCE_PRESENT' \
        /tmp/nexus_core_e2e.txt
then
    pass "Autonomous web + independent QA"
else
    cat /tmp/nexus_core_e2e.txt | tee -a "$REPORT"
    fail "Autonomous web + independent QA"
fi

if grep -q 'UNKNOWN_TOOL=' \
    /tmp/nexus_core_e2e.txt
then
    fail "No unknown tools in E2E"
else
    pass "No unknown tools in E2E"
fi

if grep -q 'NEXUS_PERMISSION_BLOCK=' \
    /tmp/nexus_core_e2e.txt
then
    fail "No permission blocks in E2E"
else
    pass "No permission blocks in E2E"
fi

if grep -q '\[RoBridge\]' \
    /tmp/nexus_core_e2e.txt
then
    fail "No unnecessary MCP in web E2E"
else
    pass "No unnecessary MCP in web E2E"
fi

# Warm target: <= 60 seconds.
python - <<PY >/tmp/nexus_core_latency.txt
value = float("$E2E_SECONDS")

if value <= 60:
    print("LATENCY=PASS")
elif value <= 75:
    print("LATENCY=WARN")
else:
    print("LATENCY=FAIL")
PY

if grep -q "LATENCY=PASS" \
    /tmp/nexus_core_latency.txt
then
    pass "Warm E2E latency <= 60s"

elif grep -q "LATENCY=WARN" \
    /tmp/nexus_core_latency.txt
then
    warn "Warm E2E latency >60s <=75s"

else
    fail "Warm E2E latency >75s"
fi

# ============================================================
# 23. MODEL RESIDENCY
# ============================================================

section "23. MODEL RESIDENCY"

if curl -fsS \
    http://127.0.0.1:11434/api/ps \
    >/tmp/nexus_core_ps.json
then
    python - <<'PY' >/tmp/nexus_core_resident.txt
import json

with open(
    "/tmp/nexus_core_ps.json",
    encoding="utf-8",
) as f:
    data = json.load(f)

models = data.get(
    "models",
    []
)

assert models

print(
    "MODEL_RESIDENCY=PASS"
)
PY

    if grep -q "MODEL_RESIDENCY=PASS" \
        /tmp/nexus_core_resident.txt
    then
        pass "Model remains resident"
    else
        fail "Model remains resident"
    fi
else
    fail "Ollama residency API"
fi

# ============================================================
# FINAL
# ============================================================

section "FINAL"

{
    echo
    echo "PASS_COUNT=$PASS"
    echo "WARN_COUNT=$WARN"
    echo "FAIL_COUNT=$FAIL"
    echo
    echo "SOURCE_COMPILE=TESTED"
    echo "CLI=TESTED"
    echo "LOCAL_MODEL=TESTED"
    echo "WORKSPACE_INDEPENDENCE=TESTED"
    echo "SANDBOX=TESTED"
    echo "TASK_SCOPED_PERMISSIONS=TESTED"
    echo "ANTI_STUB=TESTED"
    echo "NODE_COMPLETION=TESTED"
    echo "QA_EVIDENCE_INTEGRITY=TESTED"
    echo "FAST_PLANNER=TESTED"
    echo "COMPLEX_LLM_PLANNER=TESTED"
    echo "TOOL_REGISTRY=TESTED"
    echo "SCHEMA_DISPATCH_PARITY=TESTED"
    echo "WEB_BROWSER=TESTED"
    echo "LAZY_MCP=TESTED"
    echo "EXPLICIT_MCP=TESTED"
    echo "MEMORY=TESTED"
    echo "TOOL_CACHE=TESTED"
    echo "DURABLE_JOBS=TESTED"
    echo "JOB_RETRY=TESTED"
    echo "RESOURCE_CLEANUP=TESTED"
    echo "PACKAGE_INSTALL=TESTED"
    echo "AUTONOMOUS_WEB_QA=TESTED"
    echo "MODEL_RESIDENCY=TESTED"
    echo "WEB_E2E_SECONDS=$E2E_SECONDS"
} | tee -a "$REPORT"

if [ "$FAIL" -eq 0 ]; then
    echo "NEXUS_CORE_STABLE=PASS" \
        | tee -a "$REPORT"

    echo
    echo "============================================================"
    echo " NEXUS CORE CANONICAL ACCEPTANCE PASSED"
    echo "============================================================"
    echo "PASS_COUNT=$PASS"
    echo "WARN_COUNT=$WARN"
    echo "FAIL_COUNT=$FAIL"
    echo "WEB_E2E_SECONDS=$E2E_SECONDS"
    echo "REPORT=$REPORT"
    echo "NEXUS_CORE_STABLE=PASS"
    echo "============================================================"

    exit 0
else
    echo "NEXUS_CORE_STABLE=FAIL" \
        | tee -a "$REPORT"

    echo
    echo "============================================================"
    echo " NEXUS CORE CANONICAL ACCEPTANCE FAILED"
    echo "============================================================"
    echo "PASS_COUNT=$PASS"
    echo "WARN_COUNT=$WARN"
    echo "FAIL_COUNT=$FAIL"
    echo "REPORT=$REPORT"
    echo "NEXUS_CORE_STABLE=FAIL"
    echo "============================================================"

    exit 1
fi
