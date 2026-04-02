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
 * \file tvm/ffi/ir/text/printer.h
 * \brief IRPrinter and rendering functions for text format AST.
 *
 * Provides the IRPrinter (which converts IR objects into text format AST
 * nodes) and the ToPython/DocToPythonScript functions that render AST to
 * Python-style source strings. For the AST node definitions themselves,
 * see tvm/ffi/ir/text/ast.h.
 */
#ifndef TVM_FFI_IR_TEXT_PRINTER_H_
#define TVM_FFI_IR_TEXT_PRINTER_H_

#include <tvm/ffi/ir/text/ast.h>

#include <algorithm>
#include <iomanip>
#include <sstream>
#include <string>

namespace tvm {
namespace ffi {
namespace ir {
namespace text {

/************** PrinterConfig **************/

/*!
 * \brief Data object for printer configuration options.
 *
 * Controls formatting of the Python-style text output, including
 * indentation width, line numbering, context windowing, and underline
 * highlighting of specific access paths.
 *
 * \code{.cpp}
 * // Default config: 2-space indent, no line numbers, all context lines
 * PrinterConfig cfg;
 * String result = ToPython(some_ir_obj, cfg);
 *
 * // Custom config: 4-space indent, line numbers enabled, 3 context lines
 * PrinterConfig cfg2(true, 4, 1, 3);
 * String result2 = ToPython(some_ir_obj, cfg2);
 *
 * // With underline highlighting for a specific access path
 * PrinterConfig cfg3(true, 2, 0, -1, false,
 *                    {AccessPath::Root().Attr("args").ArrayItem(0)});
 * String result3 = ToPython(some_ir_obj, cfg3);
 * \endcode
 *
 * \sa PrinterConfig
 */
struct PrinterConfigObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  /// \endcond
  /*!
   * \brief When true, defines free variables automatically.
   *
   * If an IR object references a variable that has not been explicitly
   * defined via VarDef, the printer will create a definition for it
   * automatically. Example: `true`.
   */
  bool def_free_var = true;
  /*!
   * \brief Number of spaces per indentation level.
   *
   * Example: `2` for two-space indent, `4` for four-space indent.
   */
  int32_t indent_spaces = 2;
  /*!
   * \brief If > 0, prefix each output line with its line number.
   *
   * Example: `1` to enable line numbers, `0` to disable.
   */
  int8_t print_line_numbers = 0;
  /*!
   * \brief Number of context lines to show around underlined regions.
   *
   * When `path_to_underline` is non-empty, this controls how many
   * surrounding lines are displayed. Example: `-1` for all lines,
   * `3` for 3 context lines above and below the underlined region.
   */
  int32_t num_context_lines = -1;
  /*!
   * \brief Append a hex address suffix for duplicate variable names.
   *
   * When true and a name collision occurs during VarDef, the printer
   * appends `_0x...` (the object's address) instead of a numeric suffix.
   * Example: `true` appends `_0x...` to duplicate var names.
   */
  bool print_addr_on_dup_var = false;
  /*!
   * \brief Access paths to underline in the output.
   *
   * Each AccessPath identifies a position in the IR tree. Lines
   * corresponding to these paths are rendered with underline markers.
   * Example: `{AccessPath::Root().Attr("args").ArrayItem(0)}` to
   * underline the first argument.
   */
  List<AccessPath> path_to_underline;
  /// \cond Doxygen_Suppress
  PrinterConfigObj() = default;
  /*!
   * \brief Construct a PrinterConfigObj with explicit settings.
   * \param def_free_var Whether to define free variables automatically.
   * \param indent_spaces Number of spaces per indentation level.
   * \param print_line_numbers Whether to prefix lines with line numbers (> 0 to enable).
   * \param num_context_lines Context lines around underlined regions (-1 = all).
   * \param print_addr_on_dup_var Whether to append hex address for duplicate names.
   * \param path_to_underline Access paths to underline in the output.
   */
  explicit PrinterConfigObj(bool def_free_var, int32_t indent_spaces, int8_t print_line_numbers,
                            int32_t num_context_lines, bool print_addr_on_dup_var,
                            List<AccessPath> path_to_underline)
      : def_free_var(def_free_var),
        indent_spaces(indent_spaces),
        print_line_numbers(print_line_numbers),
        num_context_lines(num_context_lines),
        print_addr_on_dup_var(print_addr_on_dup_var),
        path_to_underline(std::move(path_to_underline)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.ir.text.PrinterConfig", PrinterConfigObj, Object);
  /// \endcond
};

/*!
 * \brief Reference wrapper for PrinterConfigObj.
 *
 * \code{.cpp}
 * PrinterConfig cfg;                  // default: 2-space indent, no line numbers
 * PrinterConfig cfg2(true, 4, 1, 3); // custom settings
 * \endcode
 *
 * \sa PrinterConfigObj
 */
struct PrinterConfig : public ObjectRef {
  /*!
   * \brief Construct a PrinterConfig with the given settings.
   *
   * All parameters have sensible defaults; a default-constructed
   * PrinterConfig uses 2-space indent with no line numbers.
   *
   * \param def_free_var Whether to define free variables automatically (default true).
   * \param indent_spaces Number of spaces per indentation level (default 2).
   * \param print_line_numbers Whether to prefix lines with line numbers (default 0 = off).
   * \param num_context_lines Context lines around underlined regions (default -1 = all).
   * \param print_addr_on_dup_var Whether to append hex address for duplicate names (default false).
   * \param path_to_underline Access paths to underline in the output (default empty).
   */
  explicit PrinterConfig(bool def_free_var = true, int32_t indent_spaces = 2,
                         int8_t print_line_numbers = 0, int32_t num_context_lines = -1,
                         bool print_addr_on_dup_var = false,
                         List<AccessPath> path_to_underline = {})
      : PrinterConfig(make_object<PrinterConfigObj>(def_free_var, indent_spaces, print_line_numbers,
                                                    num_context_lines, print_addr_on_dup_var,
                                                    std::move(path_to_underline))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(PrinterConfig, ObjectRef, PrinterConfigObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit PrinterConfig(ObjectPtr<PrinterConfigObj> ptr) : ObjectRef(std::move(ptr)) {}
  /// \endcond
};

/************** DefaultFrame **************/

/*!
 * \brief Data object for the default frame used by IRPrinter.
 *
 * A frame accumulates a list of statement AST nodes. The IRPrinter
 * maintains a stack of frames; statements emitted by print dispatch
 * are appended to the frame on top of the stack. DefaultFrame is the
 * simplest frame type, holding only a mutable statement list.
 *
 * \code{.cpp}
 * IRPrinter printer(PrinterConfig());
 * DefaultFrame frame;
 * // Push the frame onto the printer's frame stack
 * printer->FramePush(frame);
 * // Dispatch IR nodes; statements are appended to frame->stmts
 * Any doc = printer->operator()(Any(some_ir_obj), AccessPath::Root());
 * // Pop the frame and clean up variables defined within it
 * printer->FramePop();
 * // frame->stmts now contains all emitted statements
 * for (StmtAST stmt : frame->stmts) {
 *   // process each statement...
 * }
 * \endcode
 *
 * \sa DefaultFrame, IRPrinterObj
 */
struct DefaultFrameObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  /// \endcond
  /*! \brief Statements accumulated in this frame. */
  List<StmtAST> stmts;
  /// \cond Doxygen_Suppress
  DefaultFrameObj() = default;
  explicit DefaultFrameObj(List<StmtAST> stmts) : stmts(std::move(stmts)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.ir.text.DefaultFrame", DefaultFrameObj, Object);
  /// \endcond
};

/*!
 * \brief Reference wrapper for DefaultFrameObj.
 *
 * Constructible with an empty statement list (default) or with a
 * pre-populated list. Used with IRPrinter::FramePush/FramePop.
 *
 * \code{.cpp}
 * // Create an empty frame and use it with a printer
 * IRPrinter printer(PrinterConfig());
 * DefaultFrame frame;
 * printer->FramePush(frame);
 * // ... emit IR nodes via printer->operator() ...
 * printer->FramePop();
 *
 * // Or pre-populate with existing statements
 * DefaultFrame frame2(List<StmtAST>{some_stmt});
 * \endcode
 *
 * \sa DefaultFrameObj
 */
struct DefaultFrame : public ObjectRef {
  /// \cond Doxygen_Suppress
  explicit DefaultFrame() : DefaultFrame(make_object<DefaultFrameObj>()) {}
  explicit DefaultFrame(List<StmtAST> stmts)
      : DefaultFrame(make_object<DefaultFrameObj>(std::move(stmts))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(DefaultFrame, ObjectRef, DefaultFrameObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit DefaultFrame(ObjectPtr<DefaultFrameObj> ptr) : ObjectRef(std::move(ptr)) {}
  /// \endcond
};

/************** VarInfo **************/

/*!
 * \brief Data object holding metadata for a variable tracked by IRPrinter.
 *
 * Each variable binding in the printer maps an IR object to a VarInfo
 * containing its display name (if any) and a creator function that
 * produces the definition-site AST node when invoked.
 *
 * \code{.cpp}
 * // Named variable: creator returns an IdAST with the given name
 * VarInfo named_var(String("x"), Function::FromTyped([]() -> IdAST {
 *   return IdAST("x");
 * }));
 *
 * // Unnamed variable: name is null, creator returns a custom expression
 * VarInfo unnamed_var(Optional<String>{}, some_creator_fn);
 * \endcode
 *
 * \sa VarInfo, IRPrinterObj::VarDef, IRPrinterObj::VarDefNoName
 */
struct VarInfoObj : public Object {
  /*!
   * \brief The display name, or null if unnamed.
   *
   * For named variables (created via VarDef), this holds the normalized,
   * de-duplicated name string. Example: `String("my_var")` or
   * `String("my_var_1")` if the name was de-duplicated.
   * For unnamed variables (created via VarDefNoName), this is null.
   */
  Optional<String> name;
  /*!
   * \brief Callable that produces the definition-site AST.
   *
   * When invoked with no arguments, returns an ExprAST node representing
   * how this variable should be rendered. For named variables, this
   * typically returns `IdAST(name)`. For unnamed variables, the creator
   * may return any ExprAST. Example: `Function::FromTyped([]() -> IdAST {
   * return IdAST("x"); })`.
   */
  Function creator;
  /// \cond Doxygen_Suppress
  explicit VarInfoObj(Optional<String> name, Function creator)
      : name(std::move(name)), creator(std::move(creator)) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.ir.text.VarInfo", VarInfoObj, Object);
  /// \endcond
};

/*!
 * \brief Reference wrapper for variable metadata tracked by IRPrinter.
 *
 * \code{.cpp}
 * VarInfo info(String("x"), Function::FromTyped([]() -> IdAST {
 *   return IdAST("x");
 * }));
 * // info->name is "x"
 * // info->creator() returns IdAST("x")
 * \endcode
 *
 * \sa VarInfoObj
 */
struct VarInfo : public ObjectRef {
  /// \cond Doxygen_Suppress
  explicit VarInfo(Optional<String> name, Function creator)
      : VarInfo(make_object<VarInfoObj>(std::move(name), std::move(creator))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(VarInfo, ObjectRef, VarInfoObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit VarInfo(ObjectPtr<VarInfoObj> ptr) : ObjectRef(std::move(ptr)) {}
  /// \endcond
};

/************** IRPrinter **************/

/*!
 * \brief Data object for the IR-to-document-AST printer.
 *
 * IRPrinterObj converts IR objects into the text format AST by dispatching
 * through __ffi_text_print__ methods registered on each IR type. It maintains:
 * - A variable table (obj2info / defined_names) for name deduplication.
 * - A frame stack for scoped statement collection.
 *
 * The call operator `operator()(source, path)` dispatches printing for
 * a single IR value, returning the resulting text format AST node.
 *
 * \code{.cpp}
 * IRPrinter printer(PrinterConfig());
 * DefaultFrame frame;
 * printer->FramePush(frame);
 * // Print an IR object into the frame:
 * Any doc = printer->operator()(Any(some_ir_obj), AccessPath::Root());
 * printer->FramePop();
 * // Render the collected statements:
 * StmtBlockAST block({}, NullOpt, frame->stmts);
 * String code = DocToPythonScript(block, printer->cfg);
 * \endcode
 *
 * \sa IRPrinter, PrinterConfig, DefaultFrame
 */
struct IRPrinterObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  /// \endcond
  /*! \brief The printer configuration. */
  PrinterConfig cfg;
  /*! \brief Mapping from IR objects to their variable metadata. */
  Dict<Any, VarInfo> obj2info;
  /*! \brief Set of variable names already in use. */
  Dict<String, int64_t> defined_names;
  /*! \brief Stack of active scoping frames. */
  List<Any> frames;
  /*! \brief Mapping from frames to variables defined in each. */
  Dict<Any, Any> frame_vars;
  /// \cond Doxygen_Suppress
  explicit IRPrinterObj(PrinterConfig cfg) : cfg(std::move(cfg)) {}
  explicit IRPrinterObj(PrinterConfig cfg, Dict<Any, VarInfo> obj2info,
                        Dict<String, int64_t> defined_names, List<Any> frames,
                        Dict<Any, Any> frame_vars)
      : cfg(std::move(cfg)),
        obj2info(std::move(obj2info)),
        defined_names(std::move(defined_names)),
        frames(std::move(frames)),
        frame_vars(std::move(frame_vars)) {}
  /// \endcond

  /*!
   * \brief Check whether an IR object already has a variable binding in this printer.
   *
   * \param obj The IR object to look up.
   * \return True if \p obj has been registered via VarDef or VarDefNoName.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * printer->VarDef("x", some_obj, {});
   * bool defined = printer->VarIsDefined(some_obj);  // true
   * bool unknown = printer->VarIsDefined(other_obj);  // false
   * printer->FramePop();
   * \endcode
   */
  bool VarIsDefined(const ObjectRef& obj) { return obj2info.count(obj) > 0; }
  /*!
   * \brief Define a named variable for an IR object.
   *
   * Normalizes the name hint (replacing non-alphanumeric characters with
   * underscores), de-duplicates against existing names, and registers the
   * binding in the current frame.
   *
   * \param name_hint Suggested display name (may be normalized).
   * \param obj The IR object to bind.
   * \param frame Frame to register in, or null for the current top frame.
   * \return An IdAST node referencing the defined variable.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * IdAST x = printer->VarDef("my_var", some_ir_obj, {});
   * // x renders as "my_var"
   * IdAST y = printer->VarDef("my_var", another_obj, {});
   * // y renders as "my_var_1" (de-duplicated)
   * printer->FramePop();
   * \endcode
   */
  IdAST VarDef(String name_hint, const ObjectRef& obj, const Optional<ObjectRef>& frame);
  /*!
   * \brief Define a variable for an IR object using a custom creator function (no name).
   *
   * Unlike VarDef, this does not assign a display name. Instead, the
   * provided creator function determines how the variable renders when
   * looked up via VarGet.
   *
   * \param creator A nullary function returning an ExprAST for this variable.
   * \param obj The IR object to bind.
   * \param frame Frame to register in, or null for the current top frame.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * Function creator = Function::FromTyped([]() -> ExprAST {
   *   return AttrAST(IdAST("module"), "func_a", {});
   * });
   * printer->VarDefNoName(creator, some_ir_obj, {});
   * // VarGet(some_ir_obj) now returns AttrAST(IdAST("module"), "func_a")
   * printer->FramePop();
   * \endcode
   */
  void VarDefNoName(const Function& creator, const ObjectRef& obj,
                    const Optional<ObjectRef>& frame);
  /*!
   * \brief Remove the variable binding for an IR object.
   *
   * Erases the object from the variable table and frees the name (if any)
   * so it can be reused. Throws KeyError if the object has no binding.
   *
   * \param obj The IR object whose binding to remove.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * printer->VarDef("x", some_obj, {});
   * printer->VarRemove(some_obj);
   * // printer->VarIsDefined(some_obj) is now false
   * printer->FramePop();
   * \endcode
   */
  void VarRemove(const ObjectRef& obj);
  /*!
   * \brief Look up the expression AST for a previously defined variable.
   *
   * If the object has a binding, invokes its creator function and returns
   * the resulting ExprAST. Returns null if no binding exists.
   *
   * \param obj The IR object to look up.
   * \return The ExprAST for the variable, or null if not defined.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * printer->VarDef("x", some_obj, {});
   * Optional<ExprAST> expr = printer->VarGet(some_obj);
   * // expr.has_value() == true, renders as IdAST("x")
   * Optional<ExprAST> missing = printer->VarGet(unknown_obj);
   * // missing.has_value() == false
   * printer->FramePop();
   * \endcode
   */
  Optional<ExprAST> VarGet(const ObjectRef& obj);
  /*!
   * \brief Convert a source value to a text format AST node using registered
   *        __ffi_text_print__ dispatch.
   *
   * For primitive types (None, bool, int, float, string), returns the
   * corresponding LiteralAST directly. For Object types, dispatches to
   * the __ffi_text_print__ method registered for that type, which should return
   * a NodeAST.
   *
   * \param source The IR value to print (may be a primitive or an Object).
   * \param path The access path identifying \p source within the IR tree.
   * \return A NodeAST (or LiteralAST) representing the printed value.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * // Print an IR object; dispatches to its __ffi_text_print__ method
   * Any doc = printer->operator()(Any(some_ir_obj), AccessPath::Root());
   * // Print a primitive value; returns a LiteralAST directly
   * Any lit = printer->operator()(Any(42), AccessPath::Root().Attr("value"));
   * printer->FramePop();
   * \endcode
   */
  Any operator()(Any source, AccessPath path) const;

  /*!
   * \brief Apply this printer to each element of a list.
   *
   * Iterates over \p list, calling `operator()` on each element with
   * an ArrayItem access path derived from \p p, and collects the results
   * into a typed list.
   *
   * \tparam T The element type for the output list (e.g., ExprAST).
   * \param list The list of IR values to print.
   * \param p The parent access path; each element gets `p->ArrayItem(i)`.
   * \return A list of printed AST nodes, one per input element.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * List<Any> ir_args = {Any(arg0), Any(arg1), Any(arg2)};
   * AccessPath args_path = AccessPath::Root().Attr("args");
   * List<ExprAST> printed = printer->ApplyToList<ExprAST>(ir_args, args_path);
   * // printed[0] was printed with path Root().Attr("args").ArrayItem(0)
   * // printed[1] was printed with path Root().Attr("args").ArrayItem(1)
   * printer->FramePop();
   * \endcode
   */
  template <typename T>
  List<T> ApplyToList(const List<Any>& list, const AccessPath& p) const {
    int64_t n = static_cast<int64_t>(list.size());
    List<T> result;
    result.reserve(n);
    for (int64_t i = 0; i < n; ++i) {
      result.push_back(this->operator()(list[i], p->ArrayItem(i)));
    }
    return result;
  }

  /*!
   * \brief Push a scoping frame onto the frame stack.
   *
   * Variables defined after this call (until the matching FramePop) are
   * associated with \p frame. The frame becomes the new top of the stack.
   *
   * \param frame The frame to push (typically a DefaultFrame).
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame frame;
   * printer->FramePush(frame);
   * // ... define variables and emit statements ...
   * printer->FramePop();
   * \endcode
   */
  void FramePush(const ObjectRef& frame);
  /*!
   * \brief Pop the top frame and remove all variables defined in it.
   *
   * Removes every variable binding that was registered to the top frame
   * (freeing their names), then removes the frame from the stack. Must
   * be paired with a preceding FramePush call.
   *
   * \code{.cpp}
   * IRPrinter printer(PrinterConfig());
   * DefaultFrame outer;
   * printer->FramePush(outer);
   * printer->VarDef("x", obj_x, {});
   * {
   *   DefaultFrame inner;
   *   printer->FramePush(inner);
   *   printer->VarDef("y", obj_y, {});
   *   printer->FramePop();  // removes "y", inner frame popped
   * }
   * // "x" is still defined; "y" is gone
   * printer->FramePop();  // removes "x", outer frame popped
   * \endcode
   */
  void FramePop();

  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO_FINAL("ffi.ir.text.IRPrinter", IRPrinterObj, Object);
  /// \endcond

 private:
  /*! \brief Internal: register a VarInfo for \p obj in the given frame. */
  void VarDefInternal(VarInfo var_info, const ObjectRef& obj, const Optional<ObjectRef>& frame);
};

/*!
 * \brief Reference wrapper for IRPrinterObj.
 *
 * Constructed from a PrinterConfig. Use the underlying object's methods
 * (via operator->) to define variables, push/pop frames, and dispatch
 * printing.
 *
 * \code{.cpp}
 * IRPrinter printer(PrinterConfig());
 * // Convenient one-shot printing is available via the ToPython free function:
 * String code = ToPython(some_ir_obj, printer->cfg);
 * \endcode
 *
 * \sa IRPrinterObj
 */
struct IRPrinter : public ObjectRef {
  /// \cond Doxygen_Suppress
  explicit IRPrinter(PrinterConfig cfg) : IRPrinter(make_object<IRPrinterObj>(std::move(cfg))) {}
  /// \endcond
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(IRPrinter, ObjectRef, IRPrinterObj);
  /// \endcond
  /// \cond Doxygen_Suppress
  explicit IRPrinter(ObjectPtr<IRPrinterObj> ptr) : ObjectRef(std::move(ptr)) {}
  /// \endcond
};

/************** Free functions **************/

/*!
 * \brief Dispatch __ffi_text_print__ for the given IR object.
 *
 * Looks up the `__ffi_text_print__` method registered for the type of \p obj
 * and invokes it, passing the printer and access path. This is the
 * low-level dispatch mechanism used internally by IRPrinterObj::operator().
 *
 * \param obj The IR object to print (as an AnyView).
 * \param printer The IRPrinter performing the printing (as an AnyView).
 * \param path The access path for \p obj within the IR tree (as an AnyView).
 * \return A NodeAST produced by the object's __ffi_text_print__ method.
 *
 * \code{.cpp}
 * IRPrinter printer(PrinterConfig());
 * AccessPath path = AccessPath::Root();
 * NodeAST node = IRPrintDispatch(AnyView(some_ir_obj),
 *                                AnyView(printer),
 *                                AnyView(path));
 * \endcode
 */
TVM_FFI_EXTRA_CXX_API NodeAST IRPrintDispatch(AnyView obj, AnyView printer, AnyView path);
/*!
 * \brief Convert an IR object to a Python source code string.
 *
 * This is the high-level entry point for IR-to-text conversion. It
 * creates an IRPrinter, dispatches printing for \p obj, collects the
 * resulting AST, and renders it to a Python-style source string.
 *
 * \param obj The IR object to convert.
 * \param cfg Printer configuration controlling formatting.
 * \return A Python-style source code string representing \p obj.
 *
 * \code{.cpp}
 * PrinterConfig cfg(true, 4, 1);  // 4-space indent, line numbers on
 * String code = ToPython(some_ir_obj, cfg);
 * // code contains the Python-style text representation
 * \endcode
 */
TVM_FFI_EXTRA_CXX_API String ToPython(ObjectRef obj, PrinterConfig cfg);  // NOLINT(*-value-param)
/*!
 * \brief Render a text format AST node to a Python source string.
 *
 * Takes an already-constructed AST node (e.g., a StmtBlockAST produced
 * by manual AST construction or by IRPrinter) and renders it to a
 * Python-style source string using the given configuration.
 *
 * \param node The AST node to render.
 * \param cfg Printer configuration controlling formatting.
 * \return A Python-style source code string.
 *
 * \code{.cpp}
 * // Build an AST manually
 * StmtBlockAST block({}, NullOpt, {some_stmt});
 * PrinterConfig cfg;
 * String code = DocToPythonScript(block, cfg);
 *
 * // Or render a node from an IRPrinter session
 * IRPrinter printer(PrinterConfig());
 * DefaultFrame frame;
 * printer->FramePush(frame);
 * Any doc = printer->operator()(Any(some_ir_obj), AccessPath::Root());
 * printer->FramePop();
 * StmtBlockAST result({}, NullOpt, frame->stmts);
 * String output = DocToPythonScript(result, printer->cfg);
 * \endcode
 */
TVM_FFI_EXTRA_CXX_API String DocToPythonScript(NodeAST node, PrinterConfig cfg);

/************** Inline: IRPrinterObj methods **************/

inline IdAST IRPrinterObj::VarDef(String name_hint, const ObjectRef& obj,
                                  const Optional<ObjectRef>& frame) {
  if (auto it = obj2info.find(obj); it != obj2info.end()) {
    Optional<String> name = (*it).second->name;
    return IdAST(name.value());
  }
  bool needs_normalize = std::any_of(name_hint.data(), name_hint.data() + name_hint.size(),
                                     [](char c) { return c != '_' && !std::isalnum(c); });
  if (needs_normalize) {
    std::string buf(name_hint.data(), name_hint.size());
    for (char& c : buf) {
      if (c != '_' && !std::isalnum(c)) {
        c = '_';
      }
    }
    name_hint = String(buf);
  }
  std::string name_hint_str(name_hint.data(), name_hint.size());
  String name(name_hint_str);
  if (defined_names.count(name)) {
    if (this->cfg->print_addr_on_dup_var) {
      std::ostringstream os;
      os << name_hint_str << "_0x" << std::setfill('0') << std::setw(12) << std::hex
         << reinterpret_cast<uintptr_t>(obj.get());
      name = String(os.str());
    } else {
      for (int i = 1; defined_names.count(name) > 0; ++i) {
        name = String(name_hint_str + '_' + std::to_string(i));
      }
    }
  }
  defined_names.Set(name, 1);
  String captured_name = name;
  this->VarDefInternal(VarInfo(name, Function::FromTyped([captured_name]() -> IdAST {
                                 return IdAST(captured_name);
                               })),
                       obj, frame);
  return IdAST(name);
}

inline void IRPrinterObj::VarDefNoName(const Function& creator, const ObjectRef& obj,
                                       const Optional<ObjectRef>& frame) {
  if (obj2info.count(obj) > 0) {
    TVM_FFI_THROW(KeyError) << "Variable already defined: " << obj.get()->GetTypeKey();
  }
  this->VarDefInternal(VarInfo(Optional<String>{}, creator), obj, frame);
}

inline void IRPrinterObj::VarDefInternal(VarInfo var_info,  // NOLINT(*-value-param)
                                         const ObjectRef& obj, const Optional<ObjectRef>& _frame) {
  ObjectRef frame_ref = _frame.has_value() ? _frame.value() : this->frames.back().cast<ObjectRef>();
  obj2info.Set(obj, var_info);
  auto it = frame_vars.find(frame_ref);
  if (it == frame_vars.end()) {
    TVM_FFI_THROW(KeyError) << "Frame is not pushed to IRPrinter: "
                            << frame_ref.get()->GetTypeKey();
  } else {
    frame_vars[frame_ref].cast<List<Any>>().push_back(obj);
  }
}

inline void IRPrinterObj::VarRemove(const ObjectRef& obj) {
  auto it = obj2info.find(obj);
  if (it == obj2info.end()) {
    TVM_FFI_THROW(KeyError) << "No such object: " << obj.get()->GetTypeKey();
  }
  Optional<String> name = (*it).second->name;
  if (name.has_value()) {
    defined_names.erase(name.value());
  }
  obj2info.erase(obj);
}

inline Optional<ExprAST> IRPrinterObj::VarGet(const ObjectRef& obj) {
  auto it = obj2info.find(obj);
  if (it == obj2info.end()) {
    return Optional<ExprAST>{};
  }
  return (*it).second->creator().cast<ExprAST>();
}

inline Any IRPrinterObj::operator()(Any source, AccessPath path) const {  // NOLINT(*-value-param)
  int32_t ti = source.type_index();
  if (ti == TypeIndex::kTVMFFINone) {
    return LiteralAST::Null({path});
  }
  if (ti == TypeIndex::kTVMFFIBool) {
    return LiteralAST::Bool(source.cast<bool>(), {path});
  }
  if (ti == TypeIndex::kTVMFFIInt) {
    return LiteralAST::Int(source.cast<int64_t>(), {path});
  }
  if (ti == TypeIndex::kTVMFFIStr || ti == TypeIndex::kTVMFFISmallStr ||
      ti == TypeIndex::kTVMFFIRawStr) {
    return LiteralAST::Str(source.cast<String>(), {path});
  }
  if (ti == TypeIndex::kTVMFFIFloat) {
    return LiteralAST::Float(source.cast<double>(), {path});
  }
  if (ti < TypeIndex::kTVMFFIStaticObjectBegin) {
    TVM_FFI_THROW(ValueError) << "Unsupported type index: " << ti;
  }
  IRPrinter self_ref = GetRef<IRPrinter>(this);
  NodeAST ret = IRPrintDispatch(AnyView(source), AnyView(self_ref), AnyView(path));
  const_cast<NodeASTObj*>(ret.get())->source_paths.push_back(path);
  return ret;
}

inline void IRPrinterObj::FramePush(const ObjectRef& frame) {
  frames.push_back(frame);
  frame_vars.Set(frame, List<Any>());
}

inline void IRPrinterObj::FramePop() {
  ObjectRef frame = frames.back().cast<ObjectRef>();
  for (Any var_any : frame_vars[frame].cast<List<Any>>()) {
    this->VarRemove(var_any.cast<ObjectRef>());
  }
  frame_vars.erase(frame);
  frames.pop_back();
}

}  // namespace text
}  // namespace ir
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_IR_TEXT_PRINTER_H_
