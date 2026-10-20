from pathlib import Path
import yaml
from .models import Policy


class PolicyError(ValueError):
    pass


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in mapping:
            raise PolicyError("Policy keys must be unique strings")
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def load_policy(path: str | Path) -> Policy:
    try:
        data = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueSafeLoader)
        return Policy.model_validate(data)
    except (ValueError, TypeError, yaml.YAMLError, RecursionError) as exc:
        raise PolicyError("Invalid policy") from exc
