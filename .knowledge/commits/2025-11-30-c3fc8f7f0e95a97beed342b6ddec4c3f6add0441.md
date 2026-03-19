---
author: "DarkSharpness"
subject: "Add STL interop header for vanilla C++ containers in FFI"
commit_shape: "standard"
commit_type: "feature"
potential_duplicate: ""
has_design_updates: false
scope:
  - "ffi/extra"
---
# Add STL interop header for vanilla C++ containers in FFI

## TL;DR
- Adds `include/tvm/ffi/extra/stl.h` (649 LOC) providing automatic conversion between C++ STL containers (std::vector, std::map, std::tuple, std::string, std::optional) and FFI types
- Includes Python test coverage via inline C++ compilation

## Key Exports
```python
# include/tvm/ffi/extra/stl.h
# Provides TypeTraits specializations for:
# std::vector<T> <-> Array<T>
# std::map<K,V> <-> Map<K,V>
# std::tuple<T...> <-> Tuple<T...>
# std::string <-> String
# std::optional<T> <-> Optional<T>
# Interacts with: TypeTraits (0005), Containers (0006)
```

## Impact
- API: New STL<->FFI automatic conversions
- Behavioral: None
- Flags/config: None
- Data formats/schemas: None

## Design Elements
Design elements this commit consumes:
- TypeTraits protocol (`0005-type-traits-protocol`)
- Containers (`0006-containers`): Array, Map, Tuple, String

Design elements this commit produces:
- STL interop layer in `extra/stl.h`

## Usage Examples
```cpp
#include <tvm/ffi/extra/stl.h>
std::vector<int> v = {1, 2, 3};
Any any_v(v);  // auto-converts to Array
std::vector<int> back = any_v.cast<std::vector<int>>();
```

## Reflection

### Design docs to write or update
None

### Stale knowledge references
None
