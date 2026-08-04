import inspect
from typing import Any, Dict, List, Union, Optional
from yasin_core.compatibility.exceptions import APICompatibilityError


class APICompatibilityChecker:
    """
    Validates structural API compatibility of objects, modules, or classes.
    """

    @staticmethod
    def validate_method_signature(
        func: Any,
        expected_params: Optional[List[str]] = None,
        min_args: Optional[int] = None
    ) -> bool:
        """
        Validate if a callable has the expected parameter names or minimum argument count.
        """
        if not callable(func):
            return False

        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            # Skip self/cls for methods
            if params and params[0] in ("self", "cls"):
                params = params[1:]

            # Check expected specific parameter names
            if expected_params:
                for param in expected_params:
                    # Allow variable arguments or keyword arguments to satisfy parameter requirements
                    has_var_keyword = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD
                        for p in sig.parameters.values()
                    )
                    has_var_positional = any(
                        p.kind == inspect.Parameter.VAR_POSITIONAL
                        for p in sig.parameters.values()
                    )
                    if param not in params and not has_var_keyword and not has_var_positional:
                        return False

            # Check minimum arguments (excluding parameters with defaults, var_positional, var_keyword)
            if min_args is not None:
                required_params = [
                    p for p in sig.parameters.values()
                    if p.name not in ("self", "cls")
                    and p.default == inspect.Parameter.empty
                    and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                ]
                if len(required_params) > min_args:
                    return False

            return True
        except (ValueError, TypeError):
            # Built-ins or non-inspectable objects
            return True

    def check_compatibility(
        self,
        target: Any,
        expected_api: Dict[str, Any],
        raise_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Check if the target object matches the expected API structure.
        expected_api dictionary format:
        {
            "attribute_name": "attribute",  # Checks if attribute exists
            "method_name": ["arg1", "arg2"],  # Checks if method exists and has these arguments
            "another_method": {"params": ["x"], "min_args": 1}  # Detailed method check
        }

        Returns:
            Dict containing 'compatible' (bool), 'missing' (list of missing attributes/methods),
            and 'mismatched_signatures' (list of methods with incorrect signatures).
        """
        result = {
            "compatible": True,
            "missing": [],
            "mismatched_signatures": []
        }

        for member_name, spec in expected_api.items():
            if not hasattr(target, member_name):
                result["missing"].append(member_name)
                result["compatible"] = False
                continue

            member = getattr(target, member_name)

            if spec == "attribute":
                # Only need existence, which is satisfied by hasattr above.
                continue

            # Method check
            if not callable(member):
                result["mismatched_signatures"].append(f"{member_name} is not callable")
                result["compatible"] = False
                continue

            expected_params = None
            min_args = None

            if isinstance(spec, list):
                expected_params = spec
            elif isinstance(spec, dict):
                expected_params = spec.get("params")
                min_args = spec.get("min_args")

            if not self.validate_method_signature(member, expected_params, min_args):
                result["mismatched_signatures"].append(member_name)
                result["compatible"] = False

        if raise_on_error and not result["compatible"]:
            details = []
            if result["missing"]:
                details.append(f"Missing attributes/methods: {result['missing']}")
            if result["mismatched_signatures"]:
                details.append(f"Mismatched signatures: {result['mismatched_signatures']}")
            raise APICompatibilityError(f"API compatibility check failed: {'; '.join(details)}")

        return result
