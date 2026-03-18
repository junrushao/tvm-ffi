---
scope:
  - "0011-module-system.md"
---
# ADR: Module as a Static Object Type (kTVMFFIModule = 73)

**TL;DR**: Decision to assign Module a fixed static type index (`73`) in the `[64, 75)` range rather than a dynamic type index (`>= 128`), making it a first-class FFI type with stable cross-DLL identity.

## Context
- Compiled code in loaded shared libraries needs to interact with `Module` objects at runtime: looking up imported functions, registering symbols, and checking module properties.
- Generated code hardcodes C ABI calls like `TVMFFIEnvModLookupFromImports(library_ctx, ...)` where `library_ctx` is a `ModuleObj*`. The runtime must recognize this as a Module without relying on dynamic type index allocation, which varies between compilation units and processes.
- All other first-class FFI types (String=65, Function=68, Shape=69, Tensor=70, Array=71, Map=72, OpaquePyObject=74) use static type indices in `[64, 75)`. Module is architecturally at the same level -- it is a fundamental FFI building block, not a user-defined type.

Usecases:
- Cross-DLL module loading: `Module::LoadFromFile("model.so")` returns a Module with `type_index = 73` that is recognizable by any code linked against the FFI headers.
- AOT compilation: System libraries register symbols at static init time via `TVMFFIEnvModRegisterSystemLibSymbol`, and the runtime creates `SystemLibrary`-backed `Module` objects with a known type index.
- Type checking in generated code: `type_index == kTVMFFIModule` is a single integer comparison, O(1).

Design Decisions:
- **Use static type index `73`** via `TVM_FFI_DECLARE_OBJECT_INFO_STATIC(StaticTypeKey::kTVMFFIModule, ModuleObj, Object)` instead of `TVM_FFI_DECLARE_OBJECT_INFO_FINAL` (which would allocate a dynamic index `>= 128`). Macro names updated in a08fa6e.
- **Place in the static object range `[64, 75)`**: This is the designated range for built-in types. Module occupies slot 73, followed by `kTVMFFIOpaquePyObject = 74`. The gap `[75, 128)` provides room for future static types.
- **Module is `_type_final = true`**: No subclassing of `ModuleObj` through the type system (concrete module variants like `LibraryModuleObj` use C++ inheritance but share the same type index).

## Implementation Notes
- `StaticTypeKey::kTVMFFIModule` constant added to `object.h`, used by `ModuleObj::_type_key = "ffi.Module"`.
- `Module` uses `TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE` since modules are mutable (`_type_mutable = true` on `ModuleObj`) and non-nullable. Mutability is now a property of the Obj class, not the ref macro choice (a08fa6e).
- C ABI entry points in `c_env_api.h` use the `TVMFFIEnvMod` prefix to distinguish module-scoped operations from global environment operations.

## Related Design Docs
- [0011-module-system.md](../designs/0011-module-system.md)
- [0001-c-abi.md](../designs/0001-c-abi.md)
- [0002-object-system.md](../designs/0002-object-system.md)
