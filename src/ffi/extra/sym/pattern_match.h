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

#ifndef TVM_FFI_EXTRA_SYM_PATTERN_MATCH_H_
#define TVM_FFI_EXTRA_SYM_PATTERN_MATCH_H_

#include <cmath>
#include <tuple>

#include "./expr_functor.h"
#include "./utils.h"

namespace tvm {
namespace ffi {
namespace std_ {

template <typename Derived>
struct Pattern {
  template <typename T>
  bool Match(const T& value) const {
    derived().InitMatch_();
    return derived().Match_(value);
  }

  template <typename T, typename Cond>
  bool Match(const T& value, Cond cond) const {
    derived().InitMatch_();
    return derived().Match_(value) && cond();
  }

  const Derived& derived() const { return *static_cast<const Derived*>(this); }

 private:
  friend Derived;
  Pattern() = default;
};

template <typename T>
struct Equivalent {
  bool operator()(const T& lhs, const T& rhs) const { return lhs == rhs; }
};

template <>
struct Equivalent<Expr> {
  bool operator()(const Expr& lhs, const Expr& rhs) const {
    if (lhs.same_as(rhs)) return true;
    return ExprDeepEqual::Compare(lhs, rhs);
  }
};

template <>
struct Equivalent<IntImm> {
  bool operator()(const IntImm& lhs, const IntImm& rhs) const {
    return lhs->value == rhs->value && DTypeOf(lhs) == DTypeOf(rhs);
  }
};

template <>
struct Equivalent<FloatImm> {
  bool operator()(const FloatImm& lhs, const FloatImm& rhs) const {
    return DTypeOf(lhs) == DTypeOf(rhs) && std::fabs(lhs->value - rhs->value) < 1e-20;
  }
};

template <>
struct Equivalent<BoolImm> {
  bool operator()(const BoolImm& lhs, const BoolImm& rhs) const {
    return lhs->value == rhs->value && DTypeOf(lhs) == DTypeOf(rhs);
  }
};

template <>
struct Equivalent<Var> {
  bool operator()(const Var& lhs, const Var& rhs) const { return lhs.same_as(rhs); }
};

template <typename T>
class PVar : public Pattern<PVar<T>> {
 public:
  PVar() : value_(std::make_shared<std::optional<T>>()) {}

  void InitMatch_() const { *value_ = std::nullopt; }

  bool Match_(const T& value) const {
    if (!*value_) {
      *value_ = value;
      return true;
    }
    return Equivalent<T>()(**value_, value);
  }

  template <typename U>
  bool Match_(const U& value) const {
    if constexpr (std::is_base_of_v<ObjectRef, T> && std::is_base_of_v<ObjectRef, U>) {
      if (value.template as<typename T::ContainerType>() != nullptr) {
        return Match_(
            T(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<typename T::ContainerType>(
                const_cast<typename T::ContainerType*>(
                    static_cast<const typename T::ContainerType*>(
                        value.template as<typename T::ContainerType>())))));
      }
    }
    return false;
  }

  T Eval() const {
    if (!*value_) {
      TVM_FFI_THROW(InternalError) << "PVar is not filled";
    }
    return **value_;
  }

  T EvalOr(const T& default_value) const { return value_->value_or(default_value); }

 private:
  std::shared_ptr<std::optional<T>> value_;
};

template <typename T>
class PConst : public Pattern<PConst<T>> {
 public:
  explicit PConst(T value) : value_(std::move(value)) {}

  void InitMatch_() const {}

  bool Match_(const T& value) const { return Equivalent<T>()(value_, value); }

  T Eval() const { return value_; }

 private:
  T value_;
};

template <typename T>
class PMatchesOneOf : public Pattern<PMatchesOneOf<T>> {
 public:
  template <typename... Args>
  explicit PMatchesOneOf(Args&&... args) : args_(std::forward<Args>(args)...) {}

  void InitMatch_() const {}

  bool Match_(const Expr& value) const {
    return std::apply(
        [&](const auto&... args) {
          bool matched = false;
          ((matched = matched || args.Match(value)), ...);
          return matched;
        },
        args_);
  }

  Expr Eval() const {
    TVM_FFI_THROW(InternalError) << "PMatchesOneOf cannot be evaluated";
    TVM_FFI_UNREACHABLE();
  }

 private:
  T args_;
};

template <typename... Args>
PMatchesOneOf(Args&&...) -> PMatchesOneOf<std::tuple<std::decay_t<Args>...>>;

template <typename... Args>
inline auto matches_one_of(Args&&... args) {
  return PMatchesOneOf<std::tuple<std::decay_t<Args>...>>(std::forward<Args>(args)...);
}

template <typename TA>
class PConstWithTypeLike : public Pattern<PConstWithTypeLike<TA>> {
 public:
  PConstWithTypeLike(TA ref, int64_t value) : ref_(std::move(ref)), value_(value) {}

  void InitMatch_() const {}

  bool Match_(const Expr& value) const {
    if (const IntImmObj* ptr = value.as<IntImmObj>()) {
      return ptr->value == value_;
    }
    if (const BoolImmObj* ptr = value.as<BoolImmObj>()) {
      return ptr->value == (value_ != 0);
    }
    return false;
  }

  Expr Eval() const { return Const(DTypeOf(ref_.Eval()), value_); }

 private:
  TA ref_;
  int64_t value_;
};

template <typename OpObj>
struct BinaryOpMaker;

#define TVM_FFI_SYM_DEFINE_BINARY_MAKER(ObjName, FuncName)                            \
  template <>                                                                         \
  struct BinaryOpMaker<ObjName> {                                                     \
    static Expr Make(Expr a, Expr b) { return FuncName(std::move(a), std::move(b)); } \
  }

TVM_FFI_SYM_DEFINE_BINARY_MAKER(AddObj, add);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(SubObj, sub);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(MulObj, mul);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(CDivObj, truncdiv);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(CModObj, truncmod);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(FloorDivObj, floordiv);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(FloorModObj, floormod);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(MinObj, min);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(MaxObj, max);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(EqObj, equal);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(NeObj, not_equal);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(LtObj, less);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(LeObj, less_equal);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(GtObj, greater);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(GeObj, greater_equal);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(AndObj, logical_and);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(OrObj, logical_or);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(LShiftObj, left_shift);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(RShiftObj, right_shift);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(BitwiseAndObj, bitwise_and);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(BitwiseOrObj, bitwise_or);
TVM_FFI_SYM_DEFINE_BINARY_MAKER(BitwiseXorObj, bitwise_xor);

#undef TVM_FFI_SYM_DEFINE_BINARY_MAKER

template <typename OpObj>
inline Optional<Expr> TryConstFold(Expr a, Expr b) {
  Expr ret = BinaryOpMaker<OpObj>::Make(std::move(a), std::move(b));
  if (ret.as<OpObj>() == nullptr) {
    return ret;
  }
  return std::nullopt;
}

template <typename OpObj>
inline Optional<Expr> TryConstFold(Expr a) {
  Expr ret;
  if constexpr (std::is_same_v<OpObj, NotObj>) {
    ret = logical_not(std::move(a));
  } else if constexpr (std::is_same_v<OpObj, BitwiseNotObj>) {
    ret = bitwise_not(std::move(a));
  } else if constexpr (std::is_same_v<OpObj, AbsObj>) {
    ret = abs(std::move(a));
  } else {
    TVM_FFI_THROW(InternalError) << "Unsupported unary constant fold";
  }
  if (ret.as<OpObj>() == nullptr) {
    return ret;
  }
  return std::nullopt;
}

template <typename OpObj, typename TA, typename TB>
class PBinaryExpr : public Pattern<PBinaryExpr<OpObj, TA, TB>> {
 public:
  PBinaryExpr(TA a, TB b) : a_(std::move(a)), b_(std::move(b)) {}

  void InitMatch_() const {
    a_.InitMatch_();
    b_.InitMatch_();
  }

  bool Match_(const Expr& value) const {
    if (const OpObj* ptr = value.as<OpObj>()) {
      return a_.Match_(ptr->a) && b_.Match_(ptr->b);
    }
    return false;
  }

  Expr Eval() const { return BinaryOpMaker<OpObj>::Make(a_.Eval(), b_.Eval()); }

 private:
  TA a_;
  TB b_;
};

template <typename TA>
class PNotExpr : public Pattern<PNotExpr<TA>> {
 public:
  explicit PNotExpr(TA value) : value_(std::move(value)) {}

  void InitMatch_() const { value_.InitMatch_(); }

  bool Match_(const Expr& value) const {
    if (const NotObj* ptr = value.as<NotObj>()) {
      return value_.Match_(ptr->operand);
    }
    return false;
  }

  Expr Eval() const { return logical_not(value_.Eval()); }

 private:
  TA value_;
};

template <typename TCond, typename TTrue, typename TFalse>
class PSelectExpr : public Pattern<PSelectExpr<TCond, TTrue, TFalse>> {
 public:
  PSelectExpr(TCond condition, TTrue true_value, TFalse false_value)
      : condition_(std::move(condition)),
        true_value_(std::move(true_value)),
        false_value_(std::move(false_value)) {}

  void InitMatch_() const {
    condition_.InitMatch_();
    true_value_.InitMatch_();
    false_value_.InitMatch_();
  }

  bool Match_(const Expr& value) const {
    if (const IfExprObj* ptr = value.as<IfExprObj>()) {
      return condition_.Match_(ptr->cond) && true_value_.Match_(ptr->then_expr) &&
             false_value_.Match_(ptr->else_expr);
    }
    return false;
  }

  Expr Eval() const { return select(condition_.Eval(), true_value_.Eval(), false_value_.Eval()); }

 private:
  TCond condition_;
  TTrue true_value_;
  TFalse false_value_;
};

template <typename TDType, typename TValue>
class PCastExpr : public Pattern<PCastExpr<TDType, TValue>> {
 public:
  PCastExpr(TDType dtype, TValue value) : dtype_(std::move(dtype)), value_(std::move(value)) {}

  void InitMatch_() const {
    dtype_.InitMatch_();
    value_.InitMatch_();
  }

  bool Match_(const Expr& value) const {
    if (const CastObj* ptr = value.as<CastObj>()) {
      return dtype_.Match_(DTypeOf(ptr->ty)) && value_.Match_(ptr->value);
    }
    return false;
  }

  Expr Eval() const { return CastDType(dtype_.Eval(), value_.Eval()); }

 private:
  TDType dtype_;
  TValue value_;
};

template <typename TDType, typename TValue>
inline PCastExpr<TDType, TValue> cast(const Pattern<TDType>& dtype, const Pattern<TValue>& value) {
  return PCastExpr<TDType, TValue>(dtype.derived(), value.derived());
}

#define TVM_FFI_SYM_PATTERN_BINARY(FuncName, ObjName)                                             \
  template <typename TA, typename TB>                                                             \
  inline PBinaryExpr<ObjName##Obj, TA, TB> FuncName(const Pattern<TA>& a, const Pattern<TB>& b) { \
    return PBinaryExpr<ObjName##Obj, TA, TB>(a.derived(), b.derived());                           \
  }                                                                                               \
  template <typename TA>                                                                          \
  inline PBinaryExpr<ObjName##Obj, TA, PConstWithTypeLike<TA>> FuncName(const Pattern<TA>& a,     \
                                                                        int64_t b) {              \
    return FuncName(a, PConstWithTypeLike<TA>(a.derived(), b));                                   \
  }                                                                                               \
  template <typename TA>                                                                          \
  inline PBinaryExpr<ObjName##Obj, PConstWithTypeLike<TA>, TA> FuncName(int64_t a,                \
                                                                        const Pattern<TA>& b) {   \
    return FuncName(PConstWithTypeLike<TA>(b.derived(), a), b);                                   \
  }

TVM_FFI_SYM_PATTERN_BINARY(operator+, Add)
TVM_FFI_SYM_PATTERN_BINARY(operator-, Sub)
TVM_FFI_SYM_PATTERN_BINARY(operator*, Mul)
TVM_FFI_SYM_PATTERN_BINARY(min, Min)
TVM_FFI_SYM_PATTERN_BINARY(max, Max)
TVM_FFI_SYM_PATTERN_BINARY(truncdiv, CDiv)
TVM_FFI_SYM_PATTERN_BINARY(div, CDiv)
TVM_FFI_SYM_PATTERN_BINARY(truncmod, CMod)
TVM_FFI_SYM_PATTERN_BINARY(floordiv, FloorDiv)
TVM_FFI_SYM_PATTERN_BINARY(floormod, FloorMod)
TVM_FFI_SYM_PATTERN_BINARY(operator>, Gt)
TVM_FFI_SYM_PATTERN_BINARY(operator>=, Ge)
TVM_FFI_SYM_PATTERN_BINARY(operator<, Lt)
TVM_FFI_SYM_PATTERN_BINARY(operator<=, Le)
TVM_FFI_SYM_PATTERN_BINARY(operator==, Eq)
TVM_FFI_SYM_PATTERN_BINARY(operator!=, Ne)
TVM_FFI_SYM_PATTERN_BINARY(operator&&, And)
TVM_FFI_SYM_PATTERN_BINARY(operator||, Or)
TVM_FFI_SYM_PATTERN_BINARY(operator<<, LShift)
TVM_FFI_SYM_PATTERN_BINARY(operator>>, RShift)
TVM_FFI_SYM_PATTERN_BINARY(operator&, BitwiseAnd)
TVM_FFI_SYM_PATTERN_BINARY(operator|, BitwiseOr)
TVM_FFI_SYM_PATTERN_BINARY(operator^, BitwiseXor)

#undef TVM_FFI_SYM_PATTERN_BINARY

template <typename TA>
inline PNotExpr<TA> operator!(const Pattern<TA>& a) {
  return PNotExpr<TA>(a.derived());
}

template <typename TCond, typename TTrue, typename TFalse>
inline PSelectExpr<TCond, TTrue, TFalse> select(const Pattern<TCond>& condition,
                                                const Pattern<TTrue>& true_value,
                                                const Pattern<TFalse>& false_value) {
  return PSelectExpr<TCond, TTrue, TFalse>(condition.derived(), true_value.derived(),
                                           false_value.derived());
}

template <typename TCond, typename TTrue, typename TFalse>
inline PSelectExpr<TCond, TTrue, TFalse> if_then_else(const Pattern<TCond>& condition,
                                                      const Pattern<TTrue>& true_value,
                                                      const Pattern<TFalse>& false_value) {
  return select(condition, true_value, false_value);
}

template <typename... Args>
class PUnsupportedVectorExpr : public Pattern<PUnsupportedVectorExpr<Args...>> {
 public:
  explicit PUnsupportedVectorExpr(const Args&... args) : args_(args...) {}

  void InitMatch_() const {
    std::apply([](const auto&... args) { (args.InitMatch_(), ...); }, args_);
  }

  bool Match_(const Expr&) const { return false; }

  Expr Eval() const {
    TVM_FFI_THROW(RuntimeError) << "Vector symbolic patterns are not supported for ffi.std.Expr";
    TVM_FFI_UNREACHABLE();
  }

 private:
  std::tuple<Args...> args_;
};

template <typename TValue, typename TLanes>
inline PUnsupportedVectorExpr<TValue, TLanes> broadcast(const Pattern<TValue>& value,
                                                        const Pattern<TLanes>& lanes) {
  return PUnsupportedVectorExpr<TValue, TLanes>(value.derived(), lanes.derived());
}

template <typename TBase, typename TStride, typename TLanes>
inline PUnsupportedVectorExpr<TBase, TStride, TLanes> ramp(const Pattern<TBase>& base,
                                                           const Pattern<TStride>& stride,
                                                           const Pattern<TLanes>& lanes) {
  return PUnsupportedVectorExpr<TBase, TStride, TLanes>(base.derived(), stride.derived(),
                                                        lanes.derived());
}

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_PATTERN_MATCH_H_
