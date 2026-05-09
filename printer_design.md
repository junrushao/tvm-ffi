<!--- Licensed to the Apache Software Foundation (ASF) under one -->
<!--- or more contributor license agreements.  See the NOTICE file -->
<!--- distributed with this work for additional information -->
<!--- regarding copyright ownership.  The ASF licenses this file -->
<!--- to you under the Apache License, Version 2.0 (the -->
<!--- "License"); you may not use this file except in compliance -->
<!--- with the License.  You may obtain a copy of the License at -->

<!---   http://www.apache.org/licenses/LICENSE-2.0 -->

<!--- Unless required by applicable law or agreed to in writing, -->
<!--- software distributed under the License is distributed on an -->
<!--- "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY -->
<!--- KIND, either express or implied.  See the License for the -->
<!--- specific language governing permissions and limitations -->
<!--- under the License. -->

# Foreign Dialect Printing

This document sketches how a foreign dialect can reuse the `std` dialect
printer with minimal handwritten code.

There are two target scenarios, and they should not be forced into the same
object-model shape.

### D0: existing IR migration

For an existing IR such as Tilus, we may want to migrate it toward an std-based
dialect without changing its class structure, storage layout, or C++ inheritance
tree.  In this case the foreign node is not physically a `std.Add`, but it can
declare that it should be printed through the `std.Add` algorithm:

```python
@py_class("tilus.Add", std_schema=std.Add)
class TilusAdd:
    __ffi_dialect_mnemonic__ = ("tilus", "Add", "__add__")

    lhs: Var = field(std_field="a")
    rhs: Var = field(std_field="b")
```

The important property is that `TilusAdd` only physically reflects `lhs` and
`rhs`.  It does not acquire inherited storage fields such as `a` and `b`, and a
C++ `obj.as<std.Add>()` check should not succeed just because the type has
`std_schema=std.Add`.

### D1: new dialect development

For a new IR, we may choose class inheritance deliberately when the node really
is storage-compatible with a std class.  Inheritance gives simpler dispatch,
casts, and shared behavior:

```python
@py_class("weave.Add")
class WeaveAdd(std.Add):
    __ffi_dialect_mnemonic__ = ("weave", "Add", "__add__")

    # If the node is physically a std.Add, it should use std.Add fields.
    # Additional fields should be true extensions, not replacements for a/b.
```

This path is appropriate when the inherited fields remain the canonical storage
fields.  It is risky when a dialect wants to replace inherited fields with
different physical names, because the object would then contain both the
inherited std fields and the foreign replacement fields.

The design supports both scenarios:

- D0 uses `std_schema=std.SomeNode` for logical std compatibility without
storage inheritance.
- D1 uses Python/C++ inheritance when the foreign node intentionally has std
storage compatibility.

The user-facing `std_schema` name is intentional: the declaration selects the
canonical std schema whose fields and print algorithm the foreign node projects
onto.  Field-level resolution stays in `tvm_ffi.dataclasses.field(...)`,
instead of requiring a custom text printer for every foreign node.

## Field API

Prefer a first-class FFI field API:

```python
from tvm_ffi.dataclasses import field

operand_a: Var = field(std_field="a")
```

The first-class API is easier to validate, document, and expose to editors.  It
can still lower to the existing reflected field table, so C++ and Rust code can
read the same resolution rules.

`field(...)` is a declaration-time sentinel, similar to Python's native
`dataclasses.field(...)`.  It should not directly register runtime state,
because it does not yet know the resolved annotation, owning class, parent type,
runtime type index, or object layout.  The `@py_class` decorator is the point
that consumes these field declarations and materializes runtime reflection.

For example, `field(std_field="a")` creates a Python `Field` object whose
intent is later lowered by `@py_class` into the existing reflected field table:

```text
TVMFFITypeInfo(type_key="rx.Add")
  fields[]
    TVMFFIFieldInfo(name="operand_a",
                    metadata={"type_schema": ..., "std_field": "a"})
    TVMFFIFieldInfo(name="operand_b",
                    metadata={"type_schema": ..., "std_field": "b"})
```

This does not add a new TypeAttrColumn.  The resolution rule is field-local
information, so it belongs in `TVMFFIFieldInfo.metadata`, alongside the existing
`type_schema` metadata.  Type-level hooks such as `__ffi_text_print__` and
`__ffi_dialect_mnemonic__` continue to use TypeAttrColumn entries.

The conceptual split is:

```text
Field object         Python declaration-time intent
TVMFFIFieldInfo      C++ runtime reflection result
TVMFFITypeInfo       Per-type table that owns fields, methods, and ancestors
```

Fixed field roles should be small.  They describe **where** a field
participates in the print structure; they do not describe concrete syntax by
themselves.

The public API uses one print-role argument:

```python
field(print=...)
```

Core role constructors:


| Option                                  | Meaning                                                      |
| --------------------------------------- | ------------------------------------------------------------ |
| `std_field="a"`                         | Foreign field resolves a logical field on the std-kind node. |
| `print=ignore()`                        | Field is intentionally consumed without printed syntax.      |
| `print=body_prepend("body", order=...)` | Field contributes statements before the named body field.    |
| `print=body_append("body", order=...)`  | Field contributes statements after the named body field.     |
| `print=body_wrap("body")`               | Field contributes a wrapper around the named body field.     |
| `print=slot(...)`                       | Field contributes to a named print-builder slot.             |


`slot(...)` is the general internal form behind call arguments, call keyword
arguments, attrs, and annotations.  Most users should write the readable helper
constructors instead of spelling raw slots:


| Helper                    | Desugars to                             |
| ------------------------- | --------------------------------------- |
| `call_arg(0)`             | `slot("call.args", index=0)`            |
| `call_kwarg("predicate")` | `slot("call.kwargs", name="predicate")` |
| `attrs()`                 | `slot("attrs")`                         |
| `annotation_of("args")`   | `slot("args.annotation")`               |
| `annotation_of("return")` | `slot("return.annotation")`             |


Body roles use `order=...` to order multiple fields that target the same body
slot:

```python
reads: list[BufferRegion] = field(print=body_prepend("body", order=30))
writes: list[BufferRegion] = field(print=body_prepend("body", order=40))
```

The selected print builder decides how to turn a field value into syntax.
Trivial slots can use the default renderer.  Nontrivial slots should name a
render method.  The render method is a normal reflected FFI method and must be
decorated with `@method`:

```python
match_buffers: list[MatchBufferRegion] = field(
    print=body_prepend("body", order=70, render="print_match_buffers")
)

@method
def print_match_buffers(self, printer, path, match_buffers):
    ...
```

A field may participate in more than one print role:

```python
buffer_map: dict[Var, Buffer] = field(
    print=[
        annotation_of("args", render="print_buffer_annotations"),
        body_prepend("body", order=10, render="print_match_buffers"),
    ]
)
```

`field(...)` is only for reflected storage fields.  In the first implementation,
a render method corresponds to exactly one field: the field whose print role
names it.  If a printed part depends on multiple fields, use exact
`__ffi_text_print__` for now or model that printed part as one reflected field;
multi-field print methods are intentionally deferred.

For example:

```python
@py_class("tirx.SBlock", std_schema=std.Scope)
class SBlock:
    name_hint: str = field(print=body_wrap("body", render="print_sblock_header"))
    body: Stmt = field(std_field="body")

    reads: list[BufferRegion] = field(print=body_prepend("body", order=30))
    writes: list[BufferRegion] = field(print=body_prepend("body", order=40))
    annotations: dict[str, object] = field(
        print=body_prepend("body", order=50, render="print_sblock_attrs")
    )
    alloc_buffers: list[Buffer] = field(
        print=body_prepend("body", order=60, render="print_alloc_buffers")
    )
    match_buffers: list[MatchBufferRegion] = field(
        print=body_prepend("body", order=70, render="print_match_buffers")
    )
    init: Stmt | None = field(print=body_prepend("body", order=80, render="print_init"))
    axis_bindings: list[AxisBinding] = field(
        print=body_prepend("body", order=10, render="print_axis_bindings")
    )

    @method
    def print_axis_bindings(self, printer, path, axis_bindings):
        ...
```

The field declarations say that these fields modify the `body` part of a
scope-like print structure.  `ScopePrintBuilder` still owns the concrete
algorithm, and TIRx render methods own the concrete syntax:

```text
iter_vars      -> T.axis.* bindings
reads          -> T.reads(...)
writes         -> T.writes(...)
annotations    -> T.sblock_attr(...)
alloc_buffers  -> buffer declarations
match_buffers  -> T.match_buffer(...) statements
init           -> with T.init(): ...
```

The fixed field roles intentionally do not include:

- computed std fields, such as `min + extent + step -> range_`;
- value classifiers, such as op-specific Relax `Call` printing;
- method/index syntax choices, such as buffer load/store shorthand;
- generic sugar choices, such as infix binary operators.
- literal fallback behavior for opaque payloads.

Those cases belong in std-kind print builders, type-specific render methods, or
exact `__ffi_text_print__` implementations.

Nodes that do not have a real semantic counterpart in `std` should use exact
printing instead of choosing a misleading `std_schema`.  For example,
`tirx.Mod` is an IR node with truncating modulo semantics; it should not declare
`std_schema=std.Call` just because its fallback syntax is call-shaped.

## Std Kind

The std kind of a foreign type can be established in two ways.

For D0, an existing foreign class declares the std kind explicitly:

```python
@py_class("tilus.Add", std_schema=std.Add)
class TilusAdd:
    lhs: Var = field(std_field="a")
    rhs: Var = field(std_field="b")
```

This means `TilusAdd` selects the `std.Add` algorithm for reusable printing,
but it is not a subclass of `std.Add`, does not inherit `std.Add` storage, and
should not pass C++ casts or `IsInstance` checks for `std.Add`.

For D1, subclassing a std node gives the foreign type a default std kind:

```python
class TirxAdd(std.Add):
    ...
```

means `TirxAdd` can be used with `std.Add` algorithms.  The foreign object is
still the canonical IR object; `std.Add` is only the selected algorithm kind.

If a foreign type does not physically store the std fields, it should prefer the
D0 `std_schema` route instead of inheriting the std class.  It must
declare how its fields resolve into the std-kind algorithm.

## Resolved Print Info

The reusable print path has three pieces:

```text
Dispatch
  -> choose the print builder

ResolvePrintInfo
  -> resolve the fields and render methods that builder needs

PrintBuilderBase + concrete PrintBuilder
  -> execute the canonical print algorithm for the selected std kind
```

`ResolvedPrintInfo` is not a conversion from foreign IR to std IR.  It is the
resolved set of fields and methods needed by a print builder for the original
object.

For a foreign type, `ResolvedPrintInfo` answers questions such as:

```text
What std kind algorithm was selected?
How is std field "a" read from this object?
How is std field "body" read from this object?
Which fields prepend, append, or wrap "body"?
Which render methods should be called for nontrivial fields?
Which fields are intentionally ignored?
```

For example:

```python
@py_class("tilus.Add", std_schema=std.Add)
class TilusAdd:
    __ffi_dialect_mnemonic__ = ("tilus", "Add", "__add__")

    lhs: Var = field(std_field="a")
    rhs: Var = field(std_field="b")
```

declares a contract like:

```text
std kind: std.Add
std.Add.a <- tilus.Add.lhs
std.Add.b <- tilus.Add.rhs
```

The printer should use the std `Add` printing algorithm on the original foreign
object through this contract.  It should not materialize a temporary `std.Add`.

### Resolution Sources

Fields used for printing come from two sources.

**S0: std fields.**  These are fields expected by the selected std-kind
algorithm.  They resolve either from a foreign `std_field` declaration or from
real inherited std storage:

```text
if exactly one field declares field(std_field="a"):
  std field "a" resolves to that field
else if the object physically has std field "a":
  std field "a" resolves to inherited/std storage
else:
  the required std field is missing
```

**S1: print-role fields.**  These are fields that are not std fields but are
declared with `field(print=...)`.  They tell the selected print builder where
the field participates in the print structure:

```text
body_prepend("body")  -> field contributes statements before body
body_append("body")   -> field contributes statements after body
body_wrap("body")     -> field contributes a body wrapper
call_arg(...)         -> field contributes to call args
call_kwarg(...)       -> field contributes to call kwargs
attrs()               -> field contributes an attrs bundle
annotation_of(...)    -> field contributes an annotation
ignore()              -> field is intentionally consumed without syntax
```

If a non-std field has no `field(print=...)` role and is not explicitly ignored,
resolution should fail.  That is a bug in the dialect declaration, because the
printer would otherwise silently drop reflected state.

Render methods are resolved from method names referenced by print roles:

```python
match_buffers = field(
    print=body_prepend("body", order=70, render="print_match_buffers")
)
```

Resolution should check that `print_match_buffers` exists and is callable.  The
method must be decorated with `@method`, so it is registered in
`TVMFFITypeInfo.methods[]`.  The selected print builder decides when to call it.

### Print Builders

A print builder is the reusable algorithm for a std-kind shape.  The
implementation should keep resolution and printing separate:

```cpp
class PrintBuilderBase {
 protected:
  PrintBuilderBase(ObjectRef obj, IRPrinter printer, AccessPath path, int32_t std_schema);

  Any ReadStdField(String name) const;
  AccessPath PathForStdField(String name) const;
  List<StmtAST> PrintBody(String body_field) const;
  Any RenderPrintPart(PrintPart part, std::vector<Any> extra_args = {}) const;

  ResolvedPrintInfo info_;
};

class ScopePrintBuilder : public PrintBuilderBase {
 public:
  ScopePrintBuilder(ObjectRef obj, IRPrinter printer, AccessPath path, int32_t std_schema)
      : PrintBuilderBase(std::move(obj), std::move(printer), std::move(path), std_schema) {}

  NodeAST Build() const;
};
```

`ResolvedPrintInfo` owns the reflected facts: field projection,
`field(print=...)` directives, render-method lookup, and validation.  It should
not know the concrete syntax of `std.Scope`, `std.Add`, or other std kinds.

`PrintBuilderBase` owns the common mechanics that every std-kind builder needs
after resolution:

```text
read a logical std field from the original object
compute the matching access path for diagnostics/source paths
render a field contribution through its @method hook
normalize a contribution into statements
assemble body_prepend/body/body_append/body_wrap contributions
reject custom print directives in builders that do not consume them
```

Concrete builders should be small.  They only encode the canonical syntax for
one std kind.  For example, `ScopePrintBuilder` is the advanced version of the
existing `TextPrint(std.Scope)` algorithm.  It knows the canonical structure of
scope-like printing:

```text
optional wrapper
body-prefix statements
body statements
body-suffix statements
```

`ScopePrintBuilder` gets all object-specific information through
`PrintBuilderBase`, which delegates field resolution to `ResolvedPrintInfo`.
For a TIRx SBlock, resolution may provide:

```text
std field:
  body <- SBlock.body

body wrapper:
  name_hint, render=print_sblock_header

body prepends:
  reads, order=30
  writes, order=40
  annotations, order=50, render=print_sblock_attrs
  alloc_buffers, order=60, render=print_alloc_buffers
  match_buffers, order=70, render=print_match_buffers
  init, order=80, render=print_init
```

Then `ScopePrintBuilder` executes the scope algorithm:

```text
render wrapper
render prepend fields in order
print body after prepend hooks run
render append fields
return final pyast
```

Nontrivial render methods may update printer state before the body is printed.
For example, `print_match_buffers` may emit `T.match_buffer(...)` statements and
declare buffer names so the later body print can refer to those buffers.

## Printer Reuse

Printer dispatch should use one linear type-resolution algorithm.  For an
original object `O` with dynamic type `T`, walk the exact type and then its
single FFI ancestor chain:

```text
for K in [T, nearest parent, ..., root]:
  if K has __ffi_text_print__:
    call that printer on O
    stop

  if K has std_schema:
    resolve ResolvedPrintInfo for O and that std_schema
    run the print builder for the std_schema
    stop

  if K has a registered std print builder:
    resolve ResolvedPrintInfo for O and K
    run that print builder
    stop

DefaultPrint(O)
```

This means:

- `__ffi_text_print__` wins over `std_schema` when both are declared on
the same type.
- A child declaration wins over any parent declaration because the walk starts
at the exact dynamic type.
- `std_schema` naturally inherits through ordinary FFI inheritance when
a child has neither an exact text printer nor an exact std-schema declaration.
- Exact std nodes and D1 subclasses use the same builder path.  The dispatch
loop finds the first ancestor type index that has a registered std print
builder.
- The object passed to the selected printer or print builder is always the
original dynamic object `O`.
- D0 `std_schema` dispatch must not cast `O` to the std kind.  It uses
`ResolvedPrintInfo` instead.

TypeAttrColumn lookup is intentionally exact, so this loop is an explicit
fallback policy layered on top of TypeAttrColumn.  The std-kind print builder is
called with the original dynamic object and its `ResolvedPrintInfo`, not with a
materialized std object.  This preserves the dynamic type's dialect/mnemonic
TypeAttrColumn values.

Std nodes should not need `__ffi_text_print__` for their ordinary printing.
`__ffi_text_print__` means an exact custom printer for a concrete type.  Std
syntax is supplied by internal std print builders:

```text
std.Add    -> AddPrintBuilder
std.Scope  -> ScopePrintBuilder
std.Func   -> FunctionPrintBuilder
...
```

The std builder table is internal implementation state, not a new
`TVMFFITypeAttrColumn`.  Dispatch finds builders by type index:

```cpp
Optional<PrintBuilder> builder = LookupStdPrintBuilder(type_index);
```

This avoids repeated `obj.as<std.Add>()`, `obj.as<std.Scope>()`, and similar
checks.  The type index and `TVMFFITypeInfo::type_ancestors` chain are enough to
find whether the exact type or any ancestor is a std kind with a print builder.

For D0, `std_schema` is stored in an exact TypeAttrColumn entry:

```text
__ffi_std_schema__[TilusAdd] = type_index(std.Add)
```

The payload is the runtime type index of the canonical std node, not a separate
enum.  This reuses the same `std type_index -> print builder` table that D1
inheritance uses when dispatch walks to a real std ancestor.  It also avoids
changing `TVMFFITypeMetadata`; field-local annotations stay in
`TVMFFIFieldInfo.metadata`, while exact type-level dispatch facts use
TypeAttrColumn entries.

The FFI object model has one runtime storage parent.  `TVMFFITypeInfo` stores a
linear `type_ancestors` chain, not a multiple-inheritance graph.  Python classes
may use ordinary non-FFI mixins, but a `@py_class` should have at most one
registered FFI parent.  If multiple registered FFI bases are present, class
registration should reject the class instead of leaving printer dispatch
ambiguous.

Resolved std-kind printing works for D0 classes and can also support D1
subclasses that intentionally override std fields.  The std-kind print builder
must not read concrete storage such as `obj->a` directly when it is being used
for a foreign object.  Instead, it should ask `ResolvedPrintInfo` for the
std-shaped field:

```text
std field "a" -> original field "a"          # ordinary std.Add
std field "a" -> original field "lhs"        # tilus.Add with std_field="a"
```

`ResolvedPrintInfo` computes this mapping from the selected std kind,
`TVMFFITypeInfo::type_ancestors`, and `TVMFFIFieldInfo.metadata`.  For D0,
`std_schema` supplies the std kind because there is no std ancestor.  For
D1, std ancestors provide the default std kind and identity field mappings.
Foreign fields with `std_field=...` override the corresponding logical std
field for the dynamic type's resolved print info.  The original object remains
the printed identity, so `CallMnemonic` still sees `tilus.Add` or `weave.Add`,
not `std.Add`.

The display identity and the std algorithm identity are separate:

```text
display identity:    dynamic object's __ffi_dialect_mnemonic__  # tirx.Add
algorithm identity:  selected std-kind print builder            # std.Add
field identity:      resolved field mapping                     # a <- operand_a
```

Foreign nodes that reuse std-kind printing must define their own
`__ffi_dialect_mnemonic__`.
Std-kind printer reuse does not imply inherited dialect identity.  If a foreign
type resolves std fields but does not register a dialect mnemonic, printing
should fail with a clear error instead of silently printing as the std ancestor.

Generic handling should keep the existing printer dialect-selection rule for
now.  The implementation should therefore reuse the existing generic registry,
but the generic helper must read binary operands through
`ResolvedPrintInfo` instead of casting back to concrete storage such as
`AddObj::a`.

When printing through a std-kind builder, the display identity remains foreign:

- `CallMnemonic` should use `tirx.Add`, not `std.Add`.
- access paths should map std fields back to resolved foreign fields when
possible.
- generic sugar should be used only when the text can round-trip.

For example, `TirxAdd(operand_a=x, operand_b=y)` may print as `x + y` when the
generic sugar can round-trip.  Otherwise, the printer should suppress sugar and
print explicit syntax such as `tirx.Add(x, y)`.

## Field Resolution and Storage Inheritance

`std_field` is a logical std-field resolution rule.  It says that a foreign
field is the authoritative implementation of a std field while a std-kind print
builder is printing this dynamic type.  It does not delete, rename, or mutate
reflected storage fields.

In D0, this is clean because there is no storage inheritance:

```text
std.Add logical fields:  ty, a, b
tilus.Add fields:        lhs, rhs
resolved fields:         a <- lhs, b <- rhs
```

DefaultPrint for `TilusAdd` sees only the physical foreign fields.  The std
print builder sees `a` and `b` through `ResolvedPrintInfo`.

In D1, overriding inherited fields is more dangerous:

```text
std.Add inherited fields:  ty, a, b
weave.Add own fields:      operand_a, operand_b
resolved fields:           a <- operand_a, b <- operand_b
physical fields:           ty, a, b, operand_a, operand_b
```

This should be treated as logical std-field override, not ordinary Python name
shadowing.  The override applies only inside `ResolvedPrintInfo`.  It does
not make the inherited fields disappear, and it does not prevent C++ code from
casting the object to `std.Add` and reading `a` and `b`.

Therefore the preferred design is:

- Use D0 `std_schema` when migrating an existing IR or when foreign field
names replace std field names.
- Use D1 inheritance when the node intentionally preserves std storage fields.
- Avoid relying on D1 override-over-inherited-storage as the normal pattern.
It is compatible with the resolved-print model, but it creates confusing
constructor, DefaultPrint, repr, equality, serialization, and C++ cast
behavior.

## Open Questions

- Whether generic inheritance is implicit from std kind or an explicit type attr.
- How much access-path remapping is needed in the first implementation.
- Whether D1 override-over-inherited-storage should be allowed at all, or
only accepted with an explicit opt-in.
- How broadly logical std-field override should apply beyond printing, such as
repr, serialization, structural equality, and pattern matching.
