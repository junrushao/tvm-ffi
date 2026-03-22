# Skill /commit-ledger - Self-Evolution
- **Procedure friction**: Step 3.3 (breaking changes) required careful reading of removal of `ImportFromExternDLL` and `FunctionObj::call` — the "public header signature changes" check is the right trigger but doesn't explicitly mention removal of non-virtual member functions as a distinct breaking category worth surfacing.
- **Template gap**: The Impact section lacks a dedicated "ABI binary compatibility" row distinct from "API". This commit changes `TVMFFIFunctionCell` (a C struct) in a way that requires recompilation but not source changes — there's no clean place to document this vs. a source-level API break.
- **Wasted effort**: None — all steps contributed.
- **Suggested skill change**: Add an "ABI compatibility" row in the Impact section template alongside "API", specifically for changes to C structs, enum values, or vtable layouts that break binary but not source compatibility.
