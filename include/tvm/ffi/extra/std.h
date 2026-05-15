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
/*!
 * \file tvm/ffi/extra/std.h
 * \brief Standard core dialect node definitions.
 */
#ifndef TVM_FFI_EXTRA_STD_H_
#define TVM_FFI_EXTRA_STD_H_

#include <tvm/ffi/any.h>
#include <tvm/ffi/container/dict.h>
#include <tvm/ffi/container/list.h>
#include <tvm/ffi/dtype.h>
#include <tvm/ffi/extra/dataclass.h>
#include <tvm/ffi/extra/structural_equal.h>
#include <tvm/ffi/object.h>
#include <tvm/ffi/optional.h>
#include <tvm/ffi/string.h>

#include <utility>

namespace tvm {
namespace ffi {
namespace std_ {
struct Ty;
struct Expr;
namespace details {
inline void CheckDerivedOperandTy(const char* node_name, const char* operand_name,
                                  const Ty& result_ty, const Expr& operand);
inline void CheckBinaryDerivedOperandTys(const char* node_name, const Ty& result_ty, const Expr& a,
                                         const Expr& b);
inline Expr CoerceInitArgToExpr(AnyView value, const Ty& result_ty);
template <typename Obj>
inline ObjectPtr<Obj> MakeBinaryObj(const char* node_name, Ty ty, Expr a, Expr b);
template <typename Obj>
inline ObjectPtr<Obj> MakeUnaryObj(const char* node_name, Ty ty, Expr operand);
}  // namespace details

/*! \brief Base object for all standard dialect nodes. */
struct NodeObj : public Object {
  /// \cond Doxygen_Suppress
  static constexpr bool _type_mutable = true;
  static constexpr TVMFFISEqHashKind _type_s_eq_hash_kind = kTVMFFISEqHashKindTreeNode;
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Node", NodeObj, Object);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect node. */
struct Node : public ObjectRef {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Node, ObjectRef, NodeObj);
  /// \endcond
};

/*! \brief Base object for standard dialect type nodes. */
struct TyObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Ty", TyObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect type node. */
struct Ty : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Ty, Node, TyObj);
  /// \endcond
};

/*! \brief Base object for attribute containers. */
struct AttrsObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Attrs", AttrsObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to an attribute container. */
struct Attrs : public Node {
  /*! \brief Convert a general FFI value into an attribute container. */
  static Attrs FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Attrs, Node, AttrsObj);
  /// \endcond
};

/*! \brief Base object for standard dialect statement nodes. */
struct StmtObj : public NodeObj {
  /*! \brief Optional statement attributes. */
  Optional<Attrs> attrs;

  /// \cond Doxygen_Suppress
  StmtObj() = default;
  explicit StmtObj(Optional<Attrs> attrs) : attrs(std::move(attrs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Stmt", StmtObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect statement node. */
struct Stmt : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Stmt, Node, StmtObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Attrs> = false;

template <>
struct TypeTraits<std_::Attrs> : public ObjectRefTypeTraitsBase<std_::Attrs> {
  using Base = ObjectRefTypeTraitsBase<std_::Attrs>;

  TVM_FFI_INLINE static std::optional<std_::Attrs> TryCastFromAnyView(const TVMFFIAny* src);
};

namespace std_ {

/*! \brief Base object for standard dialect aggregate helper nodes. */
struct AggregateObj : public NodeObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Aggregate", AggregateObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect aggregate helper node. */
struct Aggregate : public Node {
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Aggregate, Node, AggregateObj);
  /// \endcond
};

/*! \brief Base object for standard dialect expression nodes. */
struct ExprObj : public NodeObj {
  /*! \brief Static type of the expression. */
  Ty ty;

  /// \cond Doxygen_Suppress
  ExprObj() = default;
  explicit ExprObj(Ty ty) : ty(std::move(ty)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Expr", ExprObj, NodeObj);
  /// \endcond
};

/*! \brief Nullable reference to a standard dialect expression node. */
struct Expr : public Node {
  /*! \brief Construct an expression with a static type. */
  explicit Expr(Ty ty) : Expr(make_object<ExprObj>(std::move(ty))) {}
  /*! \brief Convert a general FFI value into an expression. */
  static Expr FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Expr, Node, ExprObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Expr> = false;

template <>
struct TypeTraits<std_::Expr> : public ObjectRefTypeTraitsBase<std_::Expr> {
  using Base = ObjectRefTypeTraitsBase<std_::Expr>;

  TVM_FFI_INLINE static std::optional<std_::Expr> TryCastFromAnyView(const TVMFFIAny* src);
};

namespace std_ {

/*! \brief Data object for a named SSA variable. */
struct VarObj : public ExprObj {
  /*! \brief Variable name. */
  String name;

  /// \cond Doxygen_Suppress
  VarObj() = default;
  VarObj(Ty ty, String name) : ExprObj(std::move(ty)), name(std::move(name)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Var", VarObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a named SSA variable. */
struct Var : public Expr {
  /*! \brief Construct a named SSA variable. */
  Var(Ty ty, String name) : Var(make_object<VarObj>(std::move(ty), std::move(name))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Var, Expr, VarObj);
  /// \endcond
};

/*! \brief Data object for a standard dialect function. */
struct FuncObj : public StmtObj {
  /*! \brief Function symbol name. */
  String symbol;
  /*! \brief Function parameters. */
  List<Var> args;
  /*! \brief Optional return type. */
  Optional<Ty> ret_type;
  /*! \brief Function body statements. */
  List<Stmt> body;

  /// \cond Doxygen_Suppress
  FuncObj() = default;
  FuncObj(String symbol, Optional<Attrs> attrs, List<Var> args, Optional<Ty> ret_type,
          List<Stmt> body)
      : StmtObj(std::move(attrs)),
        symbol(std::move(symbol)),
        args(std::move(args)),
        ret_type(std::move(ret_type)),
        body(std::move(body)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Func", FuncObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a standard dialect function. */
struct Func : public Stmt {
  /*! \brief Construct a standard dialect function. */
  Func(String symbol, Optional<Attrs> attrs, List<Var> args, Optional<Ty> ret_type, List<Stmt> body)
      : Func(make_object<FuncObj>(std::move(symbol), std::move(attrs), std::move(args),
                                  std::move(ret_type), std::move(body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Func, Stmt, FuncObj);
  /// \endcond
};

/*! \brief Data object for a module containing standard dialect functions. */
struct ModuleObj : public NodeObj {
  /*! \brief Functions contained by the module. */
  List<Func> funcs;

  /// \cond Doxygen_Suppress
  ModuleObj() = default;
  explicit ModuleObj(List<Func> funcs) : funcs(std::move(funcs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Module", ModuleObj, NodeObj);
  /// \endcond
};

/*! \brief Reference wrapper for a module containing standard dialect functions. */
struct Module : public Node {
  /*! \brief Construct a module from its function list. */
  explicit Module(List<Func> funcs) : Module(make_object<ModuleObj>(std::move(funcs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Module, Node, ModuleObj);
  /// \endcond
};

/*! \brief Data object for a half-open iteration or indexing range. */
struct RangeObj : public AggregateObj {
  /*! \brief Optional range start. */
  Optional<Expr> start;
  /*! \brief Optional range stop. */
  Optional<Expr> stop;
  /*! \brief Optional range step. */
  Optional<Expr> step;

  /// \cond Doxygen_Suppress
  RangeObj() = default;
  explicit RangeObj(Optional<Expr> start, Optional<Expr> stop = {}, Optional<Expr> step = {})
      : start(std::move(start)), stop(std::move(stop)), step(std::move(step)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Range", RangeObj, AggregateObj);
  /// \endcond
};

/*! \brief Reference wrapper for a half-open iteration or indexing range. */
struct Range : public Aggregate {
  /*! \brief Construct a half-open range. */
  explicit Range(Optional<Expr> start, Optional<Expr> stop = {}, Optional<Expr> step = {})
      : Range(make_object<RangeObj>(std::move(start), std::move(stop), std::move(step))) {}
  /*! \brief Convert a general FFI value into a range. */
  static Range FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Range, Aggregate, RangeObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Range> = false;

template <>
struct TypeTraits<std_::Range> : public ObjectRefTypeTraitsBase<std_::Range> {
  using Base = ObjectRefTypeTraitsBase<std_::Range>;

  TVM_FFI_INLINE static std::optional<std_::Range> TryCastFromAnyView(const TVMFFIAny* src);
};

namespace std_ {

/*! \brief Data object for the dynamically typed top type. */
struct AnyTyObj : public TyObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.AnyTy", AnyTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for the dynamically typed top type. */
struct AnyTy : public Ty {
  /// \cond Doxygen_Suppress
  explicit AnyTy(ObjectPtr<AnyTyObj> ptr) : Ty(ObjectPtr<TyObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct the dynamically typed top type. */
  AnyTy() : AnyTy(make_object<AnyTyObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(AnyTy, Ty, AnyTyObj);
  /// \endcond
};

/*! \brief Data object for a scalar primitive type. */
struct PrimTyObj : public TyObj {
  /*! \brief Primitive scalar data type. */
  DLDataType dtype;

  /// \cond Doxygen_Suppress
  PrimTyObj() = default;
  explicit PrimTyObj(DLDataType dtype) : dtype(dtype) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.PrimTy", PrimTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a scalar primitive type. */
struct PrimTy : public Ty {
  /*! \brief Construct a scalar primitive type. */
  explicit PrimTy(DLDataType dtype) : PrimTy(make_object<PrimTyObj>(dtype)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(PrimTy, Ty, PrimTyObj);
  /// \endcond
};

/*! \brief Data object for a tuple type. */
struct TupleTyObj : public TyObj {
  /*! \brief Tuple field types. */
  List<Ty> fields;

  /// \cond Doxygen_Suppress
  TupleTyObj() = default;
  explicit TupleTyObj(List<Ty> fields) : fields(std::move(fields)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.TupleTy", TupleTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a tuple type. */
struct TupleTy : public Ty {
  /*! \brief Construct a tuple type from field types. */
  explicit TupleTy(List<Ty> fields) : TupleTy(make_object<TupleTyObj>(std::move(fields))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TupleTy, Ty, TupleTyObj);
  /// \endcond
};

/*! \brief Data object for a tensor type. */
struct TensorTyObj : public TyObj {
  /*! \brief Tensor shape expressions. */
  List<Expr> shape;
  /*! \brief Tensor element data type. */
  DLDataType dtype;

  /// \cond Doxygen_Suppress
  TensorTyObj() = default;
  TensorTyObj(List<Expr> shape, DLDataType dtype) : shape(std::move(shape)), dtype(dtype) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.TensorTy", TensorTyObj, TyObj);
  /// \endcond
};

/*! \brief Reference wrapper for a tensor type. */
struct TensorTy : public Ty {
  /*! \brief Construct a tensor type from shape expressions and element type. */
  TensorTy(List<Expr> shape, DLDataType dtype)
      : TensorTy(make_object<TensorTyObj>(std::move(shape), dtype)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TensorTy, Ty, TensorTyObj);
  /// \endcond
};

/*! \brief Data object for a boolean literal. */
struct BoolImmObj : public ExprObj {
  /*! \brief Boolean literal value. */
  bool value = false;

  /// \cond Doxygen_Suppress
  BoolImmObj() = default;
  BoolImmObj(Ty ty, bool value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BoolImm", BoolImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a boolean literal. */
struct BoolImm : public Expr {
  /*! \brief Construct a boolean literal. */
  BoolImm(Ty ty, bool value) : BoolImm(make_object<BoolImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BoolImm, Expr, BoolImmObj);
  /// \endcond
};

/*! \brief Data object for an integer literal. */
struct IntImmObj : public ExprObj {
  /*! \brief Integer literal value. */
  int64_t value = 0;

  /// \cond Doxygen_Suppress
  IntImmObj() = default;
  IntImmObj(Ty ty, int64_t value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IntImm", IntImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for an integer literal. */
struct IntImm : public Expr {
  /*! \brief Construct an integer literal. */
  IntImm(Ty ty, int64_t value) : IntImm(make_object<IntImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IntImm, Expr, IntImmObj);
  /// \endcond
};

/*! \brief Data object for a floating-point literal. */
struct FloatImmObj : public ExprObj {
  /*! \brief Floating-point literal value. */
  double value = 0.0;

  /// \cond Doxygen_Suppress
  FloatImmObj() = default;
  FloatImmObj(Ty ty, double value) : ExprObj(std::move(ty)), value(value) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.FloatImm", FloatImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a floating-point literal. */
struct FloatImm : public Expr {
  /*! \brief Construct a floating-point literal. */
  FloatImm(Ty ty, double value) : FloatImm(make_object<FloatImmObj>(std::move(ty), value)) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(FloatImm, Expr, FloatImmObj);
  /// \endcond
};

/*! \brief Data object for a string literal. */
struct StringImmObj : public ExprObj {
  /*! \brief String literal value. */
  String value;

  /// \cond Doxygen_Suppress
  StringImmObj() = default;
  StringImmObj(Ty ty, String value) : ExprObj(std::move(ty)), value(std::move(value)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.StringImm", StringImmObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a string literal. */
struct StringImm : public Expr {
  /*! \brief Construct a string literal. */
  StringImm(Ty ty, String value)
      : StringImm(make_object<StringImmObj>(std::move(ty), std::move(value))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(StringImm, Expr, StringImmObj);
  /// \endcond
};

/*! \brief Define the object and reference wrapper for a standard binary expression node. */
#define TVM_FFI_STD_BINARY_EXPR(TypeName)                                                        \
  /*! \brief Data object for a binary expression. */                                             \
  struct TypeName##Obj : public ExprObj {                                                        \
    /*! \brief Left operand. */                                                                  \
    Expr a;                                                                                      \
    /*! \brief Right operand. */                                                                 \
    Expr b;                                                                                      \
                                                                                                 \
    /** \cond Doxygen_Suppress */                                                                \
    TypeName##Obj() = default;                                                                   \
    TypeName##Obj(Ty ty, Expr a, Expr b)                                                         \
        : ExprObj(std::move(ty)), a(std::move(a)), b(std::move(b)) {                             \
      details::CheckBinaryDerivedOperandTys(#TypeName, this->ty, this->a, this->b);              \
    }                                                                                            \
    TypeName##Obj(Expr a, Expr b, Ty ty)                                                         \
        : TypeName##Obj(std::move(ty), std::move(a), std::move(b)) {}                            \
    TypeName##Obj(AnyView a, AnyView b, const Ty& ty)                                            \
        : TypeName##Obj(ty, details::CoerceInitArgToExpr(a, ty),                                 \
                        details::CoerceInitArgToExpr(b, ty)) {}                                  \
                                                                                                 \
    TVM_FFI_DECLARE_OBJECT_INFO("ffi.std." #TypeName, TypeName##Obj, ExprObj);                   \
    /** \endcond */                                                                              \
  };                                                                                             \
                                                                                                 \
  /*! \brief Reference wrapper for a binary expression. */                                       \
  struct TypeName : public Expr {                                                                \
    /*! \brief Construct a binary expression. */                                                 \
    TypeName(Ty ty, Expr a, Expr b)                                                              \
        : TypeName(details::MakeBinaryObj<TypeName##Obj>(#TypeName, std::move(ty), std::move(a), \
                                                         std::move(b))) {}                       \
    /** \cond Doxygen_Suppress */                                                                \
    TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(TypeName, Expr, TypeName##Obj);                   \
    /** \endcond */                                                                              \
  }

TVM_FFI_STD_BINARY_EXPR(Add);
TVM_FFI_STD_BINARY_EXPR(Sub);
TVM_FFI_STD_BINARY_EXPR(Mul);
TVM_FFI_STD_BINARY_EXPR(CDiv);
TVM_FFI_STD_BINARY_EXPR(FloorDiv);
TVM_FFI_STD_BINARY_EXPR(FloorMod);
TVM_FFI_STD_BINARY_EXPR(CMod);
TVM_FFI_STD_BINARY_EXPR(Pow);
TVM_FFI_STD_BINARY_EXPR(LShift);
TVM_FFI_STD_BINARY_EXPR(RShift);
TVM_FFI_STD_BINARY_EXPR(Xor);
TVM_FFI_STD_BINARY_EXPR(Min);
TVM_FFI_STD_BINARY_EXPR(Max);
TVM_FFI_STD_BINARY_EXPR(Eq);
TVM_FFI_STD_BINARY_EXPR(Ne);
TVM_FFI_STD_BINARY_EXPR(Le);
TVM_FFI_STD_BINARY_EXPR(Ge);
TVM_FFI_STD_BINARY_EXPR(Gt);
TVM_FFI_STD_BINARY_EXPR(Lt);
TVM_FFI_STD_BINARY_EXPR(And);
TVM_FFI_STD_BINARY_EXPR(Or);

#undef TVM_FFI_STD_BINARY_EXPR

/*! \brief Data object for logical negation. */
struct NotObj : public ExprObj {
  /*! \brief Operand to negate. */
  Expr operand;

  /// \cond Doxygen_Suppress
  NotObj() = default;
  NotObj(Ty ty, Expr operand) : ExprObj(std::move(ty)), operand(std::move(operand)) {
    details::CheckDerivedOperandTy("Not", "operand", this->ty, this->operand);
  }
  NotObj(Expr operand, Ty ty) : NotObj(std::move(ty), std::move(operand)) {}
  NotObj(AnyView operand, const Ty& ty) : NotObj(ty, details::CoerceInitArgToExpr(operand, ty)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Not", NotObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for logical negation. */
struct Not : public Expr {
  /*! \brief Construct a logical negation expression. */
  Not(Ty ty, Expr operand)
      : Not(details::MakeUnaryObj<NotObj>("Not", std::move(ty), std::move(operand))) {}
  /*! \brief Convert a general FFI value into a logical negation expression. */
  static Not FromAny(AnyView src);

  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Not, Expr, NotObj);
  /// \endcond
};

}  // namespace std_

template <>
inline constexpr bool use_default_type_traits_v<std_::Not> = false;

template <>
struct TypeTraits<std_::Not> : public ObjectRefTypeTraitsBase<std_::Not> {
  using Base = ObjectRefTypeTraitsBase<std_::Not>;

  TVM_FFI_INLINE static std::optional<std_::Not> TryCastFromAnyView(const TVMFFIAny* src);
};

namespace std_ {

/*! \brief Data object for loading from an expression with indices. */
struct LoadObj : public ExprObj {
  /*! \brief Expression being loaded. */
  Expr lhs;
  /*! \brief Load indices or slices. */
  List<Range> indices;

  /// \cond Doxygen_Suppress
  LoadObj() = default;
  LoadObj(Ty ty, Expr lhs, List<Range> indices)
      : ExprObj(std::move(ty)), lhs(std::move(lhs)), indices(std::move(indices)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Load", LoadObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for loading from an expression with indices. */
struct Load : public Expr {
  /*! \brief Construct a load expression. */
  Load(Ty ty, Expr lhs, List<Range> indices)
      : Load(make_object<LoadObj>(std::move(ty), std::move(lhs), std::move(indices))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Load, Expr, LoadObj);
  /// \endcond
};

/*! \brief Data object for a cast expression. */
struct CastObj : public ExprObj {
  /*! \brief Var being cast. */
  Expr value;

  /// \cond Doxygen_Suppress
  CastObj() = default;
  CastObj(Ty ty, Expr value) : ExprObj(std::move(ty)), value(std::move(value)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Cast", CastObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a cast expression. */
struct Cast : public Expr {
  /*! \brief Construct a cast expression. */
  Cast(Ty ty, Expr value) : Cast(make_object<CastObj>(std::move(ty), std::move(value))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Cast, Expr, CastObj);
  /// \endcond
};

/*! \brief Data object for a call expression. */
struct CallObj : public ExprObj {
  /*! \brief Callee object. */
  Any callee;
  /*! \brief Positional call arguments. */
  List<Expr> args;
  /*! \brief Optional call attributes. */
  Optional<Attrs> attr;

  /// \cond Doxygen_Suppress
  CallObj() = default;
  CallObj(Ty ty, Any callee, List<Expr> args, Optional<Attrs> attr = {})
      : ExprObj(std::move(ty)),
        callee(std::move(callee)),
        args(std::move(args)),
        attr(std::move(attr)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Call", CallObj, ExprObj);
  /// \endcond
};

/*! \brief Reference wrapper for a call expression. */
struct Call : public Expr {
  /*! \brief Construct a call expression. */
  Call(Ty ty, Any callee, List<Expr> args, Optional<Attrs> attr = {})
      : Call(make_object<CallObj>(std::move(ty), std::move(callee), std::move(args),
                                  std::move(attr))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Call, Expr, CallObj);
  /// \endcond
};

/*! \brief Data object for an if statement. */
struct IfStmtObj : public StmtObj {
  /*! \brief Condition expression. */
  Expr cond;
  /*! \brief Statements executed when the condition is true. */
  List<Stmt> then_body;
  /*! \brief Statements executed when the condition is false. */
  List<Stmt> else_body;

  /// \cond Doxygen_Suppress
  IfStmtObj() = default;
  IfStmtObj(Expr cond, List<Stmt> then_body, List<Stmt> else_body)
      : cond(std::move(cond)), then_body(std::move(then_body)), else_body(std::move(else_body)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IfStmt", IfStmtObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for an if statement. */
struct IfStmt : public Stmt {
  /*! \brief Construct an if statement. */
  IfStmt(Expr cond, List<Stmt> then_body, List<Stmt> else_body)
      : IfStmt(
            make_object<IfStmtObj>(std::move(cond), std::move(then_body), std::move(else_body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IfStmt, Stmt, IfStmtObj);
  /// \endcond
};

/*! \brief Data object for binding an expression to variables. */
struct BindExprObj : public StmtObj {
  /*! \brief Variables bound by this statement. */
  List<Var> vars;
  /*! \brief Expression being bound. */
  Expr expr;

  /// \cond Doxygen_Suppress
  BindExprObj() = default;
  BindExprObj(List<Var> vars, Optional<Attrs> attrs, Expr expr)
      : StmtObj(std::move(attrs)), vars(std::move(vars)), expr(std::move(expr)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.BindExpr", BindExprObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for binding an expression to variables. */
struct BindExpr : public Stmt {
  /*! \brief Construct an expression binding. */
  BindExpr(List<Var> vars, Optional<Attrs> attrs, Expr expr)
      : BindExpr(make_object<BindExprObj>(std::move(vars), std::move(attrs), std::move(expr))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(BindExpr, Stmt, BindExprObj);
  /// \endcond
};

/*! \brief Data object for defining variables without a source expression. */
struct VarDefObj : public StmtObj {
  /*! \brief Variables defined by this statement. */
  List<Var> vars;

  /// \cond Doxygen_Suppress
  VarDefObj() = default;
  VarDefObj(List<Var> vars, Optional<Attrs> attrs)
      : StmtObj(std::move(attrs)), vars(std::move(vars)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.VarDef", VarDefObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for defining variables without a source expression. */
struct VarDef : public Stmt {
  /*! \brief Construct a variable definition. */
  VarDef(List<Var> vars, Optional<Attrs> attrs)
      : VarDef(make_object<VarDefObj>(std::move(vars), std::move(attrs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(VarDef, Stmt, VarDefObj);
  /// \endcond
};

/*! \brief Data object for a lexical scope with carried bindings. */
struct ScopeObj : public StmtObj {
  /*! \brief Bindings introduced by the scope. */
  List<Stmt> binds;
  /*! \brief Scope body statements. */
  List<Stmt> body;

  /// \cond Doxygen_Suppress
  ScopeObj() = default;
  ScopeObj(Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : StmtObj(std::move(attrs)), binds(std::move(binds)), body(std::move(body)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Scope", ScopeObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a lexical scope with carried bindings. */
struct Scope : public Stmt {
  /*! \brief Construct a lexical scope. */
  Scope(Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : Scope(make_object<ScopeObj>(std::move(attrs), std::move(binds), std::move(body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Scope, Stmt, ScopeObj);
  /// \endcond
};

/*! \brief Data object for a for loop. */
struct ForObj : public ScopeObj {
  /*! \brief Iteration range. */
  Range range_;

  /// \cond Doxygen_Suppress
  ForObj() = default;
  ForObj(Range range_, Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : ScopeObj(std::move(attrs), std::move(binds), std::move(body)), range_(std::move(range_)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.For", ForObj, ScopeObj);
  /// \endcond
};

/*! \brief Reference wrapper for a for loop. */
struct For : public Scope {
  /*! \brief Construct a for loop. */
  For(Range range_, Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : For(make_object<ForObj>(std::move(range_), std::move(attrs), std::move(binds),
                                std::move(body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(For, Scope, ForObj);
  /// \endcond
};

/*! \brief Data object for a while loop. */
struct WhileObj : public ScopeObj {
  /*! \brief Loop condition. */
  Expr cond;

  /// \cond Doxygen_Suppress
  WhileObj() = default;
  WhileObj(Expr cond, Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : ScopeObj(std::move(attrs), std::move(binds), std::move(body)), cond(std::move(cond)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.While", WhileObj, ScopeObj);
  /// \endcond
};

/*! \brief Reference wrapper for a while loop. */
struct While : public Scope {
  /*! \brief Construct a while loop. */
  While(Expr cond, Optional<Attrs> attrs, List<Stmt> binds, List<Stmt> body)
      : While(make_object<WhileObj>(std::move(cond), std::move(attrs), std::move(binds),
                                    std::move(body))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(While, Scope, WhileObj);
  /// \endcond
};

/*! \brief Data object for storing into an expression with indices. */
struct StoreObj : public StmtObj {
  /*! \brief Expression being stored into. */
  Expr lhs;
  /*! \brief Store indices or slices. */
  List<Range> indices;
  /*! \brief Right-hand side value to store. */
  Expr rhs;

  /// \cond Doxygen_Suppress
  StoreObj() = default;
  StoreObj(Expr lhs, List<Range> indices, Expr rhs)
      : lhs(std::move(lhs)), indices(std::move(indices)), rhs(std::move(rhs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Store", StoreObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for storing into an expression with indices. */
struct Store : public Stmt {
  /*! \brief Construct a store statement. */
  Store(Expr lhs, List<Range> indices, Expr rhs)
      : Store(make_object<StoreObj>(std::move(lhs), std::move(indices), std::move(rhs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Store, Stmt, StoreObj);
  /// \endcond
};

/*! \brief Data object for an assertion statement. */
struct AssertObj : public StmtObj {
  /*! \brief Assertion condition. */
  Expr cond;

  /// \cond Doxygen_Suppress
  AssertObj() = default;
  explicit AssertObj(Expr cond) : cond(std::move(cond)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Assert", AssertObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for an assertion statement. */
struct Assert : public Stmt {
  /*! \brief Construct an assertion statement. */
  explicit Assert(Expr cond) : Assert(make_object<AssertObj>(std::move(cond))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Assert, Stmt, AssertObj);
  /// \endcond
};

/*! \brief Data object for returning expressions from a function. */
struct ReturnObj : public StmtObj {
  /*! \brief Returned expressions. */
  List<Expr> exprs;

  /// \cond Doxygen_Suppress
  ReturnObj() = default;
  explicit ReturnObj(List<Expr> exprs) : exprs(std::move(exprs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Return", ReturnObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for returning expressions from a function. */
struct Return : public Stmt {
  /*! \brief Construct a return statement. */
  explicit Return(List<Expr> exprs) : Return(make_object<ReturnObj>(std::move(exprs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Return, Stmt, ReturnObj);
  /// \endcond
};

/*! \brief Data object for yielding expressions from a resumable scope. */
struct YieldObj : public StmtObj {
  /*! \brief Yielded expressions. */
  List<Expr> exprs;

  /// \cond Doxygen_Suppress
  YieldObj() = default;
  explicit YieldObj(List<Expr> exprs) : exprs(std::move(exprs)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Yield", YieldObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for yielding expressions from a resumable scope. */
struct Yield_ : public Stmt {
  /*! \brief Construct a yield statement. */
  explicit Yield_(List<Expr> exprs) : Yield_(make_object<YieldObj>(std::move(exprs))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(Yield_, Stmt, YieldObj);
  /// \endcond
};

/*! \brief Data object for a break statement. */
struct BreakObj : public StmtObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Break", BreakObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a break statement. */
struct Break : public Stmt {
  /// \cond Doxygen_Suppress
  explicit Break(ObjectPtr<BreakObj> ptr) : Stmt(ObjectPtr<StmtObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct a break statement. */
  Break() : Break(make_object<BreakObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Break, Stmt, BreakObj);
  /// \endcond
};

/*! \brief Data object for a continue statement. */
struct ContinueObj : public StmtObj {
  /// \cond Doxygen_Suppress
  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.Continue", ContinueObj, StmtObj);
  /// \endcond
};

/*! \brief Reference wrapper for a continue statement. */
struct Continue : public Stmt {
  /// \cond Doxygen_Suppress
  explicit Continue(ObjectPtr<ContinueObj> ptr) : Stmt(ObjectPtr<StmtObj>(std::move(ptr))) {}
  /// \endcond
  /*! \brief Construct a continue statement. */
  Continue() : Continue(make_object<ContinueObj>()) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NOTNULLABLE(Continue, Stmt, ContinueObj);
  /// \endcond
};

/*! \brief Data object for dictionary-backed attributes. */
struct DictAttrsObj : public AttrsObj {
  /*! \brief Attribute key-value pairs. */
  Dict<String, Any> values;

  /// \cond Doxygen_Suppress
  DictAttrsObj() = default;
  explicit DictAttrsObj(Dict<String, Any> values) : values(std::move(values)) {}

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.DictAttrs", DictAttrsObj, AttrsObj);
  /// \endcond
};

/*! \brief Reference wrapper for dictionary-backed attributes. */
struct DictAttrs : public Attrs {
  /*! \brief Construct dictionary-backed attributes. */
  explicit DictAttrs(Dict<String, Any> values)
      : DictAttrs(make_object<DictAttrsObj>(std::move(values))) {}
  /// \cond Doxygen_Suppress
  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(DictAttrs, Attrs, DictAttrsObj);
  /// \endcond
};

}  // namespace std_

inline std::optional<std_::Attrs> TypeTraits<std_::Attrs>::TryCastFromAnyView(
    const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std_::DictAttrs(Dict<String, Any>{});
  }
  if (std::optional<std_::Attrs> attrs = Base::TryCastFromAnyView(src)) {
    return attrs;
  }
  if (std::optional<Dict<String, Any>> values =
          TypeTraits<Dict<String, Any>>::TryCastFromAnyView(src)) {
    return std_::DictAttrs(*std::move(values));
  }
  return std::nullopt;
}

inline std::optional<std_::Expr> TypeTraits<std_::Expr>::TryCastFromAnyView(const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Expr> expr = Base::TryCastFromAnyView(src)) {
    return expr;
  }
  if (src->type_index == TypeIndex::kTVMFFIBool) {
    return std_::BoolImm(std_::AnyTy(), TypeTraits<bool>::CopyFromAnyViewAfterCheck(src));
  }
  if (std::optional<int64_t> value = TypeTraits<int64_t>::TryCastFromAnyView(src)) {
    return std_::IntImm(std_::AnyTy(), *value);
  }
  if (src->type_index == TypeIndex::kTVMFFIFloat) {
    return std_::FloatImm(std_::AnyTy(), TypeTraits<double>::CopyFromAnyViewAfterCheck(src));
  }
  if (std::optional<String> value = TypeTraits<String>::TryCastFromAnyView(src)) {
    return std_::StringImm(std_::AnyTy(), *std::move(value));
  }
  return std::nullopt;
}

inline std::optional<std_::Range> TypeTraits<std_::Range>::TryCastFromAnyView(
    const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Range> range = Base::TryCastFromAnyView(src)) {
    return range;
  }
  if (std::optional<std_::Expr> expr =
          ObjectRefTypeTraitsBase<std_::Expr>::TryCastFromAnyView(src)) {
    return std_::Range(*std::move(expr));
  }
  if (std::optional<int64_t> value = TypeTraits<int64_t>::TryCastFromAnyView(src)) {
    return std_::Range(std_::IntImm(std_::AnyTy(), *value));
  }
  if (src->type_index == TypeIndex::kTVMFFIFloat) {
    return std_::Range(
        std_::FloatImm(std_::AnyTy(), TypeTraits<double>::CopyFromAnyViewAfterCheck(src)));
  }
  return std::nullopt;
}

inline std::optional<std_::Not> TypeTraits<std_::Not>::TryCastFromAnyView(const TVMFFIAny* src) {
  if (src->type_index == TypeIndex::kTVMFFINone) {
    return std::nullopt;
  }
  if (std::optional<std_::Not> expr = Base::TryCastFromAnyView(src)) {
    return expr;
  }
  if (std::optional<std_::Expr> expr = TypeTraits<std_::Expr>::TryCastFromAnyView(src)) {
    return std_::Not(std_::AnyTy(), *std::move(expr));
  }
  return std::nullopt;
}

namespace std_ {

inline Attrs Attrs::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Attrs> attrs = TypeTraits<Attrs>::TryCastFromAnyView(&src_any)) {
    return *std::move(attrs);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Attrs: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Expr Expr::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Expr> expr = TypeTraits<Expr>::TryCastFromAnyView(&src_any)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Expr: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Range Range::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Range> range = TypeTraits<Range>::TryCastFromAnyView(&src_any)) {
    return *std::move(range);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Range: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline Not Not::FromAny(AnyView src) {
  TVMFFIAny src_any = src.CopyToTVMFFIAny();
  if (std::optional<Not> expr = TypeTraits<Not>::TryCastFromAnyView(&src_any)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Not: " << src.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

namespace details {
inline Expr CoerceInitArgToExpr(AnyView value, const Ty& result_ty) {
  TVMFFIAny raw = value.CopyToTVMFFIAny();
  if (std::optional<Expr> expr = ObjectRefTypeTraitsBase<Expr>::TryCastFromAnyView(&raw)) {
    return *std::move(expr);
  }

  if (const PrimTyObj* prim_ty = result_ty.as<PrimTyObj>()) {
    if (raw.type_index == TypeIndex::kTVMFFIBool) {
      bool bool_value = TypeTraits<bool>::CopyFromAnyViewAfterCheck(&raw);
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, bool_value);
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, static_cast<int64_t>(bool_value));
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, static_cast<double>(bool_value));
      }
    }
    if (std::optional<int64_t> int_value = TypeTraits<int64_t>::TryCastFromAnyView(&raw)) {
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, static_cast<bool>(*int_value));
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, *int_value);
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, static_cast<double>(*int_value));
      }
    }
    if (raw.type_index == TypeIndex::kTVMFFIFloat) {
      double float_value = TypeTraits<double>::CopyFromAnyViewAfterCheck(&raw);
      if (DTypeIsBool(prim_ty->dtype)) {
        return BoolImm(result_ty, static_cast<bool>(float_value));
      }
      if (DTypeIsInt(prim_ty->dtype)) {
        return IntImm(result_ty, static_cast<int64_t>(float_value));
      }
      if (DTypeIsFloat(prim_ty->dtype)) {
        return FloatImm(result_ty, float_value);
      }
    }
  }

  if (result_ty.as<AnyTyObj>() != nullptr) {
    if (raw.type_index == TypeIndex::kTVMFFIBool) {
      return BoolImm(result_ty, TypeTraits<bool>::CopyFromAnyViewAfterCheck(&raw));
    }
    if (std::optional<int64_t> int_value = TypeTraits<int64_t>::TryCastFromAnyView(&raw)) {
      return IntImm(result_ty, *int_value);
    }
    if (raw.type_index == TypeIndex::kTVMFFIFloat) {
      return FloatImm(result_ty, TypeTraits<double>::CopyFromAnyViewAfterCheck(&raw));
    }
    if (std::optional<String> str_value = TypeTraits<String>::TryCastFromAnyView(&raw)) {
      return StringImm(result_ty, *std::move(str_value));
    }
  }

  if (std::optional<Expr> expr = TypeTraits<Expr>::TryCastFromAnyView(&raw)) {
    return *std::move(expr);
  }
  TVM_FFI_THROW(TypeError) << "Unsupported type for conversion to Expr: " << value.GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

inline void CheckDerivedOperandTy(const char* node_name, const char* operand_name,
                                  const Ty& result_ty, const Expr& operand) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << node_name << " result type must be defined";
  TVM_FFI_CHECK(operand.defined(), TypeError)
      << node_name << " operand `" << operand_name << "` must be defined";
  const Ty& operand_ty = operand->ty;
  TVM_FFI_CHECK(operand_ty.defined(), TypeError)
      << node_name << " operand `" << operand_name << "` type must be defined";

  bool result_is_any = result_ty->IsInstance<AnyTyObj>();
  bool operand_is_any = operand_ty->IsInstance<AnyTyObj>();
  TVM_FFI_CHECK(result_is_any == operand_is_any, TypeError)
      << node_name << " cannot derive result type " << ReprPrint(result_ty) << " from operand `"
      << operand_name << "` with type " << ReprPrint(operand_ty)
      << "; use an explicit Cast or construct operands with matching types";
  if (!result_is_any) {
    TVM_FFI_CHECK(StructuralEqual::Equal(result_ty, operand_ty), TypeError)
        << node_name << " operand `" << operand_name << "` type " << ReprPrint(operand_ty)
        << " does not match result type " << ReprPrint(result_ty);
  }
}

inline void CheckBinaryDerivedOperandTys(const char* node_name, const Ty& result_ty, const Expr& a,
                                         const Expr& b) {
  TVM_FFI_CHECK(result_ty.defined(), TypeError) << node_name << " result type must be defined";
  TVM_FFI_CHECK(a.defined(), TypeError) << node_name << " operand `a` must be defined";
  TVM_FFI_CHECK(b.defined(), TypeError) << node_name << " operand `b` must be defined";
  const Ty& a_ty = a->ty;
  const Ty& b_ty = b->ty;
  TVM_FFI_CHECK(a_ty.defined(), TypeError) << node_name << " operand `a` type must be defined";
  TVM_FFI_CHECK(b_ty.defined(), TypeError) << node_name << " operand `b` type must be defined";

  bool result_is_any = result_ty->IsInstance<AnyTyObj>();
  bool a_is_any = a_ty->IsInstance<AnyTyObj>();
  bool b_is_any = b_ty->IsInstance<AnyTyObj>();
  if (result_is_any) {
    TVM_FFI_CHECK(a_is_any || b_is_any, TypeError)
        << node_name << " cannot derive result type " << ReprPrint(result_ty)
        << " from operands with types " << ReprPrint(a_ty) << " and " << ReprPrint(b_ty)
        << "; use an explicit Cast or construct operands with matching types";
    return;
  }

  TVM_FFI_CHECK(!a_is_any, TypeError)
      << node_name << " cannot derive result type " << ReprPrint(result_ty)
      << " from operand `a` with type " << ReprPrint(a_ty)
      << "; use an explicit Cast or construct operands with matching types";
  TVM_FFI_CHECK(!b_is_any, TypeError)
      << node_name << " cannot derive result type " << ReprPrint(result_ty)
      << " from operand `b` with type " << ReprPrint(b_ty)
      << "; use an explicit Cast or construct operands with matching types";
  TVM_FFI_CHECK(StructuralEqual::Equal(result_ty, a_ty), TypeError)
      << node_name << " operand `a` type " << ReprPrint(a_ty) << " does not match result type "
      << ReprPrint(result_ty);
  TVM_FFI_CHECK(StructuralEqual::Equal(result_ty, b_ty), TypeError)
      << node_name << " operand `b` type " << ReprPrint(b_ty) << " does not match result type "
      << ReprPrint(result_ty);
}

template <typename Obj>
inline ObjectPtr<Obj> MakeBinaryObj(const char* node_name, Ty ty, Expr a, Expr b) {
  CheckBinaryDerivedOperandTys(node_name, ty, a, b);
  return make_object<Obj>(std::move(ty), std::move(a), std::move(b));
}

template <typename Obj>
inline ObjectPtr<Obj> MakeUnaryObj(const char* node_name, Ty ty, Expr operand) {
  CheckDerivedOperandTy(node_name, "operand", ty, operand);
  return make_object<Obj>(std::move(ty), std::move(operand));
}
}  // namespace details
}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_STD_H_
