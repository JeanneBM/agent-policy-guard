from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"
    REQUIRE_HUMAN = "require_human"


class Action(StrictModel):
    type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class Context(StrictModel):
    """Constructed by the trusted host, never accepted directly from an LLM."""
    actor: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    facts: dict[str, JsonValue] = Field(default_factory=dict)


class Condition(StrictModel):
    field: str = Field(pattern=r"^(action\.(type|target|parameters\.[a-zA-Z0-9_.]+)|context\.(actor|environment|facts\.[a-zA-Z0-9_.]+))$")
    op: Literal["eq", "in"]
    value: JsonValue

    @model_validator(mode="after")
    def validate_operand(self):
        if self.op == "in" and (not isinstance(self.value, list) or not self.value):
            raise ValueError("'in' requires a nonempty list")
        return self


class Rule(StrictModel):
    id: str = Field(min_length=1)
    decision: Literal["allow", "deny", "escalate", "require_human"]
    reason: str = Field(min_length=1)
    conditions: list[Condition] = Field(min_length=1)


class Policy(StrictModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("Rule IDs must be unique")
        return self


class PolicyResult(StrictModel):
    decision: Decision
    reason: str
    policy_id: str
    policy_version: str
    policy_hash: str
    request_hash: str
    matched_rules: tuple[str, ...]
