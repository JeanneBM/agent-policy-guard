import hashlib
import json
from .models import Action, Context, Decision, Policy, PolicyResult
from .loaders import load_policy


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def exact_equal(left, right):
    # JSON comparison distinguishes true from 1, including in nested containers.
    return canonical(left) == canonical(right)


_MISSING = object()


def resolve(document, path):
    value = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


class PolicyEngine:
    def __init__(self, policy: Policy | dict):
        validated = Policy.model_validate(
            policy.model_dump() if isinstance(policy, Policy) else policy
        )
        # Keep a canonical immutable snapshot; caller mutations cannot alter policy.
        self._policy_json = canonical(validated.model_dump(mode="json"))
        self.policy_hash = hashlib.sha256(self._policy_json.encode()).hexdigest()

    @classmethod
    def from_yaml(cls, path):
        return cls(load_policy(path))

    def evaluate(self, action: Action, context: Context) -> PolicyResult:
        policy = Policy.model_validate_json(self._policy_json)
        document = {
            "action": action.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
        }
        matched = []
        for rule in policy.rules:
            matches = True
            for condition in rule.conditions:
                actual = resolve(document, condition.field)
                if actual is _MISSING:
                    matches = False
                    break
                if condition.op == "eq":
                    ok = exact_equal(actual, condition.value)
                else:
                    ok = any(exact_equal(actual, item) for item in condition.value)
                if not ok:
                    matches = False
                    break
            if matches:
                matched.append(rule)
        priority = {"deny": 0, "require_human": 1, "escalate": 2, "allow": 3}
        winner = min(matched, key=lambda r: (priority[r.decision], r.id)) if matched else None
        return PolicyResult(
            decision=Decision(winner.decision) if winner else Decision.DENY,
            reason=winner.reason if winner else "No matching rule; denied by default",
            policy_id=policy.id,
            policy_version=policy.version,
            policy_hash=self.policy_hash,
            request_hash=digest(document),
            matched_rules=tuple(sorted(r.id for r in matched)),
        )
