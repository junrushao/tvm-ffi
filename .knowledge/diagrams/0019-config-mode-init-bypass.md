# Config-Mode Import Bypass Flow

Source: commits `5c0deb9` (#489, skip imports in config mode), `bad3896` (#490, Windows config loading fix)
Related: [0014-python-bindings](../designs/0014-python-bindings.md), [0016-packaging-and-build](../designs/0016-packaging-and-build.md)

## Package Initialization with Config-Mode Detection

```mermaid
flowchart TD
    IMPORT["import tvm_ffi"]
    IMPORT --> DETECT["_is_config_mode()"]

    subgraph "_is_config_mode() Detection"
        DETECT --> ARGV0{"sys.argv[0].endswith\n('tvm-ffi-config')?"}
        ARGV0 -->|"yes"| CONFIG_TRUE["return True"]
        ARGV0 -->|"no"| ORIG{"sys.orig_argv\navailable? (3.10+)"}
        ORIG -->|"no"| CONFIG_FALSE["return False"]
        ORIG -->|"yes"| DASH_M{"-m tvm_ffi.config\nin orig_argv?"}
        DASH_M -->|"yes"| CONFIG_TRUE
        DASH_M -->|"no"| CONFIG_FALSE
    end

    CONFIG_FALSE --> NORMAL_PATH["Normal import path"]
    CONFIG_TRUE --> CONFIG_PATH["Config-mode path"]

    subgraph "Normal Import Path"
        NORMAL_PATH --> TORCH_HACK["try: import torch\n(Windows symbol conflict workaround)"]
        TORCH_HACK --> LOAD_LIB["libinfo.load_lib_ctypes\n('apache-tvm-ffi', 'tvm_ffi', 'RTLD_GLOBAL')"]
        LOAD_LIB --> REGISTRY["from .registry import\nregister_object, get_global_func, ..."]
        REGISTRY --> CORE["from .core import Object, Function, ..."]
        CORE --> CONTAINERS["from .container import Array, Dict, ..."]
        CONTAINERS --> EXTRAS["from .module, .stream, .structural,\n.serialization, .dataclasses, .cpp, ..."]
        EXTRAS --> DTYPES["from ._dtype import bool, int8, float32, ..."]
    end

    subgraph "Config-Mode Path"
        CONFIG_PATH --> WIN{"sys.platform\n.startswith('win32')?"}
        WIN -->|"yes (Windows)"| WIN_LOAD["from . import libinfo\nLIB = libinfo.load_lib_ctypes(...)"]
        WIN -->|"no (Unix/macOS)"| NO_LOAD["Skip all imports\n(no native library loaded)"]
    end

    WIN_LOAD --> VERSION["try: from ._version import __version__"]
    NO_LOAD --> VERSION

    DTYPES --> VERSION

    style NORMAL_PATH fill:#c8e6c9
    style CONFIG_PATH fill:#fff3e0
    style WIN_LOAD fill:#ffcdd2
    style NO_LOAD fill:#e1f5fe
```

## Rationale

The `tvm-ffi-config` CLI (`python -m tvm_ffi.config`) only needs path discovery functions from `libinfo.py` (`find_lib_path`, `find_include_path`, etc.). Loading the full C++ shared library, Cython extension, and registering all object types is unnecessary overhead. On CI systems or cross-compilation environments, the native library may not even be available for the host platform.

The Windows exception exists because DLL search path resolution on Windows requires the native library to be loaded via `ctypes.CDLL` before any Cython extension (`.pyd` file) can be imported, even indirectly. Some test configurations trigger Cython imports even during config queries, so the library must be loaded preemptively.
