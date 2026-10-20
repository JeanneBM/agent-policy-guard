from copy import deepcopy
from pathlib import Path
import pytest
from pydantic import ValidationError
from agent_policy_guard import (
    Action, Context, Decision, PolicyEngine, GuardedExecutor,
    AuthorizationDenied, PolicyError, JsonlAudit,
)

ROOT = Path(__file__).resolve().parents[1]


def policy(decision="allow"):
    return {
        "id": "test", "version": "1",
        "rules": [{
            "id": "known", "decision": decision, "reason": "test rule",
            "conditions": [{"field": "action.type", "op": "eq", "value": "tool.safe"}],
        }],
    }


def request():
    return Action(type="tool.safe", target="lab", parameters={"value": "original"})


def context():
    return Context(actor="host", environment="lab")


def test_default_deny():
    result = PolicyEngine(policy()).evaluate(Action(type="unknown", target="lab"), context())
    assert result.decision == Decision.DENY


def test_deny_wins_regardless_of_order():
    data = policy()
    deny = deepcopy(data["rules"][0])
    deny.update(id="blocked", decision="deny")
    for rules in ([data["rules"][0], deny], [deny, data["rules"][0]]):
        assert PolicyEngine({**data, "rules": rules}).evaluate(request(), context()).decision == Decision.DENY


@pytest.mark.parametrize("decision", ["deny", "escalate", "require_human"])
def test_non_allow_never_calls_executor(decision):
    calls = []
    guard = GuardedExecutor(
        PolicyEngine(policy(decision)), action_type="tool.safe",
        executor=lambda *args: calls.append(args), audit=lambda event: None,
    )
    with pytest.raises(AuthorizationDenied):
        guard.execute(request(), context())
    assert calls == []


def test_audit_failure_blocks_execution():
    calls = []
    def broken(event):
        raise OSError("sink unavailable")
    guard = GuardedExecutor(
        PolicyEngine(policy()), action_type="tool.safe",
        executor=lambda *args: calls.append(args), audit=broken,
    )
    with pytest.raises(OSError):
        guard.execute(request(), context())
    assert calls == []


def test_executor_binding_blocks_other_action():
    calls = []
    guard = GuardedExecutor(
        PolicyEngine(policy()), action_type="other",
        executor=lambda *args: calls.append(args), audit=lambda event: None,
    )
    with pytest.raises(PermissionError):
        guard.execute(request(), context())
    assert calls == []


def test_detached_action_and_changed_proposal():
    original = request()
    def audit(event):
        original.parameters["value"] = "changed"
    guard = GuardedExecutor(
        PolicyEngine(policy()), action_type="tool.safe",
        executor=lambda approved, trusted: approved.parameters["value"], audit=audit,
    )
    first_hash = guard.engine.evaluate(original, context()).request_hash
    assert guard.execute(original, context()) == "original"
    assert guard.engine.evaluate(original, context()).request_hash != first_hash


def test_policy_snapshot_is_not_mutable_by_caller():
    data = policy()
    engine = PolicyEngine(data)
    data["rules"][0]["decision"] = "deny"
    assert engine.evaluate(request(), context()).decision == Decision.ALLOW


def test_missing_fact_denies_and_boolean_is_not_integer():
    data = policy()
    data["rules"][0]["conditions"].append(
        {"field": "context.facts.verified", "op": "eq", "value": True}
    )
    engine = PolicyEngine(data)
    for facts in ({}, {"verified": 1}, {"verified": "true"}):
        assert engine.evaluate(request(), Context(actor="host", environment="lab", facts=facts)).decision == Decision.DENY
    assert engine.evaluate(request(), Context(actor="host", environment="lab", facts={"verified": True})).decision == Decision.ALLOW


@pytest.mark.parametrize("mutation", ["unknown_field", "unknown_operator", "empty_conditions", "duplicate_id", "bad_path"])
def test_invalid_policy_rejected(mutation):
    data = policy()
    rule = data["rules"][0]
    if mutation == "unknown_field":
        rule["ignored_security_check"] = True
    elif mutation == "unknown_operator":
        rule["conditions"][0]["op"] = "execute"
    elif mutation == "empty_conditions":
        rule["conditions"] = []
    elif mutation == "duplicate_id":
        data["rules"].append(deepcopy(rule))
    else:
        rule["conditions"][0]["field"] = "arbitrary.path"
    with pytest.raises(ValidationError):
        PolicyEngine(data)


def test_duplicate_yaml_keys_rejected(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text("id: first\nid: second\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        PolicyEngine.from_yaml(path)


def test_deterministic_results():
    engine = PolicyEngine(policy())
    assert engine.evaluate(request(), context()) == engine.evaluate(request(), context())


def test_jsonl_audit_has_no_raw_parameters(tmp_path):
    import json
    path = tmp_path / "audit.jsonl"
    guard = GuardedExecutor(
        PolicyEngine(policy()), action_type="tool.safe",
        executor=lambda *args: "done", audit=JsonlAudit(path),
    )
    assert guard.execute(request(), context()) == "done"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["execution_id"] == records[1]["execution_id"]
    assert "original" not in path.read_text()


def test_executor_error_is_recorded():
    events = []
    def fail(*args):
        raise RuntimeError("tool failed")
    guard = GuardedExecutor(
        PolicyEngine(policy()), action_type="tool.safe", executor=fail, audit=events.append,
    )
    with pytest.raises(RuntimeError):
        guard.execute(request(), context())
    assert events[-1]["event"] == "execution_failed"


def test_in_operator():
    data = policy()
    data["rules"][0]["conditions"][0].update(op="in", value=["tool.safe", "tool.other"])
    assert PolicyEngine(data).evaluate(request(), context()).decision == Decision.ALLOW


def test_k8s_policy_and_changed_image():
    engine = PolicyEngine.from_yaml(ROOT / "policies/k8s_image_repair.yaml")
    action = Action(type="k8s.image_update", target="test-app/deployment/test-app", parameters={
        "container": "test-app", "current_image": "lab.azurecr.io/tset-app:1.4.2",
        "image": "lab.azurecr.io/test-app:1.4.2",
    })
    ctx = Context(actor="diagnostic-agent", environment="lab", facts={
        "image_exists": True, "observed_image": "lab.azurecr.io/tset-app:1.4.2",
    })
    assert engine.evaluate(action, ctx).decision == Decision.ALLOW
    action.parameters["image"] = "evil.example/image:latest"
    assert engine.evaluate(action, ctx).decision == Decision.DENY


def test_ci_policy():
    engine = PolicyEngine.from_yaml(ROOT / "policies/ci_code_change.yaml")
    action = Action(type="ci.propose_patch", target="example/ci-lab", parameters={"patch": "test patch"})
    for touches, expected in [(False, Decision.ALLOW), (True, Decision.DENY)]:
        ctx = Context(actor="ci-repair-agent", environment="lab", facts={
            "patch_verified": True, "touches_workflow": touches, "tests_passed": True,
        })
        assert engine.evaluate(action, ctx).decision == expected
