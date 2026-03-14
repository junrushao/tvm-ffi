# ObjectRef Construction Paths (Post-UnsafeInit)

Source: commit `472e10c4086e91fb788ffe1f0eee10df4bcf5db2`
Related: [0003-object-system](../designs/0003-object-system.md), [ADR 0028](../ADRs/0028-unsafeinit-tag-replaces-objectptr-object-ctor.md)

## How to Construct an ObjectRef Subclass

```mermaid
flowchart TD
    START["Need to create a Foo<br/>(where Foo : ObjectRef)"] --> Q1{"Do you have<br/>typed ObjectPtr<FooObj>?"}
    Q1 -->|"Yes"| P1["Foo foo(typed_ptr);<br/>// Direct typed construction<br/>// Only for nullable types"]
    Q1 -->|"No"| Q2{"Do you have<br/>untyped ObjectPtr<Object>?"}
    Q2 -->|"Yes"| P2["auto foo = ObjectUnsafe::<br/>ObjectRefFromObjectPtr<Foo>(ptr);<br/>// Centralized unsafe helper<br/>// Auditable via grep"]
    Q2 -->|"No"| Q3{"Creating fresh<br/>from scratch?"}
    Q3 -->|"Yes"| P3["auto ptr = make_object<FooObj>(args...);<br/>Foo foo(ptr);<br/>// Standard allocation + typed construction"]
    Q3 -->|"No"| Q4{"Reflection-based<br/>construction?"}
    Q4 -->|"Yes"| P4["metadata->creator() creates<br/>via ObjectCreatorDefault<T><br/>or ObjectCreatorUnsafeInit<T>"]
    Q4 -->|"No"| P5["Factory method<br/>(e.g., Shape::StridesFromShape)"]

    style P2 fill:#ff9,stroke:#333
    style P4 fill:#ff9,stroke:#333
```

## Constructor Matrix After UnsafeInit

```mermaid
graph LR
    subgraph "Nullable Types (_type_is_nullable = true)"
        N1["T(ObjectPtr<ContainerType>)<br/>-- typed, safe"]
        N2["explicit T(UnsafeInit)<br/>-- for internal/unsafe use"]
    end
    subgraph "Non-Nullable Types (_type_is_nullable = false)"
        NN1["explicit T(UnsafeInit)<br/>-- only constructor available"]
    end
    subgraph "Removed (was in all types)"
        R1["T(ObjectPtr<Object>)<br/>-- REMOVED: bypassed type checks"]
    end

    style R1 fill:#fcc,stroke:#333
```

## Reflection Creator Resolution

```mermaid
flowchart TD
    A["ObjectDef<T> constructor"] --> B{"std::is_default_constructible_v<T>?"}
    B -->|"Yes"| C["Register ObjectCreatorDefault<T>"]
    B -->|"No"| D{"std::is_constructible_v<T, UnsafeInit>?"}
    D -->|"Yes"| E["Register ObjectCreatorUnsafeInit<T>"]
    D -->|"No"| F["No creator registered<br/>(type cannot be reflection-constructed)"]
```
