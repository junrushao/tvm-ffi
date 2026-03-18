---
scope: "any-system"
---
# API Index: Any/AnyView System

**Scope**: C++ type-erased value containers (Any, AnyView) and related utilities.
**Design docs**: [0003-any-system.md](../designs/0003-any-system.md)
**ADRs**: [0001-unified-any-object-abi.md](../ADRs/0001-unified-any-object-abi.md)

## C++ API: Types, Methods, Functions, Macros
| Name | Kind | Key Fields / Methods | Description |
|------|------|---------------------|-------------|
| `AnyView` | class | `type_index() -> int32`, `cast<T>() -> T`, `as<T>() -> Optional<T>` (strict), `try_cast<T>() -> Optional<T>` (conversion), `CopyFromTVMFFIAny(src) -> AnyView` | Non-owning 16-byte type-erased value reference (layout == TVMFFIAny) |
| `Any` | class | `cast<T>() -> T` (lvalue and rvalue), `as<T>() -> Optional<T>` (strict), `try_cast<T>() -> Optional<T>` (conversion), `reset() -> void`, assignment operators | Owning 16-byte type-erased value (layout == TVMFFIAny, auto-promotes RawStr to String) |
| `PackedArgs` | class | `int size()`, `const AnyView* data()`, `AnyView operator[](int)`, `Slice(begin, end) -> PackedArgs`, `Fill(AnyView*, args...)` | Wrapper over AnyView array for function arguments |
| `AnyHash` | struct | `uint64_t operator()(const Any&)` | String-aware hash with per-type custom dispatch via `__any_hash__` TypeAttrColumn (39d9b2b) |
| `AnyEqual` | struct | `bool operator()(const Any&, const Any&)` | String-aware equality with per-type custom dispatch via `__any_equal__` TypeAttrColumn (39d9b2b) |
