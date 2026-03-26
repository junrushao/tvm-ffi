/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
/*\!
 * \file tvm/ffi/text/ast.h
 * \brief Text format AST node types for Python-style pretty-printing.
 *
 * Defines the expression and statement node hierarchy used by the text
 * printer. Nodes can be rendered to Python source via DocToPythonScript.
 */
#ifndef TVM_FFI_TEXT_AST_H_
#define TVM_FFI_TEXT_AST_H_

#include <tvm/ffi/any.h>
#include <tvm/ffi/container/dict.h>
#include <tvm/ffi/container/list.h>
#include <tvm/ffi/extra/base.h>
#include <tvm/ffi/function.h>
#include <tvm/ffi/object.h>
#include <tvm/ffi/optional.h>
#include <tvm/ffi/reflection/access_path.h>
#include <tvm/ffi/string.h>

namespace tvm {
namespace ffi {
namespace text {

using AccessPath = ::tvm::ffi::reflection::AccessPath;

// Forward declaration — full definition is in tvm/ffi/text/printer.h.
struct PrinterConfigObj;
struct PrinterConfig;

/************** NodeAST **************/

/*!
 * \brief Base data object for all text AST nodes.
 *
 * Every node in the text format AST inherits from NodeASTObj. It carries
 * a list of source access paths that trace which IR fields produced this
 * node, enabling underline highlighting in the rendered output.
 *
 * \code{.cpp}
 * // Typically not constructed directly; use ExprAST or StmtAST subtypes.
 * // Render any node to Python text:
 * NodeAST node = IdAST("x");
 * String code = node->ToPython(PrinterConfig());
 * \endcode
 *
 * \sa NodeAST, ExprASTObj, StmtASTObj
 */
struct NodeASTObj : public Object {
  /*!
   * \brief Access paths tracing this node back to the original IR structure.
   *
   * Populated by IRPrinter during dispatch. Typically empty for manually
   * constructed AST nodes. Used by the renderer to decide which text
   * regions to underline when path_to_underline is set in PrinterConfig.
   */
  List<AccessPath> source_paths;
  /// \cond Doxygen_Suppress
  explicit NodeASTObj(List<AccessPath> source_paths) : source_paths(std::move(source_paths)) {}
  /// \endcond
  /*!
   * \brief Render this AST node to Python-style source code.
   *
   * Delegates to DocToPythonScript to produce a Python-style text
   * representation of this node and all its children.
   *
   * \param cfg Printer configuration controlling indentation, line numbers,
   *        and underline highlighting.
   * \return The rendered Python-style source code as a String.
   *
   * \code{.cpp}
   * NodeAST node = IdAST("x");
   * String code = node->ToPython(PrinterConfig());
   * // code == "x"
   * \endcode
   */
  String ToPython(const PrinterConfig& cfg) const;
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.text.ast.Node", NodeASTObj, Object);
  /// \endcond
};

/*!
 * \brief Nullable reference to a NodeASTObj.
 *
 * Root reference type for the text format AST. All expression and statement
 * AST references derive from this. Can be rendered to a Python-style
 * string via DocToPythonScript.
 *
 * \code{.cpp}
 * NodeAST node = LiteralAST::Int(42);
 * String code = DocToPythonScript(node, PrinterConfig());
 * \endcode
 *
 * \sa NodeASTObj
 */
struct NodeAST : public ObjectRef {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(NodeAST, ObjectRef, NodeASTObj);
  /// \endcond
};

/************** ExprAST **************/

struct ExprAST;

/*!
 * \brief Base data object for all expression AST nodes.
 *
 * Represents a Python-style expression in the text format AST. Concrete
 * subtypes include literals, identifiers, attribute accesses, calls,
 * operations, tuples, lists, dicts, and slices.
 *
 * Expression nodes can be composed using the free-function builders
 * ExprAttr, ExprIndex, ExprCall, and ExprCallKw to form complex
 * expressions.
 *
 * \code{.cpp}
 * // Build: my_func(x, y).result
 * ExprAST callee = IdAST("my_func");
 * ExprAST call = ExprCall(callee, {IdAST("x"), IdAST("y")});
 * ExprAST attr = ExprAttr(call, "result");
 * // Renders as: my_func(x, y).result
 * \endcode
 *
 * \sa ExprAST, LiteralASTObj, IdASTObj, CallASTObj
 */
struct ExprASTObj : public NodeASTObj {
  /// \cond Doxygen_Suppress
  explicit ExprASTObj(List<AccessPath> source_paths) : NodeASTObj(std::move(source_paths)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.text.ast.Expr", ExprASTObj, NodeASTObj);
  /// \endcond
};

/*!
 * \brief Nullable reference to an ExprASTObj.
 *
 * Provides the AddPath helper for appending source-tracking metadata
 * and serves as the common handle for all expression AST nodes.
 * Convenience builders ExprAttr, ExprIndex, ExprCall, and ExprCallKw
 * are provided as free functions.
 *
 * \code{.cpp}
 * ExprAST expr = IdAST("x");
 * // Chain an attribute access: x.shape
 * ExprAST attr = ExprAttr(expr, "shape");
 * \endcode
 *
 * \sa ExprASTObj
 */
struct ExprAST : public NodeAST {
  /*!
   * \brief Append an access path to this expression's source_paths and return *this.
   *
   * Enables fluent chaining when building expressions with traceability.
   *
   * \param p The access path to append, linking this node to an IR field.
   * \return A reference to *this, allowing method chaining.
   *
   * \code{.cpp}
   * ExprAST expr = IdAST("x");
   * expr.AddPath(AccessPath::Root());
   * \endcode
   */
  ExprAST AddPath(const AccessPath& p) {
    const_cast<ExprASTObj*>(get())->source_paths.push_back(p);
    return *this;
  }
  // Convenience builders: Attr, Index, Call, CallKw — defined as free functions below.
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(ExprAST, NodeAST, ExprASTObj);
  /// \endcond
};

/************** StmtAST **************/

/*!
 * \brief Base data object for all statement AST nodes.
 *
 * Represents a Python-style statement in the text format AST. Each statement
 * may carry an optional inline comment. Concrete subtypes include
 * assignments, if/while/for blocks, function/class definitions, and more.
 *
 * \code{.cpp}
 * // Build: x = 42  # initial value
 * StmtAST stmt = AssignAST(
 *     {}, String("initial value"),
 *     IdAST("x"), LiteralAST::Int(42), NullOpt);
 * \endcode
 *
 * \sa StmtAST, AssignASTObj, IfASTObj, FunctionASTObj
 */
struct StmtASTObj : public NodeASTObj {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  /// \endcond
  /*!
   * \brief Optional inline or block comment text.
   *
   * When set, the comment is rendered after the statement on the same line
   * (e.g. `x = 42  # initial value`). Null means no comment.
   */
  Optional<String> comment;
  /// \cond Doxygen_Suppress
  explicit StmtASTObj(List<AccessPath> source_paths, Optional<String> comment)
      : NodeASTObj(std::move(source_paths)), comment(std::move(comment)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.text.ast.Stmt", StmtASTObj, NodeASTObj);
  /// \endcond
};

/*! \brief Nullable reference to a StmtASTObj. */
struct StmtAST : public NodeAST {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(StmtAST, NodeAST, StmtASTObj);
  /// \endcond
};

/************** StmtBlockAST **************/

/*!
 * \brief Data object for a block of sequential statements.
 *
 * Groups multiple statements into a single renderable unit. Used as
 * the top-level container when rendering a complete program or module.
 *
 * \code{.cpp}
 * // Build a block of two statements:
 * StmtBlockAST block({
 *     AssignAST(IdAST("x"), LiteralAST::Int(1)),
 *     AssignAST(IdAST("y"), LiteralAST::Int(2)),
 * });
 * \endcode
 *
 * \sa StmtBlockAST
 */
struct StmtBlockASTObj : public StmtASTObj {
  /*! \brief The list of statements. */
  List<StmtAST> stmts;
  /// \cond Doxygen_Suppress
  explicit StmtBlockASTObj(List<StmtAST> stmts)
      : StmtBlockASTObj(List<AccessPath>{}, Optional<String>{}, std::move(stmts)) {}
  explicit StmtBlockASTObj(List<AccessPath> source_paths, Optional<String> comment,
                           List<StmtAST> stmts)
      : StmtASTObj(std::move(source_paths), std::move(comment)), stmts(std::move(stmts)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.StmtBlock", StmtBlockASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a block of sequential statements. */
struct StmtBlockAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit StmtBlockAST(List<StmtAST> stmts)
      : StmtBlockAST(List<AccessPath>{}, Optional<String>{}, std::move(stmts)) {}
  explicit StmtBlockAST(List<AccessPath> source_paths, Optional<String> comment,
                        List<StmtAST> stmts)
      : StmtBlockAST(make_object<StmtBlockASTObj>(std::move(source_paths), std::move(comment),
                                                  std::move(stmts))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(StmtBlockAST, StmtAST, StmtBlockASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit StmtBlockAST(ObjectPtr<StmtBlockASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** LiteralAST **************/

/*!
 * \brief Data object for a literal value expression (int, float, string, bool, null).
 *
 * Wraps a type-erased Any value that will be rendered as its Python literal
 * representation (e.g. 42, 3.14, "hello", True, None).
 *
 * \code{.cpp}
 * auto lit_int = LiteralAST::Int(42);
 * auto lit_str = LiteralAST::Str("hello");
 * auto lit_none = LiteralAST::Null();
 * \endcode
 *
 * \sa LiteralAST
 */
struct LiteralASTObj : public ExprASTObj {
  /*! \brief The literal value (bool, int, float, string, or null). */
  Any value;
  /// \cond Doxygen_Suppress
  explicit LiteralASTObj(Any value) : LiteralASTObj(List<AccessPath>{}, std::move(value)) {}
  explicit LiteralASTObj(List<AccessPath> source_paths, Any value)
      : ExprASTObj(std::move(source_paths)), value(std::move(value)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Literal", LiteralASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a literal value expression.
 *
 * Provides static factory methods for common literal types: Bool, Int,
 * Str, Float, and Null. Each factory creates a fully constructed literal
 * node ready for insertion into the text format AST.
 *
 * \code{.cpp}
 * LiteralAST answer = LiteralAST::Int(42);
 * LiteralAST pi = LiteralAST::Float(3.14159);
 * LiteralAST name = LiteralAST::Str("world");
 * LiteralAST flag = LiteralAST::Bool(true);
 * LiteralAST nothing = LiteralAST::Null();
 * \endcode
 *
 * \sa LiteralASTObj
 */
struct LiteralAST : public ExprAST {
  /*!
   * \brief Create a bool literal.
   * \param value The boolean value (renders as `True` or `False`).
   * \param source_paths Optional access paths for IR traceability.
   * \return A LiteralAST wrapping the bool value.
   *
   * \code{.cpp}
   * LiteralAST flag = LiteralAST::Bool(true);
   * // Renders as: True
   * \endcode
   */
  static LiteralAST Bool(bool value, List<AccessPath> source_paths = {}) {
    return LiteralAST(std::move(source_paths), Any(value));
  }
  /*!
   * \brief Create an integer literal.
   * \param value The 64-bit integer value (renders as a decimal, e.g. `42`).
   * \param source_paths Optional access paths for IR traceability.
   * \return A LiteralAST wrapping the int value.
   *
   * \code{.cpp}
   * LiteralAST answer = LiteralAST::Int(42);
   * // Renders as: 42
   * \endcode
   */
  static LiteralAST Int(int64_t value, List<AccessPath> source_paths = {}) {
    return LiteralAST(std::move(source_paths), Any(value));
  }
  /*!
   * \brief Create a string literal.
   * \param value The string content (rendered with quotes, e.g. `"hello"`).
   * \param source_paths Optional access paths for IR traceability.
   * \return A LiteralAST wrapping the string value.
   *
   * \code{.cpp}
   * LiteralAST greeting = LiteralAST::Str("hello");
   * // Renders as: "hello"
   * \endcode
   */
  static LiteralAST Str(String value, List<AccessPath> source_paths = {}) {
    return LiteralAST(std::move(source_paths), Any(std::move(value)));
  }
  /*!
   * \brief Create a floating-point literal.
   * \param value The double-precision float value (e.g. `3.14`).
   * \param source_paths Optional access paths for IR traceability.
   * \return A LiteralAST wrapping the float value.
   *
   * \code{.cpp}
   * LiteralAST pi = LiteralAST::Float(3.14159);
   * // Renders as: 3.14159
   * \endcode
   */
  static LiteralAST Float(double value, List<AccessPath> source_paths = {}) {
    return LiteralAST(std::move(source_paths), Any(value));
  }
  /*!
   * \brief Create a null literal (renders as `None`).
   * \param source_paths Optional access paths for IR traceability.
   * \return A LiteralAST representing Python's None.
   *
   * \code{.cpp}
   * LiteralAST nothing = LiteralAST::Null();
   * // Renders as: None
   * \endcode
   */
  static LiteralAST Null(List<AccessPath> source_paths = {}) {
    return LiteralAST(std::move(source_paths), Any());
  }
  /// \cond Doxygen_Suppress
  explicit LiteralAST(Any value) : LiteralAST(List<AccessPath>{}, std::move(value)) {}
  explicit LiteralAST(List<AccessPath> source_paths, Any value)
      : LiteralAST(make_object<LiteralASTObj>(std::move(source_paths), std::move(value))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(LiteralAST, ExprAST, LiteralASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit LiteralAST(ObjectPtr<LiteralASTObj> ptr)
      : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** IdAST **************/

/*!
 * \brief Data object for an identifier expression (variable or name reference).
 *
 * Holds the string name of the identifier as it will appear in the
 * rendered Python-style output.
 *
 * \code{.cpp}
 * auto id = IdAST("my_var");
 * // Renders as: my_var
 * \endcode
 *
 * \sa IdAST
 */
struct IdASTObj : public ExprASTObj {
  /*! \brief The identifier name. */
  String name;
  /// \cond Doxygen_Suppress
  explicit IdASTObj(String name) : IdASTObj(List<AccessPath>{}, std::move(name)) {}
  explicit IdASTObj(List<AccessPath> source_paths, String name)
      : ExprASTObj(std::move(source_paths)), name(std::move(name)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Id", IdASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for an identifier expression.
 *
 * Can be constructed from a name string alone (no source paths) or
 * with explicit source paths for traceability.
 *
 * \code{.cpp}
 * IdAST x("x");
 * IdAST y({}, "y");  // with explicit empty source paths
 * \endcode
 *
 * \sa IdASTObj
 */
struct IdAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit IdAST(List<AccessPath> source_paths, String name)
      : IdAST(make_object<IdASTObj>(std::move(source_paths), std::move(name))) {}
  explicit IdAST(String name) : IdAST({}, std::move(name)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(IdAST, ExprAST, IdASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit IdAST(ObjectPtr<IdASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** AttrAST **************/

/*!
 * \brief Data object for an attribute access expression (e.g. `obj.name`).
 *
 * Represents the Python construct `obj.name` in the text format AST.
 *
 * \code{.cpp}
 * // Build: tensor.shape
 * AttrAST attr({}, IdAST("tensor"), "shape");
 * // Or use the convenience builder:
 * ExprAST attr2 = ExprAttr(IdAST("tensor"), "shape");
 * \endcode
 *
 * \sa AttrAST, ExprAttr
 */
struct AttrASTObj : public ExprASTObj {
  /*! \brief The target expression being accessed (e.g. `tensor` in `tensor.shape`). */
  ExprAST obj;
  /*! \brief The attribute name (e.g. `"shape"` in `tensor.shape`). */
  String name;
  /// \cond Doxygen_Suppress
  explicit AttrASTObj(ExprAST obj, String name)
      : AttrASTObj(List<AccessPath>{}, std::move(obj), std::move(name)) {}
  explicit AttrASTObj(List<AccessPath> source_paths, ExprAST obj, String name)
      : ExprASTObj(std::move(source_paths)), obj(std::move(obj)), name(std::move(name)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Attr", AttrASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for an attribute access expression (e.g. `obj.name`).
 *
 * \code{.cpp}
 * AttrAST attr(IdAST("module"), "func");
 * // Renders as: module.func
 * \endcode
 *
 * \sa AttrASTObj, ExprAttr
 */
struct AttrAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit AttrAST(ExprAST obj, String name)
      : AttrAST(List<AccessPath>{}, std::move(obj), std::move(name)) {}
  explicit AttrAST(List<AccessPath> source_paths, ExprAST obj, String name)
      : AttrAST(make_object<AttrASTObj>(std::move(source_paths), std::move(obj), std::move(name))) {
  }
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(AttrAST, ExprAST, AttrASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit AttrAST(ObjectPtr<AttrASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** IndexAST **************/

/*!
 * \brief Data object for an index/subscript expression (e.g. `obj[idx]`).
 *
 * Represents the Python construct `obj[idx]` in the text format AST.
 * Supports multiple index expressions for multi-dimensional subscripts.
 *
 * \code{.cpp}
 * // Build: data[0]
 * IndexAST idx(IdAST("data"), {LiteralAST::Int(0)});
 * // Or use the convenience builder:
 * ExprAST idx2 = ExprIndex(IdAST("data"), {LiteralAST::Int(0)});
 * \endcode
 *
 * \sa IndexAST, ExprIndex
 */
struct IndexASTObj : public ExprASTObj {
  /*! \brief The target expression being indexed. */
  ExprAST obj;
  /*! \brief The index expressions. */
  List<ExprAST> idx;
  /// \cond Doxygen_Suppress
  explicit IndexASTObj(ExprAST obj, List<ExprAST> idx)
      : IndexASTObj(List<AccessPath>{}, std::move(obj), std::move(idx)) {}
  explicit IndexASTObj(List<AccessPath> source_paths, ExprAST obj, List<ExprAST> idx)
      : ExprASTObj(std::move(source_paths)), obj(std::move(obj)), idx(std::move(idx)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Index", IndexASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for an index/subscript expression (e.g. `obj[idx]`).
 *
 * \code{.cpp}
 * IndexAST idx(IdAST("arr"), {LiteralAST::Int(0)});
 * // Renders as: arr[0]
 * \endcode
 *
 * \sa IndexASTObj, ExprIndex
 */
struct IndexAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit IndexAST(ExprAST obj, List<ExprAST> idx)
      : IndexAST(List<AccessPath>{}, std::move(obj), std::move(idx)) {}
  explicit IndexAST(List<AccessPath> source_paths, ExprAST obj, List<ExprAST> idx)
      : IndexAST(
            make_object<IndexASTObj>(std::move(source_paths), std::move(obj), std::move(idx))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(IndexAST, ExprAST, IndexASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit IndexAST(ObjectPtr<IndexASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** CallAST **************/

/*!
 * \brief Data object for a function call expression with positional and keyword arguments.
 *
 * Represents the Python construct `callee(args..., key=value...)` in the
 * text format AST. Keyword arguments are stored as parallel lists of keys
 * and values.
 *
 * \code{.cpp}
 * // Build: alloc(shape, dtype="float32")
 * CallAST call(
 *     IdAST("alloc"),
 *     {IdAST("shape")},             // positional args
 *     {String("dtype")},            // kwarg keys
 *     {LiteralAST::Str("float32")} // kwarg values
 * );
 * \endcode
 *
 * \sa CallAST, ExprCall, ExprCallKw
 */
struct CallASTObj : public ExprASTObj {
  /*! \brief The callee expression (e.g. `alloc` in `alloc(shape)`). */
  ExprAST callee;
  /*! \brief Positional argument expressions. */
  List<ExprAST> args;
  /*! \brief Keyword argument names, parallel to kwargs_values (e.g. `{"dtype"}`). */
  List<String> kwargs_keys;
  /*! \brief Keyword argument value expressions, parallel to kwargs_keys. */
  List<ExprAST> kwargs_values;
  /// \cond Doxygen_Suppress
  explicit CallASTObj(ExprAST callee, List<ExprAST> args, List<String> kwargs_keys,
                      List<ExprAST> kwargs_values)
      : CallASTObj(List<AccessPath>{}, std::move(callee), std::move(args), std::move(kwargs_keys),
                   std::move(kwargs_values)) {}
  explicit CallASTObj(List<AccessPath> source_paths, ExprAST callee, List<ExprAST> args,
                      List<String> kwargs_keys, List<ExprAST> kwargs_values)
      : ExprASTObj(std::move(source_paths)),
        callee(std::move(callee)),
        args(std::move(args)),
        kwargs_keys(std::move(kwargs_keys)),
        kwargs_values(std::move(kwargs_values)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Call", CallASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a function call expression.
 *
 * \code{.cpp}
 * // Build: print("hello", end="")
 * CallAST call(
 *     IdAST("print"),
 *     {LiteralAST::Str("hello")},
 *     {String("end")},
 *     {LiteralAST::Str("")}
 * );
 * \endcode
 *
 * \sa CallASTObj, ExprCall, ExprCallKw
 */
struct CallAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit CallAST(ExprAST callee, List<ExprAST> args, List<String> kwargs_keys,
                   List<ExprAST> kwargs_values)
      : CallAST(List<AccessPath>{}, std::move(callee), std::move(args), std::move(kwargs_keys),
                std::move(kwargs_values)) {}
  explicit CallAST(List<AccessPath> source_paths, ExprAST callee, List<ExprAST> args,
                   List<String> kwargs_keys, List<ExprAST> kwargs_values)
      : CallAST(make_object<CallASTObj>(std::move(source_paths), std::move(callee), std::move(args),
                                        std::move(kwargs_keys), std::move(kwargs_values))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(CallAST, ExprAST, CallASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit CallAST(ObjectPtr<CallASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** OperationAST **************/

/*!
 * \brief Data object for a unary, binary, or special operation expression.
 *
 * Represents Python operators in the text format AST. The `op` field
 * selects the operator kind, and `operands` holds 1, 2, or 3 sub-expressions
 * depending on the operator arity.
 *
 * \code{.cpp}
 * // Build: x + 1
 * OperationAST add(
 *     OperationASTObj::kAdd,
 *     {IdAST("x"), LiteralAST::Int(1)}
 * );
 * // Build: -x  (unary negation)
 * OperationAST neg(OperationASTObj::kUSub, {IdAST("x")});
 * // Build: a if cond else b  (ternary)
 * OperationAST ternary(
 *     OperationASTObj::kIfThenElse,
 *     {IdAST("a"), IdAST("cond"), IdAST("b")}
 * );
 * \endcode
 *
 * \sa OperationAST
 */
struct OperationASTObj : public ExprASTObj {
  /*!
   * \brief Enumeration of unary, binary, and special operation kinds.
   *
   * Values are grouped into three ranges:
   * - **Unary** (kUnaryStart..kUnaryEnd): kUSub (`-x`), kInvert (`~x`), kNot (`not x`).
   *   Takes 1 operand.
   * - **Binary** (kBinaryStart..kBinaryEnd): arithmetic (kAdd, kSub, kMult, kDiv,
   *   kFloorDiv, kMod, kPow), bitwise (kLShift, kRShift, kBitAnd, kBitOr, kBitXor),
   *   comparison (kLt, kLtE, kEq, kNotEq, kGt, kGtE), and logical (kAnd, kOr).
   *   Takes 2 operands.
   * - **Special** (kSpecialStart..kSpecialEnd): kIfThenElse (`a if cond else b`).
   *   Takes 3 operands: [true_value, condition, false_value].
   */
  enum Kind : int64_t {
    kUnaryStart = 0,    /*!< \brief Sentinel: start of unary operators. */
    kUSub = 1,          /*!< \brief Unary minus: `-x`. */
    kInvert = 2,        /*!< \brief Bitwise invert: `~x`. */
    kNot = 3,           /*!< \brief Logical not: `not x`. */
    kUnaryEnd = 4,      /*!< \brief Sentinel: end of unary operators. */
    kBinaryStart = 5,   /*!< \brief Sentinel: start of binary operators. */
    kAdd = 6,           /*!< \brief Addition: `x + y`. */
    kSub = 7,           /*!< \brief Subtraction: `x - y`. */
    kMult = 8,          /*!< \brief Multiplication: `x * y`. */
    kDiv = 9,           /*!< \brief True division: `x / y`. */
    kFloorDiv = 10,     /*!< \brief Floor division: `x // y`. */
    kMod = 11,          /*!< \brief Modulo: `x % y`. */
    kPow = 12,          /*!< \brief Exponentiation: `x ** y`. */
    kLShift = 13,       /*!< \brief Left shift: `x << y`. */
    kRShift = 14,       /*!< \brief Right shift: `x >> y`. */
    kBitAnd = 15,       /*!< \brief Bitwise AND: `x & y`. */
    kBitOr = 16,        /*!< \brief Bitwise OR: `x | y`. */
    kBitXor = 17,       /*!< \brief Bitwise XOR: `x ^ y`. */
    kLt = 18,           /*!< \brief Less than: `x < y`. */
    kLtE = 19,          /*!< \brief Less than or equal: `x <= y`. */
    kEq = 20,           /*!< \brief Equal: `x == y`. */
    kNotEq = 21,        /*!< \brief Not equal: `x != y`. */
    kGt = 22,           /*!< \brief Greater than: `x > y`. */
    kGtE = 23,          /*!< \brief Greater than or equal: `x >= y`. */
    kAnd = 24,          /*!< \brief Logical AND: `x and y`. */
    kOr = 25,           /*!< \brief Logical OR: `x or y`. */
    kBinaryEnd = 26,    /*!< \brief Sentinel: end of binary operators. */
    kSpecialStart = 27, /*!< \brief Sentinel: start of special operators. */
    kIfThenElse = 28,   /*!< \brief Ternary: `a if cond else b`. */
    kSpecialEnd = 29,   /*!< \brief Sentinel: end of special operators. */
  };

  /*!
   * \brief The operation kind, storing a value from the Kind enum.
   *
   * Use one of the Kind enum values (e.g. `OperationASTObj::kAdd`,
   * `OperationASTObj::kUSub`, `OperationASTObj::kIfThenElse`).
   */
  int64_t op;
  /*! \brief The operand expressions (1 for unary, 2 for binary, 3 for ternary). */
  List<ExprAST> operands;
  /// \cond Doxygen_Suppress
  explicit OperationASTObj(int64_t op, List<ExprAST> operands)
      : OperationASTObj(List<AccessPath>{}, op, std::move(operands)) {}
  explicit OperationASTObj(List<AccessPath> source_paths, int64_t op, List<ExprAST> operands)
      : ExprASTObj(std::move(source_paths)), op(op), operands(std::move(operands)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Operation", OperationASTObj, ExprASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a unary, binary, or special operation expression.
 *
 * \code{.cpp}
 * // Build: a * b + c
 * OperationAST mul(OperationASTObj::kMult, {IdAST("a"), IdAST("b")});
 * OperationAST add(OperationASTObj::kAdd, {mul, IdAST("c")});
 * \endcode
 *
 * \sa OperationASTObj
 */
struct OperationAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit OperationAST(int64_t op, List<ExprAST> operands)
      : OperationAST(List<AccessPath>{}, op, std::move(operands)) {}
  explicit OperationAST(List<AccessPath> source_paths, int64_t op, List<ExprAST> operands)
      : OperationAST(
            make_object<OperationASTObj>(std::move(source_paths), op, std::move(operands))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(OperationAST, ExprAST, OperationASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit OperationAST(ObjectPtr<OperationASTObj> ptr)
      : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** LambdaAST **************/

/*!
 * \brief Data object for a lambda expression (e.g. `lambda x, y: x + y`).
 *
 * Represents a Python lambda expression in the text format AST.
 *
 * \code{.cpp}
 * // Build: lambda x, y: x + y
 * LambdaAST lam(
 *     {IdAST("x"), IdAST("y")},
 *     OperationAST(OperationASTObj::kAdd, {IdAST("x"), IdAST("y")})
 * );
 * \endcode
 *
 * \sa LambdaAST
 */
struct LambdaASTObj : public ExprASTObj {
  /*! \brief The argument list. */
  List<IdAST> args;
  /*! \brief The lambda body expression. */
  ExprAST body;
  /// \cond Doxygen_Suppress
  explicit LambdaASTObj(List<IdAST> args, ExprAST body)
      : LambdaASTObj(List<AccessPath>{}, std::move(args), std::move(body)) {}
  explicit LambdaASTObj(List<AccessPath> source_paths, List<IdAST> args, ExprAST body)
      : ExprASTObj(std::move(source_paths)), args(std::move(args)), body(std::move(body)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Lambda", LambdaASTObj, ExprASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a lambda expression. */
struct LambdaAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit LambdaAST(List<IdAST> args, ExprAST body)
      : LambdaAST(List<AccessPath>{}, std::move(args), std::move(body)) {}
  explicit LambdaAST(List<AccessPath> source_paths, List<IdAST> args, ExprAST body)
      : LambdaAST(
            make_object<LambdaASTObj>(std::move(source_paths), std::move(args), std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(LambdaAST, ExprAST, LambdaASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit LambdaAST(ObjectPtr<LambdaASTObj> ptr)
      : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** TupleAST **************/

/*!
 * \brief Data object for a tuple expression (e.g. `(a, b, c)`).
 *
 * Represents a Python tuple literal in the text format AST.
 *
 * \code{.cpp}
 * // Build: (1, 2, 3)
 * TupleAST tup({LiteralAST::Int(1), LiteralAST::Int(2), LiteralAST::Int(3)});
 * \endcode
 *
 * \sa TupleAST
 */
struct TupleASTObj : public ExprASTObj {
  /*! \brief The contained values. */
  List<ExprAST> values;
  /// \cond Doxygen_Suppress
  explicit TupleASTObj(List<ExprAST> values) : TupleASTObj(List<AccessPath>{}, std::move(values)) {}
  explicit TupleASTObj(List<AccessPath> source_paths, List<ExprAST> values)
      : ExprASTObj(std::move(source_paths)), values(std::move(values)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Tuple", TupleASTObj, ExprASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a tuple expression. */
struct TupleAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit TupleAST(List<ExprAST> values) : TupleAST(List<AccessPath>{}, std::move(values)) {}
  explicit TupleAST(List<AccessPath> source_paths, List<ExprAST> values)
      : TupleAST(make_object<TupleASTObj>(std::move(source_paths), std::move(values))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(TupleAST, ExprAST, TupleASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit TupleAST(ObjectPtr<TupleASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** ListAST **************/

/*!
 * \brief Data object for a list expression (e.g. `[a, b, c]`).
 *
 * Represents a Python list literal in the text format AST.
 *
 * \code{.cpp}
 * // Build: [1, 2, 3]
 * ListAST lst({LiteralAST::Int(1), LiteralAST::Int(2), LiteralAST::Int(3)});
 * \endcode
 *
 * \sa ListAST
 */
struct ListASTObj : public ExprASTObj {
  /*! \brief The contained values. */
  List<ExprAST> values;
  /// \cond Doxygen_Suppress
  explicit ListASTObj(List<ExprAST> values) : ListASTObj(List<AccessPath>{}, std::move(values)) {}
  explicit ListASTObj(List<AccessPath> source_paths, List<ExprAST> values)
      : ExprASTObj(std::move(source_paths)), values(std::move(values)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.List", ListASTObj, ExprASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a list expression. */
struct ListAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit ListAST(List<ExprAST> values) : ListAST(List<AccessPath>{}, std::move(values)) {}
  explicit ListAST(List<AccessPath> source_paths, List<ExprAST> values)
      : ListAST(make_object<ListASTObj>(std::move(source_paths), std::move(values))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(ListAST, ExprAST, ListASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit ListAST(ObjectPtr<ListASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** DictAST **************/

/*!
 * \brief Data object for a dictionary expression (e.g. `{k1: v1, k2: v2}`).
 *
 * Represents a Python dict literal in the text format AST. Keys and
 * values are stored as parallel lists.
 *
 * \code{.cpp}
 * // Build: {"x": 1, "y": 2}
 * DictAST d(
 *     {LiteralAST::Str("x"), LiteralAST::Str("y")},
 *     {LiteralAST::Int(1), LiteralAST::Int(2)}
 * );
 * \endcode
 *
 * \sa DictAST
 */
struct DictASTObj : public ExprASTObj {
  /*! \brief The key expressions (parallel to values). */
  List<ExprAST> keys;
  /*! \brief The value expressions (parallel to keys). */
  List<ExprAST> values;
  /// \cond Doxygen_Suppress
  explicit DictASTObj(List<ExprAST> keys, List<ExprAST> values)
      : DictASTObj(List<AccessPath>{}, std::move(keys), std::move(values)) {}
  explicit DictASTObj(List<AccessPath> source_paths, List<ExprAST> keys, List<ExprAST> values)
      : ExprASTObj(std::move(source_paths)), keys(std::move(keys)), values(std::move(values)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Dict", DictASTObj, ExprASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a dictionary expression. */
struct DictAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit DictAST(List<ExprAST> keys, List<ExprAST> values)
      : DictAST(List<AccessPath>{}, std::move(keys), std::move(values)) {}
  explicit DictAST(List<AccessPath> source_paths, List<ExprAST> keys, List<ExprAST> values)
      : DictAST(
            make_object<DictASTObj>(std::move(source_paths), std::move(keys), std::move(values))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(DictAST, ExprAST, DictASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit DictAST(ObjectPtr<DictASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** SliceAST **************/

/*!
 * \brief Data object for a slice expression (e.g. `start:stop:step`).
 *
 * Represents a Python slice in the text format AST, typically used
 * inside an IndexAST. Each of start, stop, and step is optional.
 *
 * \code{.cpp}
 * // Build: 0:10:2  (used inside obj[0:10:2])
 * SliceAST slc(LiteralAST::Int(0), LiteralAST::Int(10), LiteralAST::Int(2));
 * // Build: :5  (start omitted)
 * SliceAST slc2(NullOpt, LiteralAST::Int(5), NullOpt);
 * \endcode
 *
 * \sa SliceAST
 */
struct SliceASTObj : public ExprASTObj {
  /*! \brief The start expression, or null if omitted (e.g. `:5` has no start). */
  Optional<ExprAST> start;
  /*! \brief The stop expression, or null if omitted (e.g. `1:` has no stop). */
  Optional<ExprAST> stop;
  /*! \brief The step expression, or null if omitted (e.g. `1:5` has no step). */
  Optional<ExprAST> step;
  /// \cond Doxygen_Suppress
  explicit SliceASTObj(Optional<ExprAST> start = {}, Optional<ExprAST> stop = {},
                       Optional<ExprAST> step = {})
      : SliceASTObj(List<AccessPath>{}, std::move(start), std::move(stop), std::move(step)) {}
  explicit SliceASTObj(List<AccessPath> source_paths, Optional<ExprAST> start,
                       Optional<ExprAST> stop, Optional<ExprAST> step)
      : ExprASTObj(std::move(source_paths)),
        start(std::move(start)),
        stop(std::move(stop)),
        step(std::move(step)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Slice", SliceASTObj, ExprASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a slice expression. */
struct SliceAST : public ExprAST {
  /// \cond Doxygen_Suppress
  explicit SliceAST(Optional<ExprAST> start = {}, Optional<ExprAST> stop = {},
                    Optional<ExprAST> step = {})
      : SliceAST(List<AccessPath>{}, std::move(start), std::move(stop), std::move(step)) {}
  explicit SliceAST(List<AccessPath> source_paths, Optional<ExprAST> start, Optional<ExprAST> stop,
                    Optional<ExprAST> step)
      : SliceAST(make_object<SliceASTObj>(std::move(source_paths), std::move(start),
                                          std::move(stop), std::move(step))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(SliceAST, ExprAST, SliceASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit SliceAST(ObjectPtr<SliceASTObj> ptr) : ExprAST(ObjectPtr<ExprASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** AssignAST **************/

/*!
 * \brief Data object for an assignment statement (e.g. `lhs = rhs` or `lhs: annotation = rhs`).
 *
 * Represents the Python construct `lhs = rhs` with an optional type
 * annotation. When used for function arguments in FunctionAST, only
 * lhs (parameter name) and annotation (type hint) are set, with no rhs.
 *
 * \code{.cpp}
 * // Build: x: int = 42
 * AssignAST assign(
 *     {}, String("initial value"),
 *     IdAST("x"), LiteralAST::Int(42), IdAST("int")
 * );
 * // Renders as: x: int = 42  # initial value
 * \endcode
 *
 * \sa AssignAST
 */
struct AssignASTObj : public StmtASTObj {
  /*! \brief The left-hand side expression (e.g. `x` in `x = 42`). */
  ExprAST lhs;
  /*! \brief The right-hand side expression (e.g. `42` in `x = 42`), or null for declarations. */
  Optional<ExprAST> rhs;
  /*! \brief Optional type annotation (e.g. `int` in `x: int = 42`). */
  Optional<ExprAST> annotation;
  /// \cond Doxygen_Suppress
  explicit AssignASTObj(ExprAST lhs, Optional<ExprAST> rhs = {}, Optional<ExprAST> annotation = {})
      : AssignASTObj(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
                     std::move(annotation)) {}
  explicit AssignASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST lhs,
                        Optional<ExprAST> rhs, Optional<ExprAST> annotation)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        lhs(std::move(lhs)),
        rhs(std::move(rhs)),
        annotation(std::move(annotation)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Assign", AssignASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for an assignment statement.
 *
 * \code{.cpp}
 * // Build: result = compute(data)
 * AssignAST stmt(IdAST("result"), ExprCall(IdAST("compute"), {IdAST("data")}));
 * \endcode
 *
 * \sa AssignASTObj
 */
struct AssignAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit AssignAST(ExprAST lhs, Optional<ExprAST> rhs = {}, Optional<ExprAST> annotation = {})
      : AssignAST(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
                  std::move(annotation)) {}
  explicit AssignAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST lhs,
                     Optional<ExprAST> rhs, Optional<ExprAST> annotation)
      : AssignAST(make_object<AssignASTObj>(std::move(source_paths), std::move(comment),
                                            std::move(lhs), std::move(rhs),
                                            std::move(annotation))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(AssignAST, StmtAST, AssignASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit AssignAST(ObjectPtr<AssignASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** IfAST **************/

/*!
 * \brief Data object for an if/else statement.
 *
 * Represents the Python construct `if cond: ... else: ...` in the text
 * format AST. The else_branch may be empty for a plain `if` without `else`.
 *
 * \code{.cpp}
 * // Build:
 * //   if x > 0:
 * //     return x
 * //   else:
 * //     return -x
 * IfAST if_stmt(
 *     OperationAST(OperationASTObj::kGt, {IdAST("x"), LiteralAST::Int(0)}),
 *     {ReturnAST(IdAST("x"))},
 *     {ReturnAST(OperationAST(OperationASTObj::kUSub, {IdAST("x")}))}
 * );
 * \endcode
 *
 * \sa IfAST
 */
struct IfASTObj : public StmtASTObj {
  /*! \brief The condition expression (e.g. `x > 0`). */
  ExprAST cond;
  /*! \brief Statements for the true branch (the `if` body). */
  List<StmtAST> then_branch;
  /*! \brief Statements for the false branch (the `else` body; may be empty for no else). */
  List<StmtAST> else_branch;
  /// \cond Doxygen_Suppress
  explicit IfASTObj(ExprAST cond, List<StmtAST> then_branch, List<StmtAST> else_branch)
      : IfASTObj(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(then_branch),
                 std::move(else_branch)) {}
  explicit IfASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                    List<StmtAST> then_branch, List<StmtAST> else_branch)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        cond(std::move(cond)),
        then_branch(std::move(then_branch)),
        else_branch(std::move(else_branch)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.If", IfASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for an if/else statement.
 *
 * \code{.cpp}
 * // Build: if flag: pass (no else branch)
 * IfAST if_only(IdAST("flag"), {ExprStmtAST(IdAST("pass"))}, {});
 * \endcode
 *
 * \sa IfASTObj
 */
struct IfAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit IfAST(ExprAST cond, List<StmtAST> then_branch, List<StmtAST> else_branch)
      : IfAST(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(then_branch),
              std::move(else_branch)) {}
  explicit IfAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                 List<StmtAST> then_branch, List<StmtAST> else_branch)
      : IfAST(make_object<IfASTObj>(std::move(source_paths), std::move(comment), std::move(cond),
                                    std::move(then_branch), std::move(else_branch))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(IfAST, StmtAST, IfASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit IfAST(ObjectPtr<IfASTObj> ptr) : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** WhileAST **************/

/*!
 * \brief Data object for a while-loop statement.
 *
 * Represents the Python construct `while cond: body` in the text format AST.
 *
 * \code{.cpp}
 * // Build:
 * //   while i < n:
 * //     i = i + 1
 * WhileAST loop(
 *     OperationAST(OperationASTObj::kLt, {IdAST("i"), IdAST("n")}),
 *     {AssignAST(IdAST("i"),
 *                OperationAST(OperationASTObj::kAdd, {IdAST("i"), LiteralAST::Int(1)}))}
 * );
 * \endcode
 *
 * \sa WhileAST
 */
struct WhileASTObj : public StmtASTObj {
  /*! \brief The loop condition expression (e.g. `i < n`). */
  ExprAST cond;
  /*! \brief The loop body statements. */
  List<StmtAST> body;
  /// \cond Doxygen_Suppress
  explicit WhileASTObj(ExprAST cond, List<StmtAST> body)
      : WhileASTObj(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(body)) {}
  explicit WhileASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                       List<StmtAST> body)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        cond(std::move(cond)),
        body(std::move(body)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.While", WhileASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a while-loop statement.
 *
 * \code{.cpp}
 * WhileAST loop(LiteralAST::Bool(true), {ExprStmtAST(IdAST("pass"))});
 * // Renders as: while True:\n    pass
 * \endcode
 *
 * \sa WhileASTObj
 */
struct WhileAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit WhileAST(ExprAST cond, List<StmtAST> body)
      : WhileAST(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(body)) {}
  explicit WhileAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                    List<StmtAST> body)
      : WhileAST(make_object<WhileASTObj>(std::move(source_paths), std::move(comment),
                                          std::move(cond), std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(WhileAST, StmtAST, WhileASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit WhileAST(ObjectPtr<WhileASTObj> ptr) : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** ForAST **************/

/*!
 * \brief Data object for a for-loop statement (e.g. `for lhs in rhs`).
 *
 * Represents the Python construct `for lhs in rhs: body` in the text format AST.
 *
 * \code{.cpp}
 * // Build:
 * //   for i in range(10):
 * //     compute(i)
 * ForAST loop(
 *     IdAST("i"),
 *     ExprCall(IdAST("range"), {LiteralAST::Int(10)}),
 *     {ExprStmtAST(ExprCall(IdAST("compute"), {IdAST("i")}))}
 * );
 * \endcode
 *
 * \sa ForAST
 */
struct ForASTObj : public StmtASTObj {
  /*! \brief The loop variable expression (e.g. `i` in `for i in range(10)`). */
  ExprAST lhs;
  /*! \brief The iterable expression (e.g. `range(10)` in `for i in range(10)`). */
  ExprAST rhs;
  /*! \brief The loop body statements. */
  List<StmtAST> body;
  /// \cond Doxygen_Suppress
  explicit ForASTObj(ExprAST lhs, ExprAST rhs, List<StmtAST> body)
      : ForASTObj(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
                  std::move(body)) {}
  explicit ForASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST lhs,
                     ExprAST rhs, List<StmtAST> body)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        lhs(std::move(lhs)),
        rhs(std::move(rhs)),
        body(std::move(body)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.For", ForASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a for-loop statement.
 *
 * \code{.cpp}
 * ForAST loop(IdAST("item"), IdAST("items"), {ExprStmtAST(IdAST("pass"))});
 * // Renders as: for item in items:\n    pass
 * \endcode
 *
 * \sa ForASTObj
 */
struct ForAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit ForAST(ExprAST lhs, ExprAST rhs, List<StmtAST> body)
      : ForAST(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
               std::move(body)) {}
  explicit ForAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST lhs, ExprAST rhs,
                  List<StmtAST> body)
      : ForAST(make_object<ForASTObj>(std::move(source_paths), std::move(comment), std::move(lhs),
                                      std::move(rhs), std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(ForAST, StmtAST, ForASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit ForAST(ObjectPtr<ForASTObj> ptr) : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** WithAST **************/

/*!
 * \brief Data object for a with-statement (e.g. `with rhs as lhs`).
 *
 * Represents the Python construct `with rhs as lhs: body` in the text
 * format AST. The `as lhs` part is optional (lhs may be null).
 *
 * \code{.cpp}
 * // Build:
 * //   with open("data.txt") as f:
 * //     read(f)
 * WithAST with_stmt(
 *     IdAST("f"),
 *     ExprCall(IdAST("open"), {LiteralAST::Str("data.txt")}),
 *     {ExprStmtAST(ExprCall(IdAST("read"), {IdAST("f")}))}
 * );
 * // Build: with lock(): ... (no `as` target)
 * WithAST with_no_as(
 *     NullOpt,
 *     ExprCall(IdAST("lock"), {}),
 *     {ExprStmtAST(IdAST("pass"))}
 * );
 * \endcode
 *
 * \sa WithAST
 */
struct WithASTObj : public StmtASTObj {
  /*! \brief Optional `as` target expression (e.g. `f` in `with open(...) as f`). */
  Optional<ExprAST> lhs;
  /*! \brief The context manager expression (e.g. `open("data.txt")`). */
  ExprAST rhs;
  /*! \brief The with-block body statements. */
  List<StmtAST> body;
  /// \cond Doxygen_Suppress
  explicit WithASTObj(Optional<ExprAST> lhs, ExprAST rhs, List<StmtAST> body)
      : WithASTObj(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
                   std::move(body)) {}
  explicit WithASTObj(List<AccessPath> source_paths, Optional<String> comment,
                      Optional<ExprAST> lhs, ExprAST rhs, List<StmtAST> body)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        lhs(std::move(lhs)),
        rhs(std::move(rhs)),
        body(std::move(body)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.With", WithASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a with-statement.
 *
 * \code{.cpp}
 * WithAST ws(IdAST("ctx"), ExprCall(IdAST("scope"), {}), {ExprStmtAST(IdAST("pass"))});
 * // Renders as: with scope() as ctx:\n    pass
 * \endcode
 *
 * \sa WithASTObj
 */
struct WithAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit WithAST(Optional<ExprAST> lhs, ExprAST rhs, List<StmtAST> body)
      : WithAST(List<AccessPath>{}, Optional<String>{}, std::move(lhs), std::move(rhs),
                std::move(body)) {}
  explicit WithAST(List<AccessPath> source_paths, Optional<String> comment, Optional<ExprAST> lhs,
                   ExprAST rhs, List<StmtAST> body)
      : WithAST(make_object<WithASTObj>(std::move(source_paths), std::move(comment), std::move(lhs),
                                        std::move(rhs), std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(WithAST, StmtAST, WithASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit WithAST(ObjectPtr<WithASTObj> ptr) : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** ExprStmtAST **************/

/*!
 * \brief Data object for an expression used as a statement.
 *
 * Wraps an expression so it can appear in a statement context, such as
 * a bare function call.
 *
 * \code{.cpp}
 * // Build: print("hello")  (as a statement)
 * ExprStmtAST stmt(ExprCall(IdAST("print"), {LiteralAST::Str("hello")}));
 * \endcode
 *
 * \sa ExprStmtAST
 */
struct ExprStmtASTObj : public StmtASTObj {
  /*! \brief The expression to evaluate as a statement. */
  ExprAST expr;
  /// \cond Doxygen_Suppress
  explicit ExprStmtASTObj(ExprAST expr)
      : ExprStmtASTObj(List<AccessPath>{}, Optional<String>{}, std::move(expr)) {}
  explicit ExprStmtASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST expr)
      : StmtASTObj(std::move(source_paths), std::move(comment)), expr(std::move(expr)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.ExprStmt", ExprStmtASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for an expression used as a statement. */
struct ExprStmtAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit ExprStmtAST(ExprAST expr)
      : ExprStmtAST(List<AccessPath>{}, Optional<String>{}, std::move(expr)) {}
  explicit ExprStmtAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST expr)
      : ExprStmtAST(make_object<ExprStmtASTObj>(std::move(source_paths), std::move(comment),
                                                std::move(expr))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(ExprStmtAST, StmtAST, ExprStmtASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit ExprStmtAST(ObjectPtr<ExprStmtASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** AssertAST **************/

/*!
 * \brief Data object for an assert statement (e.g. `assert cond, msg`).
 *
 * Represents the Python construct `assert cond` or `assert cond, msg`
 * in the text format AST.
 *
 * \code{.cpp}
 * // Build: assert x > 0, "must be positive"
 * AssertAST stmt(
 *     OperationAST(OperationASTObj::kGt, {IdAST("x"), LiteralAST::Int(0)}),
 *     LiteralAST::Str("must be positive")
 * );
 * \endcode
 *
 * \sa AssertAST
 */
struct AssertASTObj : public StmtASTObj {
  /*! \brief The condition expression. */
  ExprAST cond;
  /*! \brief Optional assertion failure message. */
  Optional<ExprAST> msg;
  /// \cond Doxygen_Suppress
  explicit AssertASTObj(ExprAST cond, Optional<ExprAST> msg = {})
      : AssertASTObj(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(msg)) {}
  explicit AssertASTObj(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                        Optional<ExprAST> msg)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        cond(std::move(cond)),
        msg(std::move(msg)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Assert", AssertASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for an assert statement. */
struct AssertAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit AssertAST(ExprAST cond, Optional<ExprAST> msg = {})
      : AssertAST(List<AccessPath>{}, Optional<String>{}, std::move(cond), std::move(msg)) {}
  explicit AssertAST(List<AccessPath> source_paths, Optional<String> comment, ExprAST cond,
                     Optional<ExprAST> msg)
      : AssertAST(make_object<AssertASTObj>(std::move(source_paths), std::move(comment),
                                            std::move(cond), std::move(msg))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(AssertAST, StmtAST, AssertASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit AssertAST(ObjectPtr<AssertASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** ReturnAST **************/

/*!
 * \brief Data object for a return statement.
 *
 * Represents the Python construct `return value` in the text format AST.
 * The value is optional (a bare `return` has no value).
 *
 * \code{.cpp}
 * // Build: return x + 1
 * ReturnAST ret(OperationAST(OperationASTObj::kAdd, {IdAST("x"), LiteralAST::Int(1)}));
 * // Build: return  (bare return)
 * ReturnAST bare_ret;
 * \endcode
 *
 * \sa ReturnAST
 */
struct ReturnASTObj : public StmtASTObj {
  /*! \brief Optional return value expression. */
  Optional<ExprAST> value;
  /// \cond Doxygen_Suppress
  explicit ReturnASTObj(Optional<ExprAST> value = {})
      : ReturnASTObj(List<AccessPath>{}, Optional<String>{}, std::move(value)) {}
  explicit ReturnASTObj(List<AccessPath> source_paths, Optional<String> comment,
                        Optional<ExprAST> value)
      : StmtASTObj(std::move(source_paths), std::move(comment)), value(std::move(value)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Return", ReturnASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a return statement. */
struct ReturnAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit ReturnAST(Optional<ExprAST> value = {})
      : ReturnAST(List<AccessPath>{}, Optional<String>{}, std::move(value)) {}
  explicit ReturnAST(List<AccessPath> source_paths, Optional<String> comment,
                     Optional<ExprAST> value)
      : ReturnAST(make_object<ReturnASTObj>(std::move(source_paths), std::move(comment),
                                            std::move(value))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(ReturnAST, StmtAST, ReturnASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit ReturnAST(ObjectPtr<ReturnASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** FunctionAST **************/

/*!
 * \brief Data object for a function definition statement.
 *
 * Represents the Python construct `def name(args) -> return_type: body`,
 * optionally preceded by decorator expressions. Function arguments are
 * represented as AssignAST nodes where lhs is the parameter name and
 * annotation is the optional type hint (rhs is unused for parameters).
 *
 * \code{.cpp}
 * // Build:
 * //   @decorator
 * //   def add(x: int, y: int) -> int:
 * //     return x + y
 * FunctionAST func(
 *     IdAST("add"),
 *     {AssignAST(IdAST("x"), NullOpt, IdAST("int")),
 *      AssignAST(IdAST("y"), NullOpt, IdAST("int"))},
 *     {IdAST("decorator")},
 *     IdAST("int"),
 *     {ReturnAST(OperationAST(OperationASTObj::kAdd, {IdAST("x"), IdAST("y")}))}
 * );
 * \endcode
 *
 * \sa FunctionAST
 */
struct FunctionASTObj : public StmtASTObj {
  /*! \brief The function name (e.g. `add`). */
  IdAST name;
  /*! \brief The argument list as AssignAST nodes (lhs = param name, annotation = type hint). */
  List<AssignAST> args;
  /*! \brief Decorator expressions (e.g. `{IdAST("staticmethod")}`). */
  List<ExprAST> decorators;
  /*! \brief Optional return type annotation (e.g. `int` in `-> int`). */
  Optional<ExprAST> return_type;
  /*! \brief The function body statements. */
  List<StmtAST> body;
  /// \cond Doxygen_Suppress
  explicit FunctionASTObj(IdAST name, List<AssignAST> args, List<ExprAST> decorators,
                          Optional<ExprAST> return_type, List<StmtAST> body)
      : FunctionASTObj(List<AccessPath>{}, Optional<String>{}, std::move(name), std::move(args),
                       std::move(decorators), std::move(return_type), std::move(body)) {}
  explicit FunctionASTObj(List<AccessPath> source_paths, Optional<String> comment, IdAST name,
                          List<AssignAST> args, List<ExprAST> decorators,
                          Optional<ExprAST> return_type, List<StmtAST> body)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        name(std::move(name)),
        args(std::move(args)),
        decorators(std::move(decorators)),
        return_type(std::move(return_type)),
        body(std::move(body)) {
    for (const AssignAST& arg_doc : this->args) {
      if (arg_doc->comment.has_value()) {
        TVM_FFI_THROW(ValueError) << "Function arg cannot have comment attached to them";
      }
    }
  }
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Function", FunctionASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a function definition statement.
 *
 * \code{.cpp}
 * // Build: def noop(): pass
 * FunctionAST func(
 *     IdAST("noop"), {}, {}, NullOpt,
 *     {ExprStmtAST(IdAST("pass"))}
 * );
 * \endcode
 *
 * \sa FunctionASTObj
 */
struct FunctionAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit FunctionAST(IdAST name, List<AssignAST> args, List<ExprAST> decorators,
                       Optional<ExprAST> return_type, List<StmtAST> body)
      : FunctionAST(List<AccessPath>{}, Optional<String>{}, std::move(name), std::move(args),
                    std::move(decorators), std::move(return_type), std::move(body)) {}
  explicit FunctionAST(List<AccessPath> source_paths, Optional<String> comment, IdAST name,
                       List<AssignAST> args, List<ExprAST> decorators,
                       Optional<ExprAST> return_type, List<StmtAST> body)
      : FunctionAST(make_object<FunctionASTObj>(
            std::move(source_paths), std::move(comment), std::move(name), std::move(args),
            std::move(decorators), std::move(return_type), std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(FunctionAST, StmtAST, FunctionASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit FunctionAST(ObjectPtr<FunctionASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** ClassAST **************/

/*!
 * \brief Data object for a class definition statement.
 *
 * Represents the Python construct `class Name: body`, optionally
 * preceded by decorator expressions.
 *
 * \code{.cpp}
 * // Build:
 * //   @dataclass
 * //   class Point:
 * //     x: int
 * //     y: int
 * ClassAST cls(
 *     IdAST("Point"),
 *     {IdAST("dataclass")},
 *     {AssignAST(IdAST("x"), NullOpt, IdAST("int")),
 *      AssignAST(IdAST("y"), NullOpt, IdAST("int"))}
 * );
 * \endcode
 *
 * \sa ClassAST
 */
struct ClassASTObj : public StmtASTObj {
  /*! \brief The class name (e.g. `Point`). */
  IdAST name;
  /*! \brief Decorator expressions (e.g. `{IdAST("dataclass")}`). */
  List<ExprAST> decorators;
  /*! \brief The class body statements. */
  List<StmtAST> body;
  /// \cond Doxygen_Suppress
  explicit ClassASTObj(IdAST name, List<ExprAST> decorators, List<StmtAST> body)
      : ClassASTObj(List<AccessPath>{}, Optional<String>{}, std::move(name), std::move(decorators),
                    std::move(body)) {}
  explicit ClassASTObj(List<AccessPath> source_paths, Optional<String> comment, IdAST name,
                       List<ExprAST> decorators, List<StmtAST> body)
      : StmtASTObj(std::move(source_paths), std::move(comment)),
        name(std::move(name)),
        decorators(std::move(decorators)),
        body(std::move(body)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Class", ClassASTObj, StmtASTObj);
  /// \endcond
};

/*!
 * \brief Reference wrapper for a class definition statement.
 *
 * \code{.cpp}
 * ClassAST cls(IdAST("Empty"), {}, {ExprStmtAST(IdAST("pass"))});
 * // Renders as: class Empty:\n    pass
 * \endcode
 *
 * \sa ClassASTObj
 */
struct ClassAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit ClassAST(IdAST name, List<ExprAST> decorators, List<StmtAST> body)
      : ClassAST(List<AccessPath>{}, Optional<String>{}, std::move(name), std::move(decorators),
                 std::move(body)) {}
  explicit ClassAST(List<AccessPath> source_paths, Optional<String> comment, IdAST name,
                    List<ExprAST> decorators, List<StmtAST> body)
      : ClassAST(make_object<ClassASTObj>(std::move(source_paths), std::move(comment),
                                          std::move(name), std::move(decorators),
                                          std::move(body))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(ClassAST, StmtAST, ClassASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit ClassAST(ObjectPtr<ClassASTObj> ptr) : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** CommentAST **************/

/*!
 * \brief Data object for a standalone comment line (e.g. `# comment text`).
 *
 * Represents a full-line Python comment in the text format AST. The
 * comment text is stored in the inherited `comment` field from StmtASTObj.
 *
 * \code{.cpp}
 * // Build: # This is a comment
 * CommentAST cmt(String("This is a comment"));
 * \endcode
 *
 * \sa CommentAST
 */
struct CommentASTObj : public StmtASTObj {
  /// \cond Doxygen_Suppress
  explicit CommentASTObj(Optional<String> comment)
      : CommentASTObj(List<AccessPath>{}, std::move(comment)) {}
  explicit CommentASTObj(List<AccessPath> source_paths, Optional<String> comment)
      : StmtASTObj(std::move(source_paths), std::move(comment)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.Comment", CommentASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a standalone comment line. */
struct CommentAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit CommentAST(Optional<String> comment)
      : CommentAST(List<AccessPath>{}, std::move(comment)) {}
  explicit CommentAST(List<AccessPath> source_paths, Optional<String> comment)
      : CommentAST(make_object<CommentASTObj>(std::move(source_paths), std::move(comment))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(CommentAST, StmtAST, CommentASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit CommentAST(ObjectPtr<CommentASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** DocStringAST **************/

/*!
 * \brief Data object for a docstring statement (triple-quoted string).
 *
 * Represents a Python docstring in the text format AST. The text is
 * stored in the inherited `comment` field from StmtASTObj and rendered
 * with triple quotes.
 *
 * \code{.cpp}
 * // Build: """Compute the sum of two values."""
 * DocStringAST doc(String("Compute the sum of two values."));
 * \endcode
 *
 * \sa DocStringAST
 */
struct DocStringASTObj : public StmtASTObj {
  /// \cond Doxygen_Suppress
  explicit DocStringASTObj(Optional<String> comment)
      : DocStringASTObj(List<AccessPath>{}, std::move(comment)) {}
  explicit DocStringASTObj(List<AccessPath> source_paths, Optional<String> comment)
      : StmtASTObj(std::move(source_paths), std::move(comment)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.text.ast.DocString", DocStringASTObj, StmtASTObj);
  /// \endcond
};

/*! \brief Reference wrapper for a docstring statement. */
struct DocStringAST : public StmtAST {
  /// \cond Doxygen_Suppress
  explicit DocStringAST(Optional<String> comment)
      : DocStringAST(List<AccessPath>{}, std::move(comment)) {}
  explicit DocStringAST(List<AccessPath> source_paths, Optional<String> comment)
      : DocStringAST(make_object<DocStringASTObj>(std::move(source_paths), std::move(comment))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(DocStringAST, StmtAST, DocStringASTObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit DocStringAST(ObjectPtr<DocStringASTObj> ptr)
      : StmtAST(ObjectPtr<StmtASTObj>(std::move(ptr))) {}
  /// \endcond
};

/************** Free convenience functions for ExprAST **************/

/*!
 * \brief Create an attribute access expression: obj.name.
 * \param obj The expression to access the attribute on.
 * \param name The attribute name.
 * \return An ExprAST representing the attribute access.
 */
inline ExprAST ExprAttr(ExprAST obj, String name) {
  return AttrAST(List<AccessPath>{}, std::move(obj), std::move(name));
}

/*!
 * \brief Create an index/subscript expression: obj[idx].
 * \param obj The expression to index into.
 * \param idx The list of index expressions.
 * \return An ExprAST representing the subscript.
 */
inline ExprAST ExprIndex(ExprAST obj, List<ExprAST> idx) {
  return IndexAST(List<AccessPath>{}, std::move(obj), std::move(idx));
}

/*!
 * \brief Create a positional-only call expression: obj(args...).
 * \param obj The callee expression.
 * \param args The list of positional argument expressions.
 * \return An ExprAST representing the call.
 */
inline ExprAST ExprCall(ExprAST obj, List<ExprAST> args) {
  return CallAST(List<AccessPath>{}, std::move(obj), std::move(args), List<String>{},
                 List<ExprAST>{});
}

/*!
 * \brief Create a call expression with keyword arguments: obj(args..., key=value...).
 * \param obj The callee expression.
 * \param args The list of positional argument expressions.
 * \param kwargs_keys The keyword argument names (parallel to kwargs_values).
 * \param kwargs_values The keyword argument value expressions.
 * \return An ExprAST representing the call.
 */
inline ExprAST ExprCallKw(ExprAST obj, List<ExprAST> args, List<String> kwargs_keys,
                          List<ExprAST> kwargs_values) {
  return CallAST(List<AccessPath>{}, std::move(obj), std::move(args), std::move(kwargs_keys),
                 std::move(kwargs_values));
}

}  // namespace text
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_TEXT_AST_H_
