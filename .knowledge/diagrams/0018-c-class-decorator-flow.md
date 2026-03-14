# @c_class Decorator and Init Wiring Flow

Source: commits `e5f3af7` (#488, c_class reimplementation), `b1abaea` (#486, __ffi_init__ wiring)
Related: [0014-python-bindings](../designs/0014-python-bindings.md), [0027-dataclass-operations](../designs/0027-dataclass-operations.md), [ADR 0069](../ADRs/0069-c-class-as-register-object-plus-dunders.md)

## @c_class Decorator Two-Phase Flow

```mermaid
flowchart TD
    DEC["@c_class(type_key, init=True, repr=True,\neq=False, order=False, unsafe_hash=False)"]
    DEC --> PHASE1["Phase 1: register_object(type_key)(cls)"]

    subgraph "register_object"
        PHASE1 --> TI_LOOKUP["core._object_type_key_to_index(type_key)"]
        TI_LOOKUP --> REG["core._register_object_by_index(type_index, cls)"]
        REG --> ATTRS["_add_class_attrs(cls, type_info)"]
        ATTRS --> FIELDS["Set field properties\n(FieldGetter/FieldSetter)"]
        ATTRS --> METHODS["Set method callables\n(__c_ffi_init__, __ffi_shallow_copy__, etc.)"]
        METHODS --> SET_TI["cls.__tvm_ffi_type_info__ = type_info"]
        SET_TI --> COPY["_setup_copy_methods\n(__copy__, __deepcopy__, __replace__)"]
    end

    COPY --> PHASE2["Phase 2: _install_dataclass_dunders(cls)"]

    subgraph "_install_dataclass_dunders"
        PHASE2 --> INIT{"init=True?"}
        INIT -->|"yes"| INSTALL_INIT["_install_init(cls, enabled=True)"]
        INIT -->|"no"| INSTALL_GUARD["_install_init(cls, enabled=False)\n(TypeError guard)"]

        INSTALL_INIT --> REPR{"repr=True?"}
        INSTALL_GUARD --> REPR

        REPR -->|"yes"| SET_REPR["cls.__repr__ = object_repr\n(C++ ReprPrint)"]
        REPR -->|"no"| EQ_CHECK

        SET_REPR --> EQ_CHECK{"eq=True?"}
        EQ_CHECK -->|"yes"| SET_EQ["cls.__eq__ = RecursiveEq wrapper\ncls.__ne__ = not RecursiveEq wrapper"]
        EQ_CHECK -->|"no"| HASH_CHECK

        SET_EQ --> HASH_CHECK{"unsafe_hash=True?"}
        HASH_CHECK -->|"yes"| SET_HASH["cls.__hash__ = RecursiveHash wrapper"]
        HASH_CHECK -->|"no"| ORDER_CHECK

        SET_HASH --> ORDER_CHECK{"order=True?"}
        ORDER_CHECK -->|"yes"| SET_ORDER["cls.__lt__ = RecursiveLt wrapper\ncls.__le__ = RecursiveLe wrapper\ncls.__gt__ = RecursiveGt wrapper\ncls.__ge__ = RecursiveGe wrapper"]
        ORDER_CHECK -->|"no"| DONE["Return cls"]
        SET_ORDER --> DONE
    end

    style PHASE1 fill:#e1f5fe
    style PHASE2 fill:#fff3e0
```

## __ffi_init__ to Python __init__ Wiring

```mermaid
flowchart TD
    INSTALL["_install_init(cls, enabled)"]
    INSTALL --> DICT{"'__init__' in\ncls.__dict__?"}
    DICT -->|"yes"| SKIP["Skip (user-defined\n__init__ preserved)"]
    DICT -->|"no"| TI{"type_info\navailable?"}
    TI -->|"no"| SKIP2["Skip (no reflection)"]
    TI -->|"yes"| ENABLED{"enabled?"}

    ENABLED -->|"yes"| FFI_INIT{"__ffi_init__ method\nin type_info.methods?"}
    FFI_INIT -->|"yes"| AUTO{"auto_init=True\nin metadata?"}
    FFI_INIT -->|"no"| PYNATIVE{"PyNativeObject\nsubclass?"}

    AUTO -->|"yes"| SYNTH["_make_init(cls, type_info)\nSynthesize __init__ with\ninspect.Signature"]
    AUTO -->|"no"| RAW["cls.__init__ = cls.__ffi_init__\n(expose raw C++ init)"]

    PYNATIVE -->|"yes"| SKIP3["Skip (PyNativeObject\nhandles init differently)"]
    PYNATIVE -->|"no"| GUARD_MISS["Install TypeError guard:\n'no __ffi_init__ registered'"]

    ENABLED -->|"no"| GUARD_OFF["Install TypeError guard:\n'cannot be constructed directly'"]

    style SYNTH fill:#c8e6c9
    style RAW fill:#c8e6c9
    style GUARD_MISS fill:#ffcdd2
    style GUARD_OFF fill:#ffcdd2
```

## _make_init Signature Synthesis

```mermaid
flowchart TD
    MAKE["_make_init_signature(type_info)"]
    MAKE --> CHAIN["Walk parent chain\n(parent-first order)"]
    CHAIN --> COLLECT["Collect all fields\nfrom ancestors"]
    COLLECT --> FILTER{"field.c_init?"}
    FILTER -->|"no (Init=false)"| SKIP["Skip field"]
    FILTER -->|"yes"| KW{"field.c_kw_only?"}
    KW -->|"yes"| KW_LIST["Add to kw_only list\nwith has_default flag"]
    KW -->|"no"| POS_LIST["Add to positional list\nwith has_default flag"]

    POS_LIST --> PARTITION_POS["Partition positional:\nrequired first, optional second"]
    KW_LIST --> PARTITION_KW["Partition kw_only:\nrequired first, optional second"]

    PARTITION_POS --> BUILD["Build inspect.Signature:\nself, pos_required, pos_optional,\nkw_required, kw_optional"]
    PARTITION_KW --> BUILD

    BUILD --> INIT_FN["__init__(self, *args, **kwargs):\n  ffi_args = list(args)\n  ffi_args.append(KWARGS_SENTINEL)\n  for k,v in kwargs: ffi_args += [k, v]\n  self.__ffi_init__(*ffi_args)"]
```

## Comparison Dunder Guard Logic

```mermaid
flowchart TD
    CALL["obj1.__eq__(obj2)"]
    CALL --> CHECK["_is_comparable(self, other)"]
    CHECK --> BI{"isinstance(other, type(self))\nor isinstance(self, type(other))?"}
    BI -->|"no"| NI["return NotImplemented"]
    BI -->|"yes"| CMP["return _ffi_api.RecursiveEq(self, other)"]

    style NI fill:#fff9c4
    style CMP fill:#c8e6c9
```
