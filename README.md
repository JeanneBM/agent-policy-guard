# Agent Policy Guard

**Deterministic authorization layer for proposed AI agent actions.**

> The model proposes; deterministic policy authorizes; execution is verified.

A small Python library for validating versioned YAML policies, evaluating proposed
actions and gating a host-owned executor. No LLM, cloud account or running cluster
is required.

## Status

Early PoC. Includes offline Kubernetes image-repair and CI patch-proposal examples,
plus a dependency-free callable suitable for a LangGraph node. Existing portfolio
repositories have **not** yet been migrated to this library. No live Kubernetes
adapter, GitHub PR writer, Entra integration or human approval service is included.

## Quick start

Run from the repository root with Python 3.11+:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
python examples/k8s_image_repair_example.py
python examples/ci_code_change_example.py
```

The Kubernetes example writes metadata-only events to `.local/audit.jsonl`.
Both examples simulate execution and incur no cloud costs. The package is not
published on PyPI; install from this checkout.

## API

```python
from agent_policy_guard import Action, Context, PolicyEngine, GuardedExecutor, JsonlAudit

engine = PolicyEngine.from_yaml("policies/ci_code_change.yaml")
proposal = Action(
    type="ci.propose_patch",
    target="example/ci-lab",
    parameters={"patch": "example test-only patch"},
)
# Demonstration facts only. The trusted host must independently verify the exact
# patch and repository state before constructing this context.
context = Context(
    actor="ci-repair-agent",
    environment="lab",
    facts={"patch_verified": True, "touches_workflow": False, "tests_passed": True},
)
guard = GuardedExecutor(
    engine,
    action_type="ci.propose_patch",
    executor=lambda action, context: {"simulated": action.parameters["patch"]},
    audit=JsonlAudit(".local/audit.jsonl"),
)
print(guard.execute(proposal, context))
```

## Decision semantics

| Decision | Execution |
| --- | --- |
| `allow` | Executor may run; configured conditions matched |
| `deny` | Blocked |
| `require_human` | Blocked; approval workflow is not implemented |
| `escalate` | Blocked; host may route for further review |

All conditions in a rule must match. Missing fields never match. All matching
rules are considered, with precedence `deny > require_human > escalate > allow`.
Ties use rule ID order. No match means deny.

Supported operators are exact JSON `eq` and list membership `in`. Unknown schema
fields, unsupported operators, empty conditions, duplicate rule IDs and duplicate
YAML keys are rejected. Booleans and numbers are distinct. There is no expression
evaluation, Python DSL, dynamic import or command execution in policies.

## Trust boundary

The LLM supplies a proposal, never authoritative identity, environment or evidence.
The host owns policies, context construction, executor binding and credentials.
Call `GuardedExecutor.execute`, not a tool directly. Keep tool credentials outside
the agent process where practical: an in-process Python library cannot stop
arbitrary code with the same credentials from bypassing it.

The wrapper detaches nested caller data, re-evaluates every call and executes that
snapshot. It binds one action type per executor. Executor implementations must use
only validated parameters, reject unexpected domain-specific parameters and
independently validate current external state. The generic engine is not an action
schema validator.

An `allow` is policy compliance, not a guarantee that an operation is safe.
A returned executor call is recorded as `execution_returned`; the application must
verify the external outcome separately.

## Audit and limitations

Events include execution/event IDs, UTC timestamps, policy ID/version/hash,
request hash, decision and matched rules. Raw proposals, context, tool output and
exception text are omitted. Hashes support correlation; they are not signatures
or a confidentiality guarantee for low-entropy values.

Authorization must be logged before execution. A sink failure prevents starting
the executor. A failure when writing the completion event occurs **after** possible
side effects and cannot roll them back. Do not blindly retry.

Local JSONL is single-process, mutable and not a tamper-proof audit ledger.
No idempotency, approval tokens, replay protection, atomic external-state checks,
automatic rollback or post-execution verification is claimed.

## Files

| Path | Purpose |
| --- | --- |
| `src/agent_policy_guard/` | Models, strict YAML loader, evaluator, execution gate and audit sink |
| `policies/k8s_image_repair.yaml` | Exact lab image repair allowlist |
| `policies/ci_code_change.yaml` | Host-verified CI patch proposals |
| `examples/` | Offline usage and LangGraph node factory |
| `tests/` | Authorization, validation, isolation and audit failure cases |
| `docs/architecture.md` | Integration contract and next steps |

## Integration roadmap

1. Bind a least-privilege AKS executor to the actual lab resource and verify rollout.
2. Bind a CI proposal executor to a reviewed patch, repository and base commit.
3. Exercise both integrations in their existing repositories and retain evidence.
4. Add narrowly scoped approvals and idempotency only when the workflow needs them.

RAG citation validation is separate from action authorization; semantic grounding
is outside this PoC.

## License

MIT.
