# Inline Module Compilation Flow

Source: commit `83805ec949227620d05e61358a4ecb4f0c931979`
Updated by: `825aeb9` (API rename), `2df07e5` (Windows), `4ffbc88` (macOS)
Related: [0017-inline-module-compilation](../designs/0017-inline-module-compilation.md), [0013-module-system](../designs/0013-module-system.md), [0008-module-export-system](../designs/0008-module-export-system.md)

## End-to-End Pipeline

```mermaid
flowchart TD
    A["tvm_ffi.cpp.load_inline(\n  name='my_ext',\n  cpp_sources='...',\n  functions=['add_one'],\n  build_directory=None\n)"] --> BD{"build_directory\nprovided?"}
    BD -->|"Yes"| BDIR["Use build_directory directly"]
    BD -->|"No"| B["_hash_sources()\nSHA-256 of all inputs"]
    B --> C["Cache dir:\n~/.cache/tvm-ffi/my_ext_a1b2c3d4/"]
    BDIR --> D
    C --> D{"Output .so/.dll\nexists?"}
    D -->|"Cache hit"| M["load_module(output_path)"]
    D -->|"Cache miss"| E["_decorate_with_tvm_ffi()"]
    E --> F["Prepend FFI headers:\n#include <tvm/ffi/function.h>\n#include <tvm/ffi/error.h>\n..."]
    F --> G["Append export macros:\nTVM_FFI_DLL_EXPORT_TYPED_FUNC(\n  add_one, add_one)"]
    G --> H["_maybe_write()\nmain.cpp, build.ninja"]
    H --> I["FileLock.acquire()\n(serialize builds)"]
    I --> J["_build_ninja()\nsubprocess: ninja -j$MAX_JOBS"]
    J --> K["FileLock.release()"]
    K --> M
    M --> N["Module\n(attribute-style access:\nmod.add_one(...))"]

    style D fill:#f9f,stroke:#333
    style M fill:#9f9,stroke:#333
```

## Source Decoration Detail

```mermaid
flowchart LR
    subgraph "User Source"
        US["void add_one(\n  ffi::Tensor x,\n  ffi::Tensor y) {\n  ...\n}"]
    end
    subgraph "Decorated Source (main.cpp)"
        DS["#include <tvm/ffi/function.h>\n#include <tvm/ffi/error.h>\n#include <tvm/ffi/dtype.h>\n#include <tvm/ffi/extra/c_env_api.h>\n\n// User source\nvoid add_one(...) { ... }\n\n// Auto-generated export\nTVM_FFI_DLL_EXPORT_TYPED_FUNC(\n  add_one, add_one)"]
    end
    US --> DS
```

## Ninja Build Structure (Platform-Aware)

```mermaid
flowchart TD
    subgraph "build.ninja (Unix)"
        R1U["rule compile_cpp\n  depfile = $out.d\n  deps = gcc\n  command = $CXX -std=c++17 -fPIC\n    -I{include} -I{dlpack}\n    -MMD -MF $out.d\n    -c $in -o $out"]
        R3U["rule link\n  command = $CXX -shared\n    -L{lib_path} -ltvm_ffi\n    $in -o $out"]
        B1U["build main.o: compile_cpp main.cpp"]
        B3U["build my_ext.so: link main.o"]
    end

    subgraph "build.ninja (Windows/MSVC)"
        R1W["rule compile_cpp\n  deps = msvc\n  command = cl /std:c++17 /MD /EHsc\n    /wd4190 /wd4005\n    /showIncludes\n    /I{include} /I{dlpack}\n    /c $in /Fo$out"]
        R3W["rule link\n  command = link.exe /DLL\n    $in /link $ldflags\n    /LIBPATH:{lib_path} tvm_ffi.lib\n    /out:$out"]
        B1W["build main.obj: compile_cpp main.cpp"]
        B3W["build my_ext.dll: link main.obj"]
    end
```

## Cache Directory Layout

```
~/.cache/tvm-ffi/
    my_ext_a1b2c3d4e5f6g7h8/
        main.cpp          # Decorated source
        cuda.cu           # CUDA source (if any)
        build.ninja       # Ninja build file
        my_ext.so         # Compiled output (Linux)
        my_ext.dylib      # Compiled output (macOS)
        my_ext.dll        # Compiled output (Windows)
        .lock             # FileLock file
```
