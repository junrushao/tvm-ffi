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

# IR Dialects

This document sketches the current standard core dialect and how later dialects
can specialize it.  The node tables use the proposed `$dialect`, `$mnemonic`,
and `$generics` metadata model described in the last section.

The standard dialect lives in C++ as `tvm::ffi::std_`, is exposed to Python as
`tvm_ffi.std`, and uses type keys under `ffi.std.*`.

**Open Questions**

- Type arguments to calls.
- Whether `std.DataTypeImm` should exist as a first-class node.


## Std Dialect

`std` defines the common type, expression, statement, structure, and attribute
nodes.  The following classes are abstract bases and are not directly
constructible:
- `std.Node`
- `std.Ty`
- `std.Stmt`
- `std.Attrs`
- `std.Structure`
- `std.Expr`
- `std.Bind`

### Types

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.AnyTy` | none | `std` | `Any` | N/A |
| `std.PrimTy` | `dtype` | `std` | `Prim` | N/A |
| `std.TupleType` | `fields` | `std` | `Tuple` | N/A |
| `std.TensorTy` | `shape`, `dtype` | `std` | `Tensor` | N/A |

The std text printer still uses concise type names such as `std.Any`,
`std.i32`, `std.Tuple[std.i32, std.f32]`, and `std.bf16[3, 12]`; those are
concrete text-format choices, not `$generics` values.  The `std` prefix follows
the printer's dialect alias policy, so `{ "std": "*" }` prints these as `Any`,
`i32`, `Tuple[i32, f32]`, and `bf16[3, 12]`.

### Structures

`std.Structure` is the base for structural helper nodes that are not statements
or expressions.

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.Range` | `start`, `stop`, `step` | `std` | `Range` | N/A |

`std.Range` prints with slice/range syntax such as `1:10:2`, `:10`, and `::2`.

### Attributes

All concrete subclasses of `std.Attrs` print as call syntax with keyword-only
arguments: `$name(attr_0=..., attr_1=...)`.

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.DictAttrs` | `values` | `std` | `DictAttrs` | N/A |

### Expressions

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.Var` | `ty`, `name` | `std` | `Var` | N/A |
| `std.IntImm` | `ty`, `value` | `std` | `IntImm` | N/A |
| `std.FloatImm` | `ty`, `value` | `std` | `FloatImm` | N/A |
| `std.StringImm` | `ty`, `value` | `std` | `StringImm` | N/A |
| `std.Add` | `ty`, `a`, `b` | `std` | `Add` | `__add__` |
| `std.Sub` | `ty`, `a`, `b` | `std` | `Sub` | `__sub__` |
| `std.Mul` | `ty`, `a`, `b` | `std` | `Mul` | `__mul__` |
| `std.FloorDiv` | `ty`, `a`, `b` | `std` | `FloorDiv` | `__floordiv__` |
| `std.FloorMod` | `ty`, `a`, `b` | `std` | `FloorMod` | `__mod__` |
| `std.Min` | `ty`, `a`, `b` | `std` | `Min` | `min` |
| `std.Max` | `ty`, `a`, `b` | `std` | `Max` | `max` |
| `std.Eq` | `ty`, `a`, `b` | `std` | `Eq` | `__eq__` |
| `std.Ne` | `ty`, `a`, `b` | `std` | `Ne` | `__ne__` |
| `std.Le` | `ty`, `a`, `b` | `std` | `Le` | `__le__` |
| `std.Ge` | `ty`, `a`, `b` | `std` | `Ge` | `__ge__` |
| `std.Gt` | `ty`, `a`, `b` | `std` | `Gt` | `__gt__` |
| `std.Lt` | `ty`, `a`, `b` | `std` | `Lt` | `__lt__` |
| `std.And` | `ty`, `a`, `b` | `std` | `And` | `__and__` |
| `std.Or` | `ty`, `a`, `b` | `std` | `Or` | `__or__` |
| `std.Not` | `ty`, `operand` | `std` | `Not` | `__invert__` |
| `std.Load` | `ty`, `var`, `indices` | `std` | `Load` | `__load__` |
| `std.Cast` | `ty`, `value` | `std` | `Cast` | `__cast__` |
| `std.Call` | `ty`, `callee`, `args`, `attr` | `std` | `Call` | N/A |

`std.Expr` conversion accepts existing expressions and Python scalar literals.
Integers, floats, and strings become `std.IntImm`, `std.FloatImm`, and
`std.StringImm` with `std.AnyTy`.

The current text printer renders `std.Load` as indexed access, `std.Cast` with a
dtype callee such as `std.i32(x)`, and `std.Call` as `std.Call(callee, *args,
**attrs)`.

### Regional Statements

All subclasses of `std.Stmt` inherit `attrs: std.Attrs | None`.  The field is
keyword-only in reflected constructors and defaults to `None`, so statement
attributes do not have to be repeated in each concrete node definition.

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.Module` | `funcs` | `std` | `Module` | N/A |
| `std.Func` | `symbol`, `args`, `ret_type`, `body` | `std` | `Func` | N/A |
| `std.IfStmt` | `cond`, `then_body`, `else_body` | `std` | `IfStmt` | `__if__` |
| `std.Scope` | `vars`, `body` | `std` | `Scope` | N/A |
| `std.For` | `range_` | `std` | `For` | `__for__` |
| `std.While` | `cond` | `std` | `While` | `__while__` |

`std.For` and `std.While` are subclasses of `std.Scope`, because they share
scope-carried bindings and a statement body.  `std.Scope.vars` is a
`list[std.Bind]`, and the text printer derives `as ...` targets from the
variables inside those binds.  They inherit `attrs` from `std.Stmt` through
`std.Scope`.

### Binding Statements

`std.Bind` is an abstract base for statements that define variables.  It adds
the common field `vars: list[std.Var]` and inherits statement attributes from
`std.Stmt`.

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.BindExpr` | `vars`, `expr` | `std` | `BindExpr` | `__bind_expr__` |
| `std.BindVarDef` | `vars` | `std` | `BindVarDef` | `__bind_var_def__` |

Current text format:

```python
y = rhs
y = std.BindExpr(rhs, tag="demo")
y, z = rhs

y = std.BindVarDef(std.i32)
y = std.BindVarDef(std.i32, tag="demo")
y, z = std.BindVarDef(std.i32, std.bf16[3, 12])
```

For `std.BindExpr`, type annotations are not printed because the type is usually
derived from the right-hand side.  For `std.BindVarDef`, declared variable types are
printed as positional arguments to `std.BindVarDef(...)`.

If `std.BindExpr.vars` is empty, the expression is emitted as an expression
statement.  If `std.BindVarDef.vars` is empty, it emits `pass` when there are no
attributes, or a standalone `std.BindVarDef(**attrs)` when attributes are present.

### Other Statements

These nodes also inherit the keyword-only `attrs` field from `std.Stmt`, even
when the compact text form shown below does not surface attributes explicitly.

| Node | Fields | $dialect | $mnemonic | $generics |
|---|---|---:|---:|---|
| `std.Store` | `var`, `indices`, `rhs` | `std` | `Store` | `__store__` |
| `std.Assert` | `cond` | `std` | `Assert` | `__assert__` |
| `std.Return` | `vars` | `std` | `Return` | `__return__` |
| `std.Yield` | `vars` | `std` | `Yield` | `__yield__` |
| `std.Break` | none | `std` | `Break` | `__break__` |
| `std.Continue` | none | `std` | `Continue` | `__continue__` |

`std.Store` prints as indexed assignment, including `x[()] = v` when indices are
empty.  `std.Assert` prints as `assert cond` when no attributes are present, and
falls back to `std.Assert(cond, **attrs)` when statement attributes need to be
preserved.  `std.Return` and `std.Yield` support multiple variables.

## TIRx Dialect

The TIRx rows below are directional sketches for how a later dialect can
specialize the standard dialect.

### Types

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `tirx.PointerType` | `tirx` | `PointerType` | N/A | `std.Ty` |
| `tirx.FuncType` | `tirx` | `FuncType` | N/A | `std.Ty` |

### Variables

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `tirx.Var` | `tirx` | `Var` | N/A | `std.Var` |
| `tirx.SizeVar` | `tirx` | `SizeVar` | N/A | `tirx.Var` |
| `tirx.Buffer` | `tirx` | `Buffer` | N/A | `std.Var` |

### Expressions

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `tirx.Select` | `tirx` | `Select` | N/A | `std.Expr` |
| `tirx.Ramp` | `tirx` | `Ramp` | N/A | `std.Expr` |
| `tirx.Broadcast` | `tirx` | `Broadcast` | N/A | `std.Expr` |
| `tirx.Shuffle` | `tirx` | `Shuffle` | N/A | `std.Expr` |
| `tirx.BufferLoad` | `tirx` | `BufferLoad` | `__load__` | `std.Load` |
| `tirx.Call` | `tirx` | `Call` | `__call__` | `std.Call` |

### Statements

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `tirx.AttrStmt` | `tirx` | `AttrStmt` | N/A | `std.Scope` |
| `tirx.Bind` | `tirx` | `Bind` | N/A | `std.BindExpr` |
| `tirx.Assert` | `tirx` | `Assert` | `__assert__` | `std.Stmt` |
| `tirx.Store` | `tirx` | `Store` | `__store__` | `std.Store` |
| `tirx.DeclBuffer` | `tirx` | `DeclBuffer` | N/A | `std.BindVarDef` |
| `tirx.AllocBuffer` | `tirx` | `AllocBuffer` | N/A | `std.BindVarDef` |
| `tirx.Evaluate` | `tirx` | `Evaluate` | N/A | `std.Stmt` |
| `tirx.For` | `tirx` | `For` | N/A | `std.For` |
| `tirx.PrimFunc` | `tirx` | `PrimFunc` | N/A | `std.Func` |

## Relax Dialect

### Types

Relax struct info should be consolidated into `std.Ty`-like nodes.

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `relax.ShapeTy` | `relax` | `ShapeTy` | N/A | `std.Ty` |
| `relax.ObjectTy` | `relax` | `ObjectTy` | N/A | `std.Ty` |
| `relax.PackedFunc` | `relax` | `PackedFunc` | N/A | `std.Ty` |

### Expressions

| Node | $dialect | $mnemonic | $generics | $kind |
|---|---:|---:|---|---|
| `relax.TupleExpr` | `relax` | `TupleExpr` | N/A | `std.Expr` |
| `relax.ShapeExpr` | `relax` | `ShapeExpr` | N/A | `std.Expr` |
| `relax.Var` | `relax` | `Var` | N/A | `std.Var` |
| `relax.DataflowVar` | `relax` | `DataflowVar` | N/A | `relax.Var` |
| `relax.Constant` | `relax` | `Constant` | N/A | `std.Expr` |

## Dialect, Mnemonic, And Generics System

Every concrete IR node belongs to a `$dialect` and has a dialect-local
`$mnemonic`.  The fully qualified mnemonic is spelled as `{dialect}${name}`.
For example, `std.Add` has `$dialect = "std"` and `$mnemonic = "Add"`, whose
fully qualified spelling is `std$Add`.

`$generics` is separate from `$mnemonic`.  It is not a rendered text form; it is
an optional sugar identifier that says a node may participate in a syntax
family.  For example, `std.Add` has `$generics = "__add__"`, which lets a
printer or parser sugar `std.Add(a, b)` as `a + b` when that spelling is
unambiguous.

Generic identifiers are scoped by dialect.  Within a dialect, a generic
identifier should name at most one concrete operation, so the spelling produced
by a generic has a single meaning in that dialect.  The same generic identifier
may appear in multiple dialects.  For example, both `std` and `tirx` may define
`__load__`, but each dialect independently decides which concrete mnemonic that
generic denotes.

The three concepts have distinct roles:

- `$dialect` groups nodes by language, for example `std`, `tirx`, or `relax`.
- `$mnemonic` identifies a concrete node within its dialect, for example `Add`.
- `$generics` identifies optional sugar families, for example `__add__`.

Every concrete IR node should register a TypeAttrColumn entry for its dialect,
mnemonic, and optional generic.  The intended Python spelling is:

```python
class Add(Expr):
    __ffi_dialect_mnemonic__: ClassVar[tuple[str, str, str]] = ("std", "Add", "__add__")
```

The equivalent C++ registration should use `.def_type_attr(...)` on the object
definition:

```cpp
refl::ObjectDef<AddObj>()
    .def_type_attr(
        refl::type_attr::kDialectMnemonic,
        Array<String>{String("std"), String("Add"), String("__add__")});
```

The exact TypeAttrColumn name is `__ffi_dialect_mnemonic__`.  The C++ value is
`Array<String>`.  The Python value is either `tuple[str, str]` for non-generic
nodes or `tuple[str, str, str]` for nodes with a generic.  This metadata is not
a reflected field, so it is not part of structural equality, hashing,
serialization payloads, or constructor signatures.  Abstract base classes may
omit it; concrete IR nodes should define it.

This metadata is separate from the C++/Python type key.  A type key such as
`ffi.std.Add` remains the FFI runtime identity.  The `(dialect, mnemonic)` pair
is the IR-facing identity used by printers, parsers, sugar dispatch, and
cross-dialect reasoning.

Nodes without generic syntax use the two-element form:

```python
class Call(Expr):
    __ffi_dialect_mnemonic__: ClassVar[tuple[str, str]] = ("std", "Call")
```

The printer should maintain a dialect stack:

```python
dialects: list[str] = ["std"]
```

The top of the stack is the current dialect context.  When the printer enters a
new `std.Scope` subclass, it pushes the scope node's dialect, prints the scope
body, and pops the dialect when leaving the scope.  Nested scopes therefore use
the innermost dialect first.  The dialect is derived from the scope node's
`__ffi_dialect_mnemonic__` metadata.

Generic sugar should be applied only when it can be resolved without ambiguity.
For a node-specific text printer, the decision is:

1. Read the node's `$mnemonic`, `$dialect`, and optional `$generics`.
2. If the node has no `$generics`, use the ordinary callee spelling.
3. Collect the dialects of the node's non-literal operand nodes.  Literal
   immediates such as `std.IntImm`, `std.FloatImm`, and `std.StringImm` are
   ignored because they can appear in any dialect without changing the meaning
   of the sugar.
4. If the non-literal operands mention more than one dialect, do not sugar.
5. If there is exactly one non-literal operand dialect, use that as the sugar
   dialect.  If there are no non-literal operands, use the top of the printer's
   dialect stack.
6. Apply the generic only if that sugar dialect has a unique printer
   implementation for the node's `$generics`.  Otherwise, use the ordinary
   callee spelling.

This rule allows compact forms such as `a + b`, `x[i]`, and `return a, b` inside
a dialect where those generic spellings are known.  It also prevents ambiguous
mixed-dialect output.  For example, if an expression combines `std` and `tirx`
operands, the printer should fall back to an explicit callee instead of emitting
syntax that a parser could attach to either dialect.

`PrinterConfigObj` and `PrinterConfig` should gain a map that controls how
dialects and individual mnemonics are printed.  A tentative field name is:

```cpp
Dict<String, String> dialect_print_map;
```

Python should expose the same field as a mapping from `str` to `str`.

Keys may be either a dialect name or a fully qualified mnemonic:

| Key form | Example | Meaning |
|---|---|---|
| dialect | `std` | Applies to all nodes whose mnemonic starts with `std$` |
| full mnemonic | `Add` | Applies only to that concrete node |

Full-mnemonic entries take precedence over dialect entries.  If neither entry is
present, the printer uses the dialect name as the prefix.

Values define the printed callee name:

| Config entry | Meaning | Example unsugared output |
|---|---|---|
| `{ "std": "*" }` | Drop the `std` prefix for every std node | `Add(...)` |
| `{ "std": "core" }` | Print the `std` dialect as `core` | `core.Add(...)` |
| `{ "std$Add": "*" }` | Drop the prefix only for `Add` | `Add(...)` |
| `{ "std$Add": "std.MyAdd" }` | Print `Add` with an explicit full name | `std.MyAdd(...)` |

The `*` value means "print without a dialect/module prefix", not "use the
generic sugar".  Sugar selection still comes from `$generics` and the node's
registered text printer.  For example, a printer may still emit `a + b` for
`std$Add` because of `__add__`; if it falls back to call syntax, the
`dialect_print_map` decides whether that fallback is `std.Add(a, b)`,
`Add(a, b)`, `core.Add(a, b)`, or `std.MyAdd(a, b)`.
