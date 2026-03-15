---
status: "active"
confidence: "high"
---
# Any/AnyView System Design

**TL;DR**:
- `Any` and `AnyView` are 16-byte type-erased value wrappers around `TVMFFIAny`. `AnyView` is non-owning; `Any` is owning (ref-counted for objects).
- Three distinct access methods: `as<T>()` (strict, no conversion), `cast<T>()` (conversion, throws), `try_cast<T>()` (conversion, returns optional).
- Both `tvm::ffi::Any`/`tvm::ffi::AnyView` and the convenience aliases `tvm::Any`/`tvm::AnyView` are available.

## Problem Statement
### Background
- The FFI needs a universal type-erased container for function arguments and return values that holds both POD values (int, float, bool, DLDevice, DLDataType) and reference-counted object pointers.
- The `TVMFFIAny` C struct provides the 16-byte binary layout; C++ wrappers add ownership semantics.

### Solution
- `AnyView`: non-owning view (no IncRef/DecRef). Safe only while the referenced value is alive.
- `Any`: owning value (IncRef on copy, DecRef on destroy). Materializes view-only types on construction.
- Both wrap `TVMFFIAny data_` as their sole member, ensuring binary compatibility with the C ABI.

### Goals
- Provide zero-cost conversion between `Any` and `AnyView` (same layout).
- Support strict type access (`as`) and conversion-based access (`cast`/`try_cast`) as distinct operations.
- Non-goals: large-value inline storage (values > 8 bytes must be boxed as objects).

## Design

### AnyView: Non-Owning View

```cpp
class AnyView {
protected:
    TVMFFIAny data_;
public:
    int32_t type_index() const;

    // Strict type check only -- no conversion. Returns nullopt on mismatch.
    template<typename T> std::optional<T> as() const;

    // Object shortcut: returns const T* or nullptr
    template<typename T> const T* as() const;  // where T : Object

    // Conversion-enabled access. Throws TypeError on failure.
    template<typename T> T cast() const;

    // Conversion-enabled access. Returns nullopt on failure.
    template<typename T> std::optional<T> try_cast() const;
};
```

Construction from C++ type `T` goes through `TypeTraits<T>::CopyToAnyView`, which writes the type index and value into `data_` without taking ownership.

Special view-only types (cannot be held in `Any`):
- `kTVMFFIRawStr` (const char*) -- non-owning string reference
- `kTVMFFIByteArrayPtr` (TVMFFIByteArray*) -- non-owning bytes reference
- `kTVMFFIObjectRValueRef` -- rvalue reference for move semantics
- `kTVMFFIDLTensorPtr` (DLTensor*) -- non-owning tensor pointer

### Any: Owning Value

```cpp
class Any {
protected:
    TVMFFIAny data_;
public:
    void reset();
    bool same_as(const Any&) const;
    bool same_as(const ObjectRef&) const;

    // Strict: lvalue (copy) and rvalue (move) overloads
    template<typename T> std::optional<T> as() const&;
    template<typename T> std::optional<T> as() &&;  // move semantics

    // Object pointer shortcut
    template<typename T> const T* as() const&;  // where T : Object

    // Conversion: lvalue (copy) and rvalue (move fast path)
    template<typename T> T cast() const&;
    template<typename T> T cast() &&;

    // Conversion: optional return
    template<typename T> std::optional<T> try_cast() const;
};
```

The rvalue `as<T>() &&` overload on `Any` enables move-based extraction: when the strict check passes, it calls `TypeTraits<T>::MoveFromAnyAfterCheck` to steal ownership without an extra IncRef/DecRef cycle. Similarly, `cast<T>() &&` has a fast path via `CheckAnyStrict` + `MoveFromAnyAfterCheck` before falling back to `TryCastFromAnyView`.

### AnyView-to-Any Conversion (`InplaceConvertAnyViewToAny`)

When constructing `Any` from `AnyView`, view-only types must be materialized:

| View Type Index     | Conversion Action |
|---------------------|-------------------|
| >= kTVMFFIStaticObjectBegin | IncRef the object pointer |
| kTVMFFIRawStr       | Create owned String object from const char* |
| kTVMFFIByteArrayPtr | Create owned Bytes object from TVMFFIByteArray* |
| kTVMFFIObjectRValueRef | Steal the pointed-to Object (move semantics) |
| POD types           | No conversion needed (no ownership) |

### Key Classes, Fields and Interfaces

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `AnyView::as<T>()` | `template<T> std::optional<T> as() const` | Strict type check, no conversion |
| `AnyView::cast<T>()` | `template<T> T cast() const` | Conversion-enabled, throws TypeError |
| `AnyView::try_cast<T>()` | `template<T> std::optional<T> try_cast() const` | Conversion-enabled, returns nullopt |
| `Any::as<T>() &&` | `template<T> std::optional<T> as() &&` | Rvalue strict check with move semantics |
| `Any::cast<T>() &&` | `template<T> T cast() &&` | Rvalue conversion with move fast path |
| `AnyHash` | `size_t operator()(const AnyView&) const` | String-aware hash; handles SmallStr cross-representation; NaN canonicalization |
| `AnyEqual` | `bool operator()(const AnyView&, const AnyView&) const` | String-aware equality; SmallStr vs Str cross-type; NaN-equal; PODs by 16-byte bitwise |
| `Any::same_as` | `bool same_as(const Any&) const` | Identity comparison including `zero_padding` field |

### Contracts, Assumptions and Invariants
- **Layout invariant**: `sizeof(AnyView) == sizeof(Any) == sizeof(TVMFFIAny) == 16`. Both contain only `TVMFFIAny data_`.
- **`zero_padding` invariant**: All non-small-string `TVMFFIAny` values must have `zero_padding = 0` at offset 4. This generalizes the prior padding-zero requirement: previously only sub-8-byte PODs needed zeroing (e.g., `DLDataType`, fixed in a5a08b2); now ALL non-small-string types must set `zero_padding = 0` in every `CopyToAnyView`/`MoveToAny` (enforced in 49e2ed4). This enables `AnyEqual`'s fast-path 16-byte comparison and ensures `AnyHash` consistency.
- **NaN canonicalization**: All NaN float values are structurally equal. `AnyHash` canonicalizes NaN to `std::numeric_limits<double>::quiet_NaN()` before hashing. `AnyEqual` treats `std::isnan(lhs) && std::isnan(rhs)` as equal (added in 59a837e for structural eq/hash, applies to `AnyEqual` as well).
- **Cross-representation string equality**: `AnyEqual` handles `kTVMFFISmallStr` vs `kTVMFFIStr` (and `kTVMFFISmallBytes` vs `kTVMFFIBytes`) by extracting content from both representations and comparing via `Bytes::memequal`. `AnyHash` uses `kTVMFFIStr` (not `kTVMFFISmallStr`) as the canonical type index component for hashing, ensuring small and large strings with the same content hash identically (added in 49e2ed4).
- **View-only materialization**: `Any` cannot hold view-only type indices. Construction from an `AnyView` with a view-only type index triggers materialization (IncRef, string copy, or move-steal).
- **Strict-check consistency**: `TypeTraits<T>::CheckAnyStrict` must return true for any value produced by `TypeTraits<T>::MoveToAny` -- i.e., strict check is the inverse of store.

### Extension Points
- New POD types can be added by assigning a type index in `[0, 64)` and providing a `TypeTraits` specialization.
- The `AnyHash`/`AnyEqual` can be extended for new string-like types by adding cases in the hash/equal implementations. The `kTVMFFISmallStr`/`kTVMFFISmallBytes` cross-type handling demonstrates the pattern.

### Usage Examples

#### Strict check (as) vs conversion (try_cast/cast)
**Context**: Accessing a value stored in `Any`/`AnyView` when you know the exact type vs when you want coercion.
```cpp
AnyView view = 1;  // stores int

// Strict: only matches exact type
auto opt_int = view.as<int64_t>();    // has_value() == true, value == 1
auto opt_bool = view.as<bool>();      // has_value() == false (int != bool)
auto opt_dbl = view.as<double>();     // has_value() == false (int != double)

// Conversion: tries type coercion
auto cast_bool = view.try_cast<bool>();   // has_value() == true, value == true
auto cast_dbl = view.try_cast<double>();  // has_value() == true, value == 1.0
double d = view.cast<double>();           // 1.0 (throws TypeError on failure)
```

#### Move extraction from rvalue Any
**Context**: Efficiently extracting a value from a temporary or consumed `Any` without extra ref-counting.
```cpp
Any any = String("hello");
// Rvalue as<T>() moves the string out without copying
auto opt_str = std::move(any).as<String>();  // moves if strict check passes
```

### Rust Binding (since 09477ce)

The Rust crate `tvm-ffi` provides `Any` and `AnyView<'a>` types that mirror the C++ wrappers:

**`AnyView<'a>`**: Non-owning view with Rust lifetime annotation. `Copy + Clone`. Contains `TVMFFIAny` data plus `PhantomData<&'a ()>` for lifetime tracking. `try_as::<T>()` provides strict-only type access (equivalent to C++ `as<T>()`).

**`Any`**: Owning value. `Clone` increments ref count for object types; `Drop` decrements. `try_as::<T>()` provides strict access. `TryFrom<AnyView>` materializes view-only types via `TVMFFIAnyViewToOwnedAny`. `From<T: AnyCompatible>` stores values via `T::move_to_any`.

**`AnyCompatible` trait** (Rust equivalent of C++ `TypeTraits<T>`):
```rust
pub unsafe trait AnyCompatible: Sized {
    unsafe fn copy_to_any_view(src: &Self, data: &mut TVMFFIAny);
    unsafe fn move_to_any(src: Self, data: &mut TVMFFIAny);
    unsafe fn check_any_strict(data: &TVMFFIAny) -> bool;
    unsafe fn copy_from_any_view_after_check(data: &TVMFFIAny) -> Self;
    unsafe fn move_from_any_after_check(data: &mut TVMFFIAny) -> Self;
    unsafe fn try_cast_from_any_view(data: &TVMFFIAny) -> Result<Self, ()>;
    fn type_str() -> String;
}
```

Implemented for: `bool`, `i8`-`i64`, `u8`-`u64`, `isize`, `usize`, `f32`, `f64`, `()`, `*mut c_void`, `String`, `Bytes`, `ObjectRef`, `DLDataType`, `DLDevice`, `Option<T: AnyCompatible>`.

The `try_cast_from_any_view` method provides conversion semantics (equivalent to C++ `try_cast<T>()`), e.g., `bool`->`int` and `int`->`float` coercions. The `TryFrom<AnyView>/TryFrom<Any>` impls use a `TryFromTemp<T>` helper to work around Rust's orphan rule while providing both strict check + move and fallback to conversion.

Note: Unlike C++, the Rust binding does not have separate `as`/`cast`/`try_cast` methods -- it uses `try_as` for strict access and `TryFrom` (which tries strict then conversion) for conversion-enabled access.

See `.knowledge/designs/rust-bindings.md` for the full Rust binding architecture.

### Evolution Timeline
| Version | Commit | Change | Motivation |
|---------|--------|--------|------------|
| v1 | 7d34eb8 | Initial `Any`/`AnyView` with `as()` (lenient) and `cast()` (strict throws) | Establish type-erased value system |
| v2 | 37a2e7c | Split `as()` into strict-only; add `try_cast()` for conversion; rvalue `as() &&` on `Any` | Cheaper strict checks, explicit conversion API |
| v3 | 192f196 | Add `tvm::Any`/`tvm::AnyView` namespace aliases | Convenience for downstream users |
| v4 | a5a08b2 | Fix DLDataType padding in `CopyToAnyView`/`MoveToAny` | AnyEqual correctness for sub-8-byte PODs |
| v5 | 59a837e | NaN canonicalization in structural eq/hash | All NaN representations compare equal and hash identically |
| v6 | 49e2ed4 | `zero_padding` invariant; cross-representation AnyHash/AnyEqual for SmallStr/SmallBytes; `Any::same_as` includes `zero_padding` | SSO support |

## Alternatives & Trade-offs
### Keep single `as<T>()` with conversion semantics
- Pros: Simpler API (one method)
- Cons: Every `as()` call pays conversion cost even when strict check is all that is needed; containers doing type verification waste cycles on coercion attempts
### Use separate named methods (e.g., `get_exact<T>` / `convert<T>`)
- Pros: Even more explicit naming
- Cons: Diverges from the `as`/`cast` convention common in C++ and other FFI systems; more API surface to learn

## Related Work
### Design Docs & ADRs
- `.knowledge/ADRs/001-unified-any-and-object.md` -- Decision to unify POD and object values under one type index system
- `.knowledge/ADRs/005-as-vs-cast-semantics.md` -- Decision to split strict and conversion type access
- `.knowledge/designs/type-traits.md` -- TypeTraits protocol that powers `as`/`cast`/`try_cast`
- `.knowledge/designs/0011-small-string-optimization.md` -- SSO design, `zero_padding` invariant, cross-representation hash/equal
- `.knowledge/designs/0010-structural-equal-hash.md` -- NaN canonicalization in structural comparison

### Evidence Matrix
- `as<T>()` strict semantics -> `2025-05-14-37a2e7c.md` + commit 37a2e7c + `AnyView::as`, `Any::as`
- Rvalue `as<T>() &&` -> `2025-05-14-37a2e7c.md` + commit 37a2e7c + `Any::as<T>() &&`
- `try_cast<T>()` -> `2025-05-14-37a2e7c.md` + commit 37a2e7c + `AnyView::try_cast`
- `tvm::Any`/`tvm::AnyView` aliases -> `2025-05-29-192f196.md` + commit 192f196
- DLDataType padding fix -> `2025-06-27-a5a08b2.md` + commit a5a08b2 + `TypeTraits<DLDataType>::CopyToAnyView`
- NaN canonicalization -> `2025-07-28-59a837e.md` + commit 59a837e
- SSO cross-representation hash/equal -> `2025-08-04-49e2ed4.md` + commit 49e2ed4
- Plus 1 supporting commit (16e9f0a namespace aliases)
