---
sha: "0daaffedd23982ea09f8c38fec4eef1cca1d8cac"
date: "2025-08-19T18:58:19-04:00"
author: "Tianqi Chen"
subject: "[FFI][REFACTOR] Establish Stream Context in ffi (#18216)"
nature: ["feat"]
tags: ["stream", "device", "extra-api"]
scope: ["include/tvm/ffi/extra", "src/ffi/extra", "CMakeLists.txt"]
risk: "low"
---

# 0daaffe — [FFI][REFACTOR] Establish Stream Context in ffi (#18216)

## TL;DR
- Introduces a thread-local stream context (`StreamContext`) in the FFI layer for tracking per-device streams.
- Adds `TVMFFIEnvSetStream` and `TVMFFIEnvGetCurrentStream` C API functions in `c_env_api.h`.
- Migrates per-device stream management from the runtime layer into the FFI env API.

## Why (intent / motivation)
- Centralizes stream context management in the FFI layer so that FFI functions can be compatible with stream-based executions (e.g., CUDA streams) across different runtimes without per-device API dependencies.

## What changed (facts from diff)
- `include/tvm/ffi/extra/c_env_api.h`: Added `TVMFFIStreamHandle` typedef and declarations for `TVMFFIEnvSetStream` / `TVMFFIEnvGetCurrentStream`.
- `src/ffi/extra/stream_context.cc` (new): `StreamContext` class with `SetStream`, `GetStream`, thread-local singleton. C API wrappers `TVMFFIEnvSetStream` / `TVMFFIEnvGetCurrentStream` using `TVM_FFI_SAFE_CALL_BEGIN/END`.
- `CMakeLists.txt`: Added `stream_context.cc` to extra sources.

## Public surface changes (if any)
- API: New C API functions `TVMFFIEnvSetStream(device_type, device_id, stream, opt_out_original)` and `TVMFFIEnvGetCurrentStream(device_type, device_id)`.
- Flags/config: Requires `TVM_FFI_USE_EXTRA_CXX_API=ON`.
- Data formats/schemas: none

## Tests & verification
- Added/updated tests: none
- How to verify manually: Call `TVMFFIEnvSetStream` / `TVMFFIEnvGetCurrentStream` from C++ or via Python bindings.
- CI impact: New extra source file; no existing test changes.

## Risk & rollout notes
- Risk level: low — Additive change; no existing behavior modified.
- Rollout/migration: none
- Follow-ups: Python bindings for stream context; integration with torch stream context (see commit 6014406).

## Evidence
### Changed files
- `CMakeLists.txt` +1/-0 (M)
- `include/tvm/ffi/extra/c_env_api.h` +33/-0 (M)
- `src/ffi/extra/stream_context.cc` +81/-0 (A)

### Notable symbols / endpoints / configs touched
- `TVMFFIStreamHandle` (typedef)
- `TVMFFIEnvSetStream`, `TVMFFIEnvGetCurrentStream`
- `StreamContext::ThreadLocal()`, `StreamContext::SetStream()`, `StreamContext::GetStream()`

### Diff notes
- Diff truncated: no

### Knowledge links
- Per-commit file: `.repo-knowledge/commits/0daaffedd23982ea09f8c38fec4eef1cca1d8cac.md`
