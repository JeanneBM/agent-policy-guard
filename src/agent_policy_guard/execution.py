from uuid import uuid4
from .models import Action, Context, Decision


class AuthorizationDenied(PermissionError):
    def __init__(self, result):
        self.result = result
        super().__init__(result.reason)


class GuardedExecutor:
    """Trusted host binds a single executor to a single action type."""
    def __init__(self, engine, *, action_type: str, executor, audit):
        self.engine = engine
        self.action_type = action_type
        self.executor = executor
        self.audit = audit

    def execute(self, action: Action, context: Context):
        # Serialize/revalidate to detach nested mutable dictionaries from caller.
        action = Action.model_validate_json(action.model_dump_json())
        context = Context.model_validate_json(context.model_dump_json())
        result = self.engine.evaluate(action, context)
        execution_id = str(uuid4())
        common = {
            "execution_id": execution_id,
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
            "policy_hash": result.policy_hash,
            "request_hash": result.request_hash,
            "decision": result.decision.value,
            "matched_rules": list(result.matched_rules),
        }
        binding_ok = action.type == self.action_type
        # Audit errors propagate before any side effect.
        self.audit({**common, "event": "authorization", "binding_ok": binding_ok})
        if result.decision != Decision.ALLOW:
            raise AuthorizationDenied(result)
        if not binding_ok:
            raise PermissionError("Executor action type mismatch")
        try:
            output = self.executor(action, context)
        except Exception:
            self.audit({**common, "event": "execution_failed"})
            raise
        # A sink failure here does not imply rollback of the external operation.
        self.audit({**common, "event": "execution_returned"})
        return output
