---
author: "DarkSharpness"
subject: "Add dynamic-style method overloading for FFI object types"
commit_shape: "standard"
commit_type: "feature"
potential_duplicate: ""
has_design_updates: false
scope:
  - "ffi/function"
  - "ffi/reflection"
---
# Add dynamic-style method overloading for FFI object types

## TL;DR
- Adds `include/tvm/ffi/reflection/overload.h` (501 LOC) for runtime method dispatch based on argument types
- Supports overloaded methods on FFI objects with automatic dispatch
- Adds comprehensive C++ test coverage (95 LOC)

## Key Exports
```python
# include/tvm/ffi/reflection/overload.h
class OverloadSet:
    """Runtime method overload set with type-based dispatch.
    # Interacts with: ObjectDef (0008), Function (0003)
    # Extension: add overloads via OverloadSet::add(signature, impl)
    """
    def dispatch(self, *args) -> Any: ...

# Registration:
# ObjectDef<T>().def_method_overload("name", typed_func1, typed_func2, ...)
```

## Impact
- API: New method overloading support for FFI objects
- Behavioral: None
- Flags/config: None
- Data formats/schemas: None

## Design Elements
Design elements this commit consumes:
- Function system (`0003-function-system`)
- Reflection (`0008-reflection`): ObjectDef

Design elements this commit produces:
- `OverloadSet` runtime dispatch for method overloading
- `reflection/overload.h` header

## Usage Examples
```cpp
ObjectDef<MyObj>()
  .def_method_overload("process",
    Function::FromTyped([](MyObj* self, int x) { ... }),
    Function::FromTyped([](MyObj* self, String s) { ... }));
```

## Reflection

### Design docs to write or update
None

### Stale knowledge references
None
