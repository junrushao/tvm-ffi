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

# Extensible Std-Derived Dialect Printing

## Background and Existing Effort

The current `std` dialect has three pieces that already point in the right direction:

1. Every IR node is an FFI object rooted at `std.Node`.
2. Every concrete printed node has dialect metadata through `__ffi_dialect_mnemonic__`, now supplied from Python as `class X(std.Node, mnemonic="dialect.Name")`.
3. The text printer already has reusable expression and scope helpers that know how to combine operands, keyword attributes, targets, and bodies into Python-shaped syntax.

The missing part is a portable way for a subclass of a `std` node to say which of its dataclass fields are language operands, compile-time attributes, binding targets, or body statements. Today those meanings are embedded in concrete `std` fields such as `Stmt.attrs`, `For.vars`, `Scope.binds`, and `Func.body`. That makes subclassing awkward: a dialect extension that only wants to rename a mnemonic and add one attribute has to fit itself into the base node's fixed field layout.

The new design moves those open-ended pieces out of base `std` nodes and into dataclass field metadata. The base `std` nodes keep only the stable schema fields that define the syntactic form:

```text
Func
    symbol: str
    args: list[Var]
    ret_type: Ty | None

Scope

For
    start: Expr | None
    stop: Expr | None
    step: Expr | None

While
    cond: Expr

BindExpr
    expr: Expr

VarDef

Store
    lhs: Expr
    indices: list[Range]
    rhs: Expr

IfStmt
    cond: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]
```

Fields such as `attrs`, `body`, `binds`, and `vars` become subclass responsibilities expressed with `dc.field(lang_kind=...)`.

Validation against `/Users/junrus/Projects/tirx.py` confirms this is the right axis of extension:

- `tirx.AttrStmt` has `node`, `attr_key`, `value`, and `body`, where the first three are attribute-like metadata and `body` is a scoped statement region.
- `tirx.IterVar.var`, `tirx.CommReducer.lhs/rhs`, and `tirx.Reduce.axis -> IterVar.var` show that binders can be nested inside helper nodes, not just direct `list[Var]` fields.
- `tirx.FuncTy.arg_types` shows that field names are not enough; `arg_types` are type-level data, not syntax-visible function arguments.
- `tirx.PointerTy`, `tirx.BufferTy`, and `tirx.Reduce` show that nested constants, nested types, and nested IR nodes need to pass through attributes without special casing.

## Task Specification and API Design

### Field Metadata

Extend `dc.field` with:

```python
dc.field(lang_kind="arg" | "attr" | "var_def" | "body")
```

The field metadata is not a reflected data field and is not part of structural equality by itself. It describes how the field should be collected for text-format construction.

Meanings:

- `arg`: ordered positional IR operands or header arguments.
- `attr`: compile-time metadata printed as keyword arguments.
- `var_def`: variables introduced by the node.
- `body`: statements owned by a scope-like node.

Default `lang_kind=None` means the field remains an ordinary reflected field and does not participate in the generic std printer protocol.

Collection rules should be simple and explicit:

- `arg`: append a scalar value; flatten list/tuple values in declaration order.
- `attr`: put scalar values into `attrs[field_name]`; if the field is named `attrs` and is a mapping or `DictAttrs`, merge its entries.
- `var_def`: recursively collect variables from `Var`, lists/tuples, and values that themselves provide field collection.
- `body`: normalize a scalar statement to a one-element body and preserve list/tuple bodies in order.

If a dialect needs a list to be a single positional argument rather than variadic operands, it should wrap that list in a dialect node or use a later explicit option such as `lang_many=False`. The MVP should not infer this from annotations.

### FieldCollectionResult

Add a small reflected carrier type:

```python
@dc.c_class("ffi.std.FieldCollectionResult")
class FieldCollectionResult:
    args: list[Any]
    attrs: std.DictAttrs
    var_def: list[std.Var]
    body: list[std.Node]
```

`args` is typed as `Any` in implementation even though most values are `std.Node`, because real dialects need scalar and nested compile-time constants in constructor positions. `attrs` is a `DictAttrs` so the C++ printer can reuse the existing "attrs as kwargs" path.

Add a new TypeAttrColumn:

```text
__ffi_dialect_field_collector__
```

Its value is a callable:

```python
def __ffi_dialect_field_collector__(self) -> FieldCollectionResult: ...
```

`@py_class` should synthesize this callable when any field has `lang_kind != None`, register it as a TypeAttrColumn, and reject malformed `lang_kind` values at decoration time. If a class explicitly defines `__ffi_dialect_field_collector__`, prefer rejecting the conflict for the first implementation; custom collection can be added later once the generated contract is stable.

### Printer Integration

The printer should use this as a value-collection protocol, not as a replacement for all specialized `std` printers.

Suggested C++ shape:

- Add `reflection::type_attr::kDialectFieldCollector = "__ffi_dialect_field_collector__"`.
- Ensure the column in the text-printer registration path.
- Add a small helper in `std.cc` that looks up the collector by `obj->type_index()`, calls it if present, and returns an empty `FieldCollectionResult` otherwise.
- Keep implementation details in `.cc`; expose only the small carrier type and TypeAttrColumn name in headers.

Then update each `TextPrint` family to combine core schema fields with the collected fields:

- Expressions: print schema operands plus `result.args`; append `result.attrs` as kwargs; use generic Python syntax only when attrs are empty and dialect derivation conditions hold.
- `Load`: use schema `lhs` and `indices`; collected attrs force explicit call syntax.
- `Store`: use schema `lhs`, `rhs`, `indices`; collected attrs force explicit call syntax.
- Body-free statements: `Assert`, `Return`, `Yield`, `Break`, and `Continue` use collected attrs to decide between Python syntax and explicit mnemonic call.
- `BindExpr`: schema `expr` is the RHS; `result.var_def` supplies assignment targets; attrs force explicit RHS call.
- `VarDef`: `result.var_def` supplies assignment targets; `result.args` supplies declaration arguments such as types or dialect-specific header operands.
- `For`: schema `start/stop/step` form the range-like header; `result.attrs` are kwargs on the range/header call; `result.var_def` supplies loop targets; `result.body` supplies the loop body.
- `While`: schema `cond` forms native `while cond:` when attrs are empty; attrs use a header-object form such as `with toy.while_(cond, **attrs):`.
- `Func`: schema `symbol/args/ret_type` remain the Python function signature; `result.attrs` feed the decorator/header object; `result.body` supplies the function body.
- `Scope`: no schema fields; `result.args` and `result.attrs` form the header object; `result.var_def` supplies optional `as` targets; `result.body` supplies the region body.
- `Module`: keep current std module behavior, but allow subclasses to use collected `body` as the module body if they do not expose `funcs`.

For classes with `__ffi_dialect_mnemonic__` but no custom `__ffi_text_print__`, the default printer should prefer `dialect.Mnemonic(...)` over `full.type.Key(...)` when field collection is available. The existing field-by-field fallback should stay for non-dialect objects.

### Parser Integration

Field collection alone is not enough to parse arbitrary dialect text. The parser also needs a dialect namespace that exposes classes, factories, and generic operators.

The minimal rule:

- Simple nodes can parse through direct class calls such as `toy.Op(...)` if the dialect module exposes `Op`.
- Scope-like nodes still need parser `Frame` objects because the parser must collect a header first, then bind targets, parse body statements, and finally materialize the node.

Recommended factory abstraction:

- Parameterize existing `FuncFactory`, `ForFactory`, `WhileFactory`, and `ScopeFactory` by `node_cls`.
- For `node_cls` subclasses of `std.For`, create a `ForFactory(node_cls=ExtFor)` whose `to_dialect()` passes schema fields plus collected attrs/body/targets into the subclass constructor.
- For `node_cls` subclasses of `std.Func`, use a `FuncFactory(node_cls=ExtFunc)`.
- For `node_cls` subclasses of `std.Scope`, use a `ScopeFactory(node_cls=ExtScope)`.
- For branch statements like `IfStmt`, keep explicit generics initially; add richer branch `lang_kind` variants only if subclasses need custom then/else body collection.

Parser binding should also stop hard-coding only `std.BindExpr` and `std.VarDef`. It needs a small dialect-neutral helper that asks field collection for `var_def` and registers those variables in the active scope.

## Step-by-Step Plan

1. Add `lang_kind` to `python/tvm_ffi/dataclasses/field.py`.
   Validate allowed values, store it on `Field`, and preserve it in `dataclasses.fields()`.

2. Add `FieldCollectionResult`.
   Define the reflected carrier in `std` with `args`, `attrs`, `var_def`, and `body`. Keep it structurally simple.

3. Generate collectors in `@py_class`.
   During `_register_fields_into_type`, after annotations resolve, synthesize `__ffi_dialect_field_collector__` from the resolved own fields. Register it as a TypeAttrColumn by adding the name to `_FFI_TYPE_ATTR_NAMES`.

4. Add C++ reflection plumbing.
   Add `kDialectFieldCollector`, ensure the column, and implement a helper that calls the collector and returns an empty result if absent.

5. Remove open-ended base fields.
   Remove `Stmt.attrs`, `Func.body`, `Scope.binds/body`, `For.vars/body`, `While.body`, `BindExpr.vars`, and `VarDef.vars` from C++ declarations, Python stubs, constructor registrations, and tests. Keep the core schema fields listed above.

6. Refactor `std.cc` printers around collected fields.
   Reuse the current expression and scope builder logic, but source attrs, targets, and bodies from `FieldCollectionResult`.

7. Refactor `_std_lang.py` factories.
   Parameterize the frame factories by destination node class and make target/body materialization compatible with field collection.

8. Generalize parser binding.
   Replace `isinstance(stmt, (std.BindExpr, std.VarDef))` checks with a helper that extracts collected `var_def` from any `std.Node`.

9. Redesign tests around subclasses.
   Add toy subclasses such as `ExtFor(std.For, mnemonic="toy.For")` with `loop_kind: str = dc.field(lang_kind="attr")`, and `MatmulOp(std.VarDef, mnemonic="toy.Matmul")` with operand vars and output var marked by `arg` and `var_def`.

10. Add TIRX-shaped coverage.
    Mirror `AttrStmt`, nested `IterVar`, and reducer-style nested binders in small tests so the design is exercised against the real patterns from `/Users/junrus/Projects/tirx.py`.

## Caveats and Common Pitfalls

- TypeAttrColumn values do not inherit. Register generated collectors on every concrete subclass that needs one.
- Do not infer language roles from field names. `arg_types` in TIRX is not syntax-visible function arguments.
- Do not assume binders are direct `Var` fields. Nested binder carriers are needed for `IterVar`, reducers, and buffer-like nodes.
- Do not treat `attrs` as only `std.Attrs`. Real dialect attributes can be strings, ints, expressions, arbitrary objects, lists, and nested dictionaries.
- Do not let reflected field order define text syntax. `lang_kind` is the syntax contract; reflected field order is only the deterministic declaration order used by the generated collector.
- Do not make parser frames frozen. Frames are intentionally two-phase: header first, target/body later.
- Keep custom `__ffi_text_print__` highest priority. Field collection is a generic path for common subclass patterns, not a replacement for truly custom printers.
- Keep stable diagnostics in `_pyast_parser.py`. Invalid function signatures, invalid targets, or malformed frames should raise `TypeError`, not rely on `assert`.
- Removing base fields is source and ABI breaking for C++ extensions. Downstream C++ must be rebuilt and Python constructor expectations must be updated together.
- If a dialect wants parser round-trip, it must register a language namespace and factories. A class with `mnemonic="toy.Op"` is printable metadata, not enough by itself for `parse("toy.Op(...)")`.
