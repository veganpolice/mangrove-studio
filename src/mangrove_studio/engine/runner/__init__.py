"""Calculation runner — evaluates node trees with real data.

Given a node tree (from the generator or YAML) and a data context mapping
DPT slugs to values, evaluates the tree bottom-up and returns results.
"""

import re
from simpleeval import simple_eval

# Standard operators recognized by keyword
STANDARD_OPERATORS = {"summation", "product", "quotient", "difference", "average", "max", "min", "count"}


class RunContext:
    """Holds input data and collects calculated outputs during a run."""

    def __init__(self, data: dict[str, float | list[float]]):
        """Initialize with a data context mapping DPT slugs to values.

        Values can be:
        - float: a single value (static inputs, constants)
        - list[float]: per-event values (event data points)
        """
        self.data = dict(data)
        self.outputs: dict[str, float] = {}

    def resolve(self, slug: str, aggregate: bool = True) -> float | list[float]:
        """Resolve a DPT slug to its value(s).

        If aggregate is True and the value is a list, returns the sum.
        If aggregate is False, returns the raw value (list or scalar).
        """
        if slug in self.outputs:
            return self.outputs[slug]
        if slug not in self.data:
            raise ValueError(f"Data point '{slug}' not found in context")
        value = self.data[slug]
        if isinstance(value, list) and aggregate:
            return sum(value)
        return value


def evaluate_node(node: dict, ctx: RunContext) -> float | list[float]:
    """Evaluate a single node in the tree, recursively evaluating children first.

    Returns the computed value (float or list of floats for per-event).
    """
    children = node.get("nexus_nodes_attributes", [])
    operator = node.get("operator")
    dpt = node.get("data_point_type")
    constant = node.get("constant")
    should_agg = node.get("should_aggregate", True)

    # Leaf node with constant value
    if constant is not None and not children:
        return float(constant)

    # Leaf node with data point reference (no children, no operator or simple lookup)
    if dpt and not children and not operator:
        return ctx.resolve(dpt, aggregate=should_agg)

    # Leaf with data point and a keisan expression but no children
    # e.g., operator: "1 - fuel-moisture-content-"
    if dpt and operator and operator not in STANDARD_OPERATORS and not children:
        result = _evaluate_keisan(operator, ctx)
        if dpt:
            ctx.outputs[dpt] = result
        return result

    # Evaluate children (ordered by 'order' field if present)
    sorted_children = sorted(children, key=lambda c: c.get("order", 0))
    child_values = [evaluate_node(child, ctx) for child in sorted_children]

    if not operator:
        # No operator — return first child or sum
        result = child_values[0] if len(child_values) == 1 else sum(_as_float(v) for v in child_values)
    elif operator == "summation":
        result = _op_summation(child_values, should_agg)
    elif operator == "product":
        result = _op_product(child_values, should_agg)
    elif operator == "quotient":
        result = _op_quotient(child_values)
    elif operator == "difference":
        result = _op_difference(child_values)
    elif operator == "average":
        flat = [_as_float(v) for v in child_values]
        result = sum(flat) / len(flat) if flat else 0.0
    elif operator == "max":
        result = max(_as_float(v) for v in child_values)
    elif operator == "min":
        result = min(_as_float(v) for v in child_values)
    elif operator == "count":
        result = float(len(child_values))
    else:
        # Keisan expression — evaluate with child DPT slugs as variables
        result = _evaluate_keisan_with_children(operator, child_values, sorted_children, ctx)

    # Store output if this node has a data_point_type
    result_float = _as_float(result)
    if dpt:
        ctx.outputs[dpt] = result_float

    return result_float


def _as_float(value: float | list[float]) -> float:
    """Convert a value to float, summing lists."""
    if isinstance(value, list):
        return sum(value)
    return float(value)


def _op_summation(values: list, should_agg: bool) -> float | list[float]:
    """Sum operator — handles both scalar and per-event values."""
    # If any value is a list (per-event), we need to handle the sumproduct pattern
    has_lists = any(isinstance(v, list) for v in values)

    if not has_lists:
        return sum(float(v) for v in values)

    if should_agg:
        # Sum all values (aggregate lists first)
        return sum(_as_float(v) for v in values)

    # Per-event: if we have lists, sum element-wise across children
    # This handles the case where multiple per-event children are summed
    max_len = max(len(v) if isinstance(v, list) else 1 for v in values)
    result = []
    for i in range(max_len):
        total = 0.0
        for v in values:
            if isinstance(v, list):
                total += v[i] if i < len(v) else 0.0
            else:
                total += float(v)
        result.append(total)
    return result


def _op_product(values: list, should_agg: bool) -> float | list[float]:
    """Product operator — multiply children together.

    For the sumproduct pattern: if should_aggregate is not True and children
    are per-event lists, multiply element-wise (then the parent summation sums).
    """
    has_lists = any(isinstance(v, list) for v in values)

    if not has_lists:
        result = 1.0
        for v in values:
            result *= float(v)
        return result

    if not should_agg:
        # Per-event product: multiply element-wise
        max_len = max(len(v) if isinstance(v, list) else 1 for v in values)
        result = []
        for i in range(max_len):
            prod = 1.0
            for v in values:
                if isinstance(v, list):
                    prod *= v[i] if i < len(v) else 1.0
                else:
                    prod *= float(v)
            result.append(prod)
        return result

    # Default: aggregate lists then multiply
    result = 1.0
    for v in values:
        result *= _as_float(v)
    return result


def _op_quotient(values: list) -> float:
    """Quotient — divide first child by second (ordered by 'order' field)."""
    if len(values) < 2:
        raise ValueError("Quotient requires at least 2 children")
    numerator = _as_float(values[0])
    denominator = _as_float(values[1])
    if denominator == 0:
        raise ValueError("Division by zero in quotient")
    return numerator / denominator


def _op_difference(values: list) -> float:
    """Difference — subtract children[1:] from children[0]."""
    if not values:
        return 0.0
    result = _as_float(values[0])
    for v in values[1:]:
        result -= _as_float(v)
    return result


def _evaluate_keisan(expression: str, ctx: RunContext) -> float:
    """Evaluate a keisan expression, resolving DPT slugs from context."""
    # Find all slug-like references in the expression
    # Slugs are lowercase with hyphens: e.g., fuel-moisture-content-
    names = {}
    sanitized = expression

    # Find all slug-like tokens (sequences of word chars and hyphens that look like slugs)
    slug_pattern = r'[a-z][a-z0-9-]*[a-z0-9-]'
    potential_slugs = re.findall(slug_pattern, expression)

    for slug in potential_slugs:
        if slug in ctx.data or slug in ctx.outputs:
            safe_name = slug.replace("-", "_")
            names[safe_name] = _as_float(ctx.resolve(slug))
            sanitized = sanitized.replace(slug, safe_name)

    return simple_eval(sanitized, names=names)


def _evaluate_keisan_with_children(
    expression: str,
    child_values: list,
    children: list[dict],
    ctx: RunContext,
) -> float:
    """Evaluate a keisan expression using child node values as variables."""
    names = {}
    sanitized = expression

    # Map child DPT slugs to their computed values
    for child, value in zip(children, child_values):
        slug = child.get("data_point_type", "")
        if slug:
            safe_name = slug.replace("-", "_")
            names[safe_name] = _as_float(value)
            sanitized = sanitized.replace(slug, safe_name)

    # Also resolve any other slug references from context
    slug_pattern = r'[a-z][a-z0-9-]*[a-z0-9-]'
    for slug in re.findall(slug_pattern, sanitized):
        safe_name = slug.replace("-", "_")
        if safe_name not in names:
            if slug in ctx.data or slug in ctx.outputs:
                names[safe_name] = _as_float(ctx.resolve(slug))
                sanitized = sanitized.replace(slug, safe_name)

    return simple_eval(sanitized, names=names)


def run_model(node_tree: dict, data: dict[str, float | list[float]]) -> dict[str, float]:
    """Run a complete model, returning all calculated outputs.

    Args:
        node_tree: The model's nexus_nodes_attributes dict
            (e.g., {"nexus_nodes_attributes": [...]})
        data: Input data mapping DPT slugs to values

    Returns:
        Dict of calculated DPT slugs to their computed values
    """
    ctx = RunContext(data)
    roots = node_tree.get("nexus_nodes_attributes", [])
    for root in roots:
        evaluate_node(root, ctx)
    return ctx.outputs
