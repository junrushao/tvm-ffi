# Any Access Semantics: as() vs try_cast() vs cast()

Source: commit `37a2e7c521435cbe2bd772480f0389c18bd9ce2c`
Related: [0002-any-system](../designs/0002-any-system.md), [ADR 0008](../ADRs/0008-as-strict-cast-lenient.md)

## Decision Flow for the Three Access Methods

```mermaid
flowchart TD
    subgraph "as&lt;T&gt;() -- STRICT, non-converting"
        A1["AnyView::as&lt;T&gt;()"] --> A2["TypeTraits&lt;T&gt;::CheckAnyStrict"]
        A2 -->|true| A3["CopyFromAnyViewAfterCheck -> optional&lt;T&gt;"]
        A2 -->|false| A4["return nullopt"]
    end

    subgraph "try_cast&lt;T&gt;() -- LENIENT, converting"
        B1["AnyView::try_cast&lt;T&gt;()"] --> B2["TypeTraits&lt;T&gt;::TryCastFromAnyView"]
        B2 --> B3{"Fast path: CheckAnyStrict?"}
        B3 -->|true| B4["return value"]
        B3 -->|false| B5{"Coercion possible?"}
        B5 -->|"e.g. int->float"| B6["Convert and return optional&lt;T&gt;"]
        B5 -->|"no path"| B7["return nullopt"]
    end

    subgraph "cast&lt;T&gt;() -- LENIENT + THROW"
        C1["AnyView::cast&lt;T&gt;()"] --> C2["try_cast&lt;T&gt;()"]
        C2 -->|value| C3["return T"]
        C2 -->|nullopt| C4["throw TypeError"]
    end
```

## TypeTraits Method Mapping

```mermaid
graph LR
    subgraph "User-Facing Methods"
        AS["as&lt;T&gt;()"]
        TC["try_cast&lt;T&gt;()"]
        CA["cast&lt;T&gt;()"]
    end

    subgraph "TypeTraits&lt;T&gt; Protocol"
        CAS["CheckAnyStrict"]
        CFAV["CopyFromAnyViewAfterCheck"]
        MFAA["MoveFromAnyAfterCheck"]
        TCA["TryCastFromAnyView"]
    end

    AS -->|"check"| CAS
    AS -->|"extract"| CFAV
    AS -->|"extract (rvalue)"| MFAA
    TC -->|"convert"| TCA
    CA -->|"convert"| TCA
```

## Behavioral Examples

```mermaid
graph TD
    subgraph "AnyView holding int(42)"
        E1["as&lt;int&gt;() -> 42"] --- E1a["CheckAnyStrict: kTVMFFIInt == kTVMFFIInt -> true"]
        E2["as&lt;float&gt;() -> nullopt"] --- E2a["CheckAnyStrict: kTVMFFIInt != kTVMFFIFloat -> false"]
        E3["try_cast&lt;float&gt;() -> 42.0"] --- E3a["TryCastFromAnyView: int->float coercion"]
        E4["cast&lt;float&gt;() -> 42.0"] --- E4a["Same as try_cast but throws on failure"]
        E5["as&lt;bool&gt;() -> nullopt"] --- E5a["CheckAnyStrict: kTVMFFIInt != kTVMFFIBool"]
        E6["try_cast&lt;bool&gt;() -> true"] --- E6a["TryCastFromAnyView: int->bool coercion"]
    end
```
