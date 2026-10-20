"""Dependency-free node callable, suitable for registering in a LangGraph graph.

The trusted application constructs the node and binds its context provider.
The graph state contains the untrusted proposal only.
"""
from agent_policy_guard import Action, GuardedExecutor


def make_guarded_node(engine, trusted_context_provider, executor, audit):
    guard = GuardedExecutor(
        engine, action_type="ci.propose_patch", executor=executor, audit=audit
    )

    def node(state):
        proposal = Action.model_validate(state["proposal"])
        context = trusted_context_provider(proposal)
        return {"execution_result": guard.execute(proposal, context)}

    return node
