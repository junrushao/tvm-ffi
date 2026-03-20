---
status: "active"
confidence: "medium"
---
# FFI Kwargs Wrapper (Code-Generated Keyword Argument Support)

**TL;DR**.
- `tvm_ffi.utils.kwargs_wrapper` provides `make_kwargs_wrapper` and `make_kwargs_wrapper_from_signature`, which dynamically generate Python wrapper functions that add keyword-argument support to positional-only callables (such as FFI packed functions).
- Code generation uses `exec()` with a controlled namespace (same pattern as Python `dataclasses`). A `MISSING` sentinel distinguishes "not passed" from any real default value, and only `None`/`bool` literals are inlined into generated code -- all other defaults use runtime indirection.
- Parameter names are validated against Python keywords and duplicates. `exclude_arg_names` allows filtering parameters when generating from an `inspect.Signature`.

## Problem Statement
### Background
- FFI packed functions have a flat `(const AnyView* args, int32_t num_args, Any* rv)` calling convention. From Python, they accept only positional arguments. Users of these functions lose Python's keyword argument ergonomics and IDE support.
- Manually writing wrappers for each exported function is tedious and error-prone.

### Solution
- Generate wrapper functions at runtime via `exec()` that translate keyword arguments into positional calls to the underlying packed function.
- Default values are handled via a `MISSING` sentinel pattern: generated code checks `arg is MISSING` and substitutes the real default at call time. This avoids embedding arbitrary `repr()` in generated source code (a security and correctness concern).

### Goals
- Add keyword argument support to any positional-only callable with zero manual wrapper code.
- Safe code generation: no untrusted values embedded in generated source.
- Non-goal: handling `*args` or `**kwargs` parameters (explicitly rejected).

## Design

```python
# Module: tvm_ffi.utils.kwargs_wrapper

MISSING: object
# Invariant: identity comparison only (`is MISSING`), never equality
# Interacts with: generated wrapper code checks `arg is MISSING` at call time

def make_kwargs_wrapper(
    target_func: Callable,
    arg_names: list[str],
    arg_defaults: tuple = (),
    kwonly_names: list[str] | None = None,
    kwonly_defaults: dict[str, Any] | None = None,
    prototype: Callable | None = None,
) -> Callable: ...
    # Generates wrapper via exec() with controlled exec_globals:
    #   {"__i_target_func": target_func, "__i_MISSING": MISSING, "__i_args_defaults": defaults_dict}
    # Invariant: arg_names must be valid Python identifiers, not keywords, not duplicated
    # Invariant: arg_defaults are right-aligned to arg_names (matches __defaults__ behavior)
    # Invariant: kwonly_names must not overlap with arg_names
    # Invariant: only None and bool (exact type) are inlined as literals; all others use MISSING sentinel
    # Extension: prototype parameter copies __name__, __doc__ via functools.update_wrapper

def make_kwargs_wrapper_from_signature(
    target_func: Callable,
    signature: inspect.Signature,
    prototype: Callable | None = None,
    exclude_arg_names: Iterable[str] | None = None,
) -> Callable: ...
    # Extracts params from signature, filters exclude_arg_names, delegates to make_kwargs_wrapper
    # Invariant: rejects VAR_POSITIONAL (*args) and VAR_KEYWORD (**kwargs)
    # Extension: use exclude_arg_names to skip "self" or internal params

def _validate_argument_names(names: list[str], arg_type: str) -> None: ...
    # Invariant: rejects Python keywords (keyword.iskeyword) and invalid identifiers
    # Invariant: rejects duplicates
```

### Contracts, Assumptions and Invariants
- **No arbitrary repr in codegen**: Generated source never contains `repr(default_value)` for user-provided defaults. Only `None` and `bool` literals are safe to inline.
- **Reserved internal names**: `__i_target_func`, `__i_MISSING`, `__i_args_defaults` are reserved in the exec namespace. User arg names must not collide.
- **Right-aligned defaults**: `arg_defaults` tuple is aligned to the rightmost `arg_names`, matching Python's `__defaults__` semantics.

### Extension Points
- To add new "safe to inline" types beyond `None`/`bool`, extend the `_add_param_with_default` logic.
- The `MISSING` sentinel pattern is reusable in other code generation contexts (e.g., `py_class` `__init__` generation uses a similar approach).

### Usage Examples

#### Wrapping an FFI packed function with keyword args
**Context**: Add named parameters and defaults to a positional-only FFI function.
```python
from tvm_ffi.utils.kwargs_wrapper import make_kwargs_wrapper

# Positional-only FFI target
f_add = tvm_ffi.get_global_func("math.add")

wrapper = make_kwargs_wrapper(
    f_add,
    arg_names=["x", "y", "z"],
    arg_defaults=(10, 20),          # y=10, z=20
    kwonly_names=["debug"],
    kwonly_defaults={"debug": False},
)

wrapper(1)                   # -> f_add(1, 10, 20, False)
wrapper(1, y=5, debug=True)  # -> f_add(1, 5, 20, True)
```

#### Using exclude_arg_names with a signature
**Context**: Generate a wrapper from a prototype signature, excluding internal parameters.
```python
import inspect
from tvm_ffi.utils.kwargs_wrapper import make_kwargs_wrapper_from_signature

def prototype(a: int, b: int, c: int = 10) -> int:
    """Add numbers."""
    ...

wrapper = make_kwargs_wrapper_from_signature(
    target_func, inspect.signature(prototype),
    prototype=prototype,
    exclude_arg_names=["c"],
)
# wrapper accepts (a, b) with metadata from prototype
```

## Implementation Notes
- The generated function body is a string assembled from parameter descriptors. Each parameter is either a positional arg (with or without default) or a keyword-only arg.
- `functools.update_wrapper` propagates `__name__`, `__doc__`, `__module__`, and `__qualname__` from the prototype to the generated wrapper.
- A benchmark script is included for measuring the overhead of the generated wrapper vs direct positional calls.

## Alternatives & Trade-offs
### exec()-based codegen vs. closure-based wrapper
- Pros of exec: Generated functions have correct `inspect.signature()`, enabling IDE autocomplete and documentation tools. Matches stdlib `dataclasses` approach.
- Cons: Generated code is harder to debug. Mitigated by keeping generated bodies small and deterministic.
### Inline all defaults vs. MISSING sentinel
- Pros of MISSING: No risk of `repr()` producing invalid Python source or security issues. Works with unhashable/unrepr-able defaults.
- Cons: One extra `is MISSING` check per defaulted argument at call time. Negligible overhead.

## Evidence
| Commit | Scope | Contribution |
|--------|-------|-------------|
| 3115b237 | python/utils | Introduced `make_kwargs_wrapper` and `make_kwargs_wrapper_from_signature` |
| 6bc1a8eb | python/utils | Renamed parameters, added keyword validation, `exclude_arg_names` |

## Related Design Docs & ADRs
- [0016-python-dataclasses.md](0016-python-dataclasses.md) -- Uses the same `exec()` + sentinel pattern for `__init__` generation
- [0004-function-system.md](0004-function-system.md) -- Packed functions that kwargs_wrapper wraps
