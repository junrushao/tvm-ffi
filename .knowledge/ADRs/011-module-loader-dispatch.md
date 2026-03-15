---
scope:
  - ".knowledge/designs/0013-module-system.md"
---
# String-Keyed Global Function Dispatch for Module Loading

**TL;DR**:
- Module loading uses string-keyed global function dispatch (`ffi.Module.load_from_file.<ext>` and `ffi.Module.load_from_bytes.<kind>`) rather than a fixed enum, vtable, or factory registration pattern.
- This allows new module formats to be supported by registering a single global function, with zero changes to the Module class or core library.

## Context
When loading modules from files or binary blobs, the system must dispatch to the correct loader implementation based on the file format or serialization kind. The set of supported formats is open-ended: DSO (`.so`), CUDA (`.cu`), LLVM bitcode, custom accelerator formats, etc. New formats may come from third-party libraries or plugins that are not part of the core build.

Usecases:
- Loading a compiled `.so` model file at runtime: `Module::LoadFromFile("model.so")` must find and invoke the DSO loader.
- Deserializing a CUDA module from binary data embedded in a library binary: `ffi.Module.load_from_bytes.cuda` must find the CUDA deserializer.
- A third-party plugin registers a custom module format (e.g., `ffi.Module.load_from_file.tflite`) at static init time, without modifying any core code.

Design Decisions:
- Module loading dispatches through the global function registry by constructing a key from a prefix + format string.
- The `Module::LoadFromFile` function normalizes the file extension (`dll`/`dylib`/`dso` -> `so`) and looks up `ffi.Module.load_from_file.<format>`.
- Binary deserialization looks up `ffi.Module.load_from_bytes.<kind>`.
- Loader registration happens in `TVM_FFI_STATIC_INIT_BLOCK` via `reflection::GlobalDef().def(...)`.

## Alternatives

### Alternative A: Fixed Enum of Loaders
- Description: Define an enum `ModuleFormat { kDSO, kCUDA, kOpenCL, ... }` and switch on it in `LoadFromFile`.
- Pros: Compile-time exhaustiveness checking; IDE autocomplete; marginally faster dispatch (no string hash).
- Cons: Adding a new format requires modifying the enum and the switch statement in the core library. Third-party formats cannot be added without forking or patching the core. This violates the open-closed principle.
- Why rejected: The set of module formats is inherently open-ended. Requiring core library changes for every new format is unacceptable for an extensible FFI system.

### Alternative B: Virtual Factory Method on a Format Registry Object
- Description: Define a `ModuleLoader` interface with `virtual Module Load(String path)`, and maintain a `Map<String, ModuleLoader*>` registry.
- Pros: Type-safe; standard OOP factory pattern; each loader is a proper object.
- Cons: Introduces a new class hierarchy just for loading. The global function registry already provides exactly this pattern (string -> callable). Adding a separate registry duplicates infrastructure, and the two registries (function and loader) could drift out of sync. Callers would need to know about `ModuleLoader` instead of just calling a function.
- Why rejected: The global function registry already solves this problem. Using it for loaders maintains a single, well-understood dispatch mechanism and avoids introducing a parallel registration system.

## Implementation Notes
- `Module::LoadFromFile` normalizes extensions: `dll`, `dylib`, `dso` all become `so`. The canonical loader for shared libraries is `ffi.Module.load_from_file.so`.
- The DSO loader is registered as:
  ```cpp
  refl::GlobalDef().def("ffi.Module.load_from_file.so", [](String library_path, String) {
    return CreateLibraryModule(make_object<DSOLibrary>(library_path));
  });
  ```
- Error messages are explicit about the expected loader key, so users can diagnose missing loaders:
  ```
  Loader for `.xyz` files is not registered, resolved to (ffi.Module.load_from_file.xyz)
  ```
- The `ffi.Module.load_from_bytes.<kind>` convention is used by `ProcessLibraryBin` to deserialize sub-modules from the binary module format.

## Related Design Docs
- `.knowledge/designs/0013-module-system.md` -- Full module system design
- `.knowledge/designs/function-system.md` -- Global function registry used for dispatch
