---
diagram: "0008"
title: "Python Package Architecture"
format: "mermaid"
source_commits:
  - "2d41a5115f6a91e2781012a3379f9626bc9e18a1"
related_designs:
  - ".memory/designs/0010-python-packaging-architecture.md"
  - ".memory/designs/0011-cython-binding-layer.md"
---

# Python Package Architecture

## Package Build Pipeline

```mermaid
flowchart TD
  A["pip install -e ."] --> B["scikit-build-core<br/>(PEP 517 backend)"]
  B --> C["CMake configure<br/>-DTVM_FFI_BUILD_PYTHON_MODULE=ON"]
  C --> D["Compile C++ sources<br/>tvm_ffi_objs (OBJECT library)"]
  C --> E["Cython transpile<br/>core.pyx -> core.cpp"]
  D --> F["Link: libtvm_ffi.{so,dylib,dll}<br/>(tvm_ffi_shared)"]
  E --> G["Compile core.cpp<br/>Link against tvm_ffi_objs"]
  G --> H["core.cpython-*.so<br/>(SABI abi3 if Python>=3.12)"]
  F --> I["Install to wheel/site-packages"]
  H --> I
  I --> J["setuptools-scm<br/>writes _version.py"]
```

## Package Layout (installed)

```mermaid
flowchart LR
  subgraph "site-packages/tvm_ffi/"
    direction TB
    A["__init__.py<br/>(loads libtvm_ffi, imports all modules)"]
    B["core.cpython-312-*.so<br/>(Cython extension)"]
    C["libtvm_ffi.so<br/>(C++ shared library)"]
    D["libinfo.py<br/>(library/path discovery)"]
    E["config.py<br/>(tvm-ffi-config CLI)"]
    F["registry.py, container.py,<br/>module.py, ndarray.py, etc."]
    G["cython/<br/>(source .pxi files)"]
    H["include/<br/>(C++ headers)"]
    I["share/cmake/<br/>(tvm_ffi-config.cmake)"]
  end
```

## Import and Initialization Sequence

```mermaid
sequenceDiagram
  participant User as User Code
  participant Init as tvm_ffi.__init__
  participant LibInfo as libinfo.py
  participant CTypes as ctypes.CDLL
  participant Core as core.cpython-*.so
  participant Registry as registry.py

  User->>Init: import tvm_ffi
  Note over Init: Try import torch first<br/>(Windows symbol conflict workaround)
  Init->>LibInfo: load_lib_ctypes("apache-tvm-ffi", "tvm_ffi", "RTLD_GLOBAL")
  LibInfo->>LibInfo: importlib.metadata.distribution("apache-tvm-ffi")<br/>Parse RECORD for library path
  LibInfo->>CTypes: ctypes.CDLL(path, RTLD_GLOBAL)
  CTypes-->>Init: LIB (loaded shared library)
  Init->>Core: from .core import Object, Function
  Note over Core: Cython extension loads<br/>C symbols from RTLD_GLOBAL
  Init->>Registry: from .registry import register_object, ...
  Init->>Init: Import all other modules<br/>(container, module, ndarray, dtype, error, ...)
  Init-->>User: tvm_ffi module ready
```

## Downstream C++ Integration Flow

```mermaid
flowchart TD
  A["Downstream CMakeLists.txt"] --> B["find_package(Python COMPONENTS Interpreter)"]
  B --> C["execute_process:<br/>python -m tvm_ffi.config --cmakedir"]
  C --> D["Set tvm_ffi_ROOT"]
  D --> E["find_package(tvm_ffi CONFIG REQUIRED)"]
  E --> F["tvm_ffi-config.cmake loaded"]
  F --> G["python -m tvm_ffi.config<br/>--includedir --dlpack-includedir --libfiles"]
  G --> H["Create tvm_ffi::header<br/>(INTERFACE IMPORTED)"]
  G --> I["Create tvm_ffi::shared<br/>(SHARED IMPORTED)"]
  H --> J["target_link_libraries(mylib tvm_ffi::header)"]
  I --> K["target_link_libraries(mylib tvm_ffi::shared)"]
```

## Library Discovery Strategy (libinfo.py)

```mermaid
flowchart TD
  A["find_libtvm_ffi()"] --> B["importlib.metadata.distribution('apache-tvm-ffi')"]
  B --> C["Parse RECORD file"]
  C --> D{"lib{tvm_ffi}.{so,dylib}<br/>found in RECORD?"}
  D -->|Yes| E["Return resolved path"]
  D -->|No| F["Fallback: filesystem search"]
  F --> G["Check PROJECT_ROOT/build/lib"]
  F --> H["Check PROJECT_ROOT/lib"]
  F --> I["Check LD_LIBRARY_PATH / DYLD_LIBRARY_PATH / PATH"]
  G --> J{"File exists?"}
  H --> J
  I --> J
  J -->|Yes| E
  J -->|No| K["RuntimeError: Cannot find libtvm_ffi"]
```

## Dual CMake Mode

```mermaid
flowchart TD
  A["CMakeLists.txt entered"] --> B["Define unconditional targets:<br/>tvm_ffi_header, tvm_ffi_objs,<br/>tvm_ffi_shared, tvm_ffi_static"]
  B --> C{"PROJECT_NAME ==<br/>CMAKE_PROJECT_NAME?"}
  C -->|No: Subproject| D["return()<br/>Only library targets visible"]
  C -->|Yes: Root project| E["Define root-only options:<br/>TVM_FFI_BUILD_TESTS<br/>TVM_FFI_BUILD_PYTHON_MODULE<br/>TVM_FFI_ATTACH_DEBUG_SYMBOLS"]
  E --> F{"TVM_FFI_BUILD_TESTS?"}
  F -->|Yes| G["Add GoogleTest targets"]
  F -->|No| H{"TVM_FFI_BUILD_PYTHON_MODULE?"}
  H -->|Yes| I["Find Python, run Cython,<br/>build core extension,<br/>add install rules"]
  H -->|No| J["Done"]
```

## Evidence

- `pyproject.toml` (scikit-build-core config): `pyproject.toml` @ `2d41a51`
- `__init__.py` (initialization): `python/tvm_ffi/__init__.py` @ `2d41a51`
- `libinfo.py` (library discovery): `python/tvm_ffi/libinfo.py` @ `2d41a51`
- `config.py` (CLI): `python/tvm_ffi/config.py` @ `2d41a51`
- `tvm_ffi-config.cmake`: `cmake/tvm_ffi-config.cmake` @ `2d41a51`
- `CMakeLists.txt` (dual mode): `CMakeLists.txt` @ `2d41a51`
- `Library.cmake` (tvm_ffi_ prefix): `cmake/Utils/Library.cmake` @ `2d41a51`
