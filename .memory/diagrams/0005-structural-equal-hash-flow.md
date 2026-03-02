---
diagram: "0005"
title: "Structural Equal and Hash Dispatch Flow"
format: "mermaid"
source_commits:
  - "9445fe734839cffc8bdf881788528b7763f7be03"
  - "59a837eb4040843051706cbf5c7b71725fd65364"
  - "3fc0391e29dac100ad37db45348090438e1db739"
  - "f4ede982f00257881d9ba7fe82dd8abc07e14690"
related_designs:
  - ".memory/designs/0007-structural-equal-hash-system.md"
  - ".memory/designs/0006-reflection-system.md"
---

# Structural Equal and Hash Dispatch Flow

## Structural Equal Dispatch

```mermaid
flowchart TD
  A["StructuralEqual::Equal(lhs, rhs)"] --> B{"Same pointer?"}
  B -->|Yes| C["Return true"]
  B -->|No| D{"Same type_index?"}
  D -->|No| E["Return false"]
  D -->|Yes| F{"SEqHashKind?"}

  F -->|UniqueInstance| G["Return lhs == rhs<br/>(pointer equality)"]
  F -->|Unsupported| H["Throw TypeError"]
  F -->|FreeVar| I["Check/update<br/>equal_map_ bijection"]
  F -->|DAGNode| J{"Already compared<br/>this pair?"}
  J -->|Yes| K["Return true"]
  J -->|No| L["Field-by-field or custom"]
  F -->|TreeNode| L
  F -->|ConstTreeNode| L

  L --> M{"Has __s_equal__<br/>in TypeAttrColumn?"}
  M -->|Yes| N["Call custom callback<br/>with cmp function"]
  M -->|No| O["ForEachFieldInfo<br/>field-by-field compare"]

  O --> P{"Field has<br/>SEqHashIgnore?"}
  P -->|Yes| Q["Skip field"]
  P -->|No| R{"Field has<br/>SEqHashDef?"}
  R -->|Yes| S["Set map_free_vars=true<br/>then compare field"]
  R -->|No| T["Compare field<br/>recursively"]

  N --> U["Post-process:<br/>FreeVar/DAG mapping"]
  T --> U
  S --> U
  Q --> U
  U --> V["Return result"]
```

## Structural Hash Dispatch

```mermaid
flowchart TD
  A["StructuralHash::Hash(value)"] --> B{"type_index?"}
  B -->|POD int/float/bool| C["StableHashCombine<br/>with type key + value"]
  B -->|String/Bytes| D["StableHashBytes<br/>(small or heap)"]
  B -->|Object| E{"SEqHashKind?"}

  E -->|UniqueInstance| F["Hash pointer address"]
  E -->|Unsupported| G["Throw TypeError"]
  E -->|FreeVar| H["Assign FreeVar<br/>counter index, hash it"]
  E -->|DAGNode| I{"Already hashed?"}
  I -->|Yes| J["Hash DAG counter"]
  I -->|No| K["Field-by-field or custom"]
  E -->|TreeNode| K
  E -->|ConstTreeNode| K

  K --> L{"Has __s_hash__<br/>in TypeAttrColumn?"}
  L -->|Yes| M["Call custom callback<br/>with hash function"]
  L -->|No| N["ForEachFieldInfo<br/>hash each field"]

  N --> O{"SEqHashIgnore?"}
  O -->|Yes| P["Skip field"]
  O -->|No| Q{"SEqHashDef?"}
  Q -->|Yes| R["Set map_free_vars=true<br/>hash field"]
  Q -->|No| S["Hash field<br/>recursively"]

  C --> T["Return hash"]
  D --> T
  F --> T
  M --> T
  S --> T
  R --> T
  P --> T
  H --> T
  J --> T
```

## AccessPath Mismatch Tracking

```mermaid
flowchart LR
  subgraph "Parent-pointing tree"
    Root["Root<br/>depth=0"]
    A1["Attr('body')<br/>depth=1"]
    A2["ArrayItem(0)<br/>depth=2"]
    A3["Attr('value')<br/>depth=3"]
    A3 -->|parent| A2
    A2 -->|parent| A1
    A1 -->|parent| Root
  end

  subgraph "Flattened path"
    P[".body[0].value"]
  end

  A3 -->|ToSteps| P
```

## SEqHashKind Taxonomy

```mermaid
graph TD
  subgraph "TVMFFISEqHashKind values"
    U["Unsupported (0)<br/>Throws TypeError"]
    TN["TreeNode (1)<br/>Field-by-field comparison"]
    FV["FreeVar (2)<br/>Identity-mapped variable"]
    DN["DAGNode (3)<br/>Shared subexpression"]
    CT["ConstTreeNode (4)<br/>Always compare by content"]
    UI["UniqueInstance (5)<br/>Pointer equality only"]
  end

  TN -.->|"may have custom<br/>__s_equal__/__s_hash__"| CA["TypeAttrColumn<br/>custom callbacks"]
```

## Evidence

- StructuralEqual dispatch: `src/ffi/extra/structural_equal.cc` @ `9445fe7`, `59a837e`
- StructuralHash dispatch: `src/ffi/extra/structural_hash.cc` @ `9445fe7`, `59a837e`
- AccessPath/AccessStep: `include/tvm/ffi/reflection/access_path.h` @ `9445fe7`, `3fc0391`
- AccessPathObj parent-pointing tree redesign: `include/tvm/ffi/reflection/access_path.h` @ `f4ede98`
- TVMFFISEqHashKind enum: `include/tvm/ffi/c_api.h` @ `9445fe7`, `59a837e`
- TypeAttrColumn custom dispatch: `src/ffi/extra/structural_equal.cc` @ `2ec11f5`, `59a837e`
- Field flags (SEqHashIgnore, SEqHashDef): `include/tvm/ffi/reflection/registry.h` @ `9445fe7`
