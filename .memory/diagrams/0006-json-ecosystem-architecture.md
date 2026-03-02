---
diagram: "0006"
title: "JSON Ecosystem Architecture"
format: "mermaid"
source_commits:
  - "de541e37ad3820033856cc8a0af55e896af55a3b"
  - "8eaefe04a044292e071263aca309b6991124c566"
  - "7cb92736b2ed95852ac71543937511acc7a3feec"
  - "55edee051c780af1831d7d04a40ddb8960ce01ed"
  - "1a271f00321b8cc16b72e58436716a05e2f62500"
related_designs:
  - ".memory/designs/0008-json-ecosystem.md"
  - ".memory/designs/0004-container-library.md"
  - ".memory/designs/0006-reflection-system.md"
---

# JSON Ecosystem Architecture

## Layer Diagram

```mermaid
graph TD
  subgraph "Cross-Language API (Global Functions)"
    G1["ffi.json.Parse"]
    G2["ffi.json.Stringify"]
    G3["ffi.ToJSONGraph"]
    G4["ffi.FromJSONGraph"]
    G5["ffi.ToJSONGraphString"]
    G6["ffi.FromJSONGraphString"]
  end

  subgraph "String Convenience Layer"
    S1["ToJSONGraphString(String) -> String"]
    S2["FromJSONGraphString(String) -> Any"]
  end

  subgraph "Object Graph Serialization Layer"
    OGS["ObjectGraphSerializer<br/>ToJSONGraph(Any) -> json::Value"]
    OGD["ObjectGraphDeserializer<br/>FromJSONGraph(json::Value) -> Any"]
  end

  subgraph "JSON Parser/Writer Layer"
    JP["json::Parse(String) -> json::Value"]
    JW["json::Stringify(json::Value) -> String"]
  end

  subgraph "FFI Type System (JSON DOM)"
    V["json::Value = Any"]
    O["json::Object = Map&lt;Any, Any&gt;"]
    A["json::Array = Array&lt;Any&gt;"]
  end

  subgraph "Reflection Infrastructure"
    OC["reflection::ObjectCreator<br/>Map&lt;String, Any&gt; -> Object"]
    FEF["ForEachFieldInfo<br/>(field traversal)"]
    TAC["TypeAttrColumn<br/>__data_to_json__<br/>__data_from_json__"]
    B64["Base64Encode / Base64Decode"]
  end

  G5 --> S1
  G6 --> S2
  S1 --> OGS
  S1 --> JW
  S2 --> JP
  S2 --> OGD
  G3 --> OGS
  G4 --> OGD
  G1 --> JP
  G2 --> JW
  OGS --> JW
  OGD --> JP
  OGS --> FEF
  OGS --> TAC
  OGD --> OC
  OGD --> TAC
  OGD --> B64
  OGS --> B64
  OGS --> V
  OGD --> V
  JP --> V
  JP --> O
  JP --> A
  JW --> V
  OC --> FEF
```

## JSON Parser Flow

```mermaid
flowchart TD
  A["json::Parse(str)"] --> B["JSONParserContext<br/>(character scanning)"]
  B --> C["JSONParser::ParseValue()"]
  C --> D{"First char?"}
  D -->|"{"| E["ParseObject() -> Map&lt;Any,Any&gt;"]
  D -->|"["| F["ParseArray() -> Array&lt;Any&gt;"]
  D -->|'"'| G["ParseString() -> String"]
  D -->|"digit/-"| H["ParseNumber() -> int64/double"]
  D -->|"t/f"| I["ParseBool() -> bool"]
  D -->|"n"| J["ParseNull() -> nullptr"]
  D -->|"I/N"| K["ParseInfNaN() -> Inf/NaN"]

  E --> L["Temp stack accumulate"]
  F --> L
  L --> M["Batch construct<br/>with exact size"]

  H --> N{"strtoimax OK?"}
  N -->|"Yes"| O["Return int64_t"]
  N -->|"No"| P["strtod fallback<br/>Return double"]
```

## Object Graph Serialization Format

```mermaid
graph LR
  subgraph "JSON Wire Format"
    ROOT["root_index: 0"]
    NODES["nodes: [...]"]
    META["metadata: {...}"]
  end

  subgraph "Node Types"
    N0["Node 0:<br/>type: 'MyObj'<br/>data: {x: 42, child: 1}"]
    N1["Node 1:<br/>type: 'ChildObj'<br/>data: {name: 'foo'}"]
    N2["Node 2:<br/>type: 'ffi.Shape'<br/>data: [2, 3, 4]"]
  end

  ROOT --> N0
  N0 -->|"child field<br/>index = 1"| N1
  N0 -.->|"Primitive field<br/>inlined"| I42["x: 42 (inline)"]
```

## Object Graph Deserialization Flow

```mermaid
flowchart TD
  A["FromJSONGraph(json)"] --> B["Read root_index"]
  B --> C["DecodeNode(root_index)"]
  C --> D{"Node decoded?"}
  D -->|"Yes (cached)"| E["Return cached"]
  D -->|"No"| F["Read node type key"]
  F --> G{"Has __data_from_json__<br/>hook?"}
  G -->|"Yes"| H["Call custom hook"]
  G -->|"No"| I["ObjectCreator(type_key)"]
  I --> J["ForEachFieldInfo"]
  J --> K{"Field is<br/>primitive?"}
  K -->|"Yes"| L["Read inline value"]
  K -->|"No"| M["Read index,<br/>DecodeNode(index)<br/>(recursive/lazy)"]
  L --> N["Set field"]
  M --> N
  N --> O["Return object"]
  H --> O
```

## Evidence

- JSON parser/writer: `src/ffi/extra/json_parser.cc`, `src/ffi/extra/json_writer.cc` @ `de541e3`
- JSON type aliases: `include/tvm/ffi/extra/json.h` @ `de541e3`
- Object graph serialization: `src/ffi/extra/serialization.cc`, `include/tvm/ffi/extra/serialization.h` @ `8eaefe0`
- ObjectCreator: `include/tvm/ffi/reflection/creator.h` @ `7cb9273`
- String convenience wrappers: `src/ffi/extra/serialization.cc` @ `55edee0`
- FastMath-safe helpers: `src/ffi/extra/json_parser.cc`, `src/ffi/extra/json_writer.cc` @ `1a271f0`
- TypeAttrColumn hooks: `src/ffi/extra/serialization.cc` @ `8eaefe0`
- Base64: `include/tvm/ffi/extra/base64.h` @ `8eaefe0`
