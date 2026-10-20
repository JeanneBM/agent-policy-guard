"""Offline integration example; no cluster credentials or mutations."""
from agent_policy_guard import Action, Context, PolicyEngine, GuardedExecutor, JsonlAudit

action = Action(
    type="k8s.image_update",
    target="test-app/deployment/test-app",
    parameters={
        "container": "test-app",
        "current_image": "lab.azurecr.io/tset-app:1.4.2",
        "image": "lab.azurecr.io/test-app:1.4.2",
    },
)
context = Context(
    actor="diagnostic-agent", environment="lab",
    facts={"image_exists": True, "observed_image": action.parameters["current_image"]},
)
guard = GuardedExecutor(
    PolicyEngine.from_yaml("policies/k8s_image_repair.yaml"),
    action_type="k8s.image_update",
    executor=lambda approved, trusted: {"simulated_image": approved.parameters["image"]},
    audit=JsonlAudit(".local/audit.jsonl"),
)
print(guard.execute(action, context))
