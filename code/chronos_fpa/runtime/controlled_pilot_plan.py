"""Explicit, subset-only execution schedules for the frozen pilot protocol."""
import math

GROUP_FIELDS = ("seed", "dataset_name", "series_id", "window_id", "branch_step")


def group_identity(group):
    return tuple(group[name] for name in GROUP_FIELDS)


def selected_groups(config, execution_plan=None):
    original = [dict(seed=seed, dataset_name=case["dataset_name"], series_id=case["series_id"],
                     window_id=case["window_id"], branch_step=step)
                for seed in config["seeds"] for case in config["cases"] for step in case["branch_steps"]]
    if execution_plan is None:
        return original
    if set(execution_plan) != {"version", "reason", "max_wall_seconds", "groups"} or execution_plan["version"] != 1:
        raise ValueError("Unsupported execution plan; only group selection and time budget may change")
    budget = execution_plan["max_wall_seconds"]
    if isinstance(budget, bool) or not isinstance(budget, (float, int)) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("Execution plan needs a positive finite wall-clock budget")
    if not execution_plan["reason"] or not execution_plan["groups"]:
        raise ValueError("Execution plan needs a reason and at least one selected group")
    if any(set(group) != set(GROUP_FIELDS) for group in execution_plan["groups"]):
        raise ValueError("Execution groups must specify exact identifiers, not scientific overrides")
    keys = [group_identity(group) for group in execution_plan["groups"]]
    if len(keys) != len(set(keys)) or not set(keys).issubset({group_identity(group) for group in original}):
        raise ValueError("Execution groups must be a unique subset of the original pilot")
    return execution_plan["groups"]
