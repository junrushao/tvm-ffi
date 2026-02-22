# ADR 014: Keep Dynamically Loaded Modules Alive by Default

- Status: Accepted
- Date: 2025-12-11
- Owners: Junru Shao

## Context

Dynamically loaded modules (`.so` / `.dll`) hold destructors in their own
code. When Python's garbage collector unloads a module before all objects
referencing it are freed, the destructors call into already-unmapped memory,
causing segfaults (issues #264, #322).

Prior workarounds included forcing `gc.collect()` before releasing module
references (`79894c3`), but this was fragile and required manual user
intervention. Additionally, metadata strings allocated inside extension
modules (`dcacb98`) suffered the same use-after-unload problem.

## Decision

`load_module` gained a `keep_module_alive: bool = True` parameter
(`8dcaec1`). When `True` (the default), the loaded module is registered in
a C++-side `ModuleGlobals` singleton inside `libtvm_ffi.so`, preventing
Python from unloading the library while the process runs.

Key implementation details:
- `ModuleGlobals` is a thread-safe `Map<Module, int>` singleton in
  `src/ffi/extra/module.cc` with `Add`/`Remove` methods.
- Global functions `ffi.ModuleGlobalsAdd` and `ffi.ModuleGlobalsRemove`
  are registered for Python access.
- `cpp.load_inline` and `cpp.load` forward the parameter.
- Users who need explicit unloading can pass `keep_module_alive=False`.

Metadata string allocation was also moved to `libtvm_ffi` (`dcacb98`) using
`TVMFFIStringFromByteArray`, ensuring strings remain valid after module
unloading.

## Consequences

- Positive: Segfaults from module unloading are eliminated by default;
  no user-side workarounds needed; safe-by-default behavior.
- Negative: Modules kept alive consume memory for the process lifetime;
  opt-out requires passing `keep_module_alive=False`.
- Migration/Rollout: Default behavior is safe for all existing callers.
  Callers that relied on module unloading on Python GC must explicitly
  set `keep_module_alive=False`.

## References

- Range summary: `.repo-knowledge/ranges/2025-12-29-5A82940-6E7CAFA.md`
- Evidence commits: `8dcaec1`, `79894c3`, `dcacb98`

## Related Design Docs

- `.repo-knowledge/design/007-module-system.md`
- `.repo-knowledge/design/008-python-packaging.md`
