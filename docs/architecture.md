# Architecture and integration contract

## Execution path

1. An untrusted agent proposes an Action.
2. The trusted host validates the domain-specific action schema and gathers facts
   for that exact proposal from authenticated systems.
3. PolicyEngine evaluates an immutable policy snapshot and the request.
4. GuardedExecutor emits the authorization event and blocks every non-allow result.
5. The bound executor uses the approved snapshot and checks current external state.
6. The host independently verifies the outcome and records domain evidence.

The policy hash covers canonical parsed policy JSON. The request hash covers action
and context. Decision results contain no timestamps, so equal inputs and policies
produce equal results. Audit events add timestamps and unique IDs separately.

## Kubernetes integration

The sample uses fictitious registry names. Adapt exact image references and the
target to the real lab. Verify registry existence and observed deployment image
using trusted clients; never accept these facts from the diagnostic model.

A real executor must parse the target, allow only the intended container/image
fields, reject extra parameters, and use resourceVersion or JSON Patch tests to
prevent overwriting a concurrently changed deployment. Bind a least-privilege
Workload Identity to that executor. Read-only diagnostic identity stays separate.
Then verify rollout and record evidence. This repository does not provision Azure.

## CI / LangGraph integration

The node factory in examples/langgraph_integration.py takes a trusted context
provider and bound executor. Register the returned callable as a graph node.
Do not pass identity or verification booleans through model-controlled graph state.

The provider must inspect every changed path, reject traversal, inspect workflows,
run required checks against the exact patch/base SHA, and bind that evidence to the
proposal. The executor must enforce that base SHA, create only the reviewed
proposal, and avoid shell interpretation of generated strings. The offline example
does not implement those external checks or open PRs.

## Security properties and limits

The evaluator is deterministic for canonical JSON inputs. Policies fail validation
on unknown fields rather than silently ignoring conditions. All conditions are AND;
matching decisions combine by restrictive precedence. Unknown actions have no
implicit allow.

This is a host integration library, not an isolation boundary against hostile
Python code, a sandbox, an identity provider or a remote authorization service.
The executor and audit sink are trusted code. Missing or false evidence cannot
enable the provided allow rules; fabricated evidence supplied by a compromised
host can.

Mutable external state can change after evaluation. Revalidation, conditional
updates, least privilege, idempotency and outcome verification belong in the
host/executor. Audit output is local and mutable. Human review decisions remain
blocked until a separately designed approval flow exists.

## Verification

The CI workflow installs the package on Python 3.11, 3.12 and 3.13, runs pytest,
and runs both offline integration examples. Tests cover default deny, rule
precedence, missing facts, boolean/number confusion, invalid policies, duplicate
YAML keys, snapshot isolation, executor binding, non-allow blocking, audit
failures, executor failures and both example policies.
