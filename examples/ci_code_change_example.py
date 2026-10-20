"""Offline CI integration with a host-owned context provider."""
from agent_policy_guard import Action, Context, GuardedExecutor, PolicyEngine

action = Action(
    type="ci.propose_patch", target="example/ci-lab",
    parameters={"patch": "simulated test-only patch"},
)
# Real hosts must compute these facts from this exact patch and repository state.
context = Context(
    actor="ci-repair-agent", environment="lab",
    facts={"patch_verified": True, "touches_workflow": False, "tests_passed": True},
)
events = []
guard = GuardedExecutor(
    PolicyEngine.from_yaml("policies/ci_code_change.yaml"),
    action_type="ci.propose_patch",
    executor=lambda approved, trusted: {"simulated_proposal": approved.parameters["patch"]},
    audit=events.append,
)
print(guard.execute(action, context))
assert [event["event"] for event in events] == ["authorization", "execution_returned"]
