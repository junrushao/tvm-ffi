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

#ifndef TVM_FFI_EXTRA_SYM_UTILS_H_
#define TVM_FFI_EXTRA_SYM_UTILS_H_

#include <tvm/ffi/extra/std.h>

#include <functional>
#include <limits>
#include <utility>
#include <vector>

namespace tvm {
namespace ffi {
namespace std_ {

inline DLDataType DTypeOf(const Ty& ty) {
  TVM_FFI_CHECK(ty.defined(), TypeError) << "Cannot get dtype from undefined type";
  if (const auto* prim_ty = ty.as<PrimTyObj>()) {
    return prim_ty->dtype;
  }
  TVM_FFI_THROW(TypeError) << "Expected primitive std type, got " << ReprPrint(ty);
  TVM_FFI_UNREACHABLE();
}

inline DLDataType DTypeOf(const Expr& expr) {
  TVM_FFI_CHECK(expr.defined(), TypeError) << "Cannot get dtype from undefined expression";
  return DTypeOf(expr->ty);
}

inline DLDataType DTypeOf(const ExprObj* expr) {
  TVM_FFI_CHECK(expr != nullptr, TypeError) << "Cannot get dtype from null expression";
  return DTypeOf(expr->ty);
}

inline DLDataType DTypeOf(const ExprObj& expr) { return DTypeOf(expr.ty); }

inline Expr Const(DLDataType dtype, int64_t value) {
  Ty ty = PrimTy(dtype);
  if (DTypeIsBool(dtype)) {
    return BoolImm(ty, value != 0);
  }
  if (DTypeIsFloat(dtype)) {
    return FloatImm(ty, static_cast<double>(value));
  }
  return IntImm(ty, value);
}

inline Expr Const(DLDataType dtype, int value) { return Const(dtype, static_cast<int64_t>(value)); }

inline Expr Const(DLDataType dtype, bool value) { return BoolImm(PrimTy(dtype), value); }

inline Expr Const(DLDataType dtype, double value) {
  Ty ty = PrimTy(dtype);
  if (DTypeIsFloat(dtype)) {
    return FloatImm(ty, value);
  }
  if (DTypeIsBool(dtype)) {
    return BoolImm(ty, value != 0.0);
  }
  return IntImm(ty, static_cast<int64_t>(value));
}

inline Expr max_value(DLDataType dtype) {
  if (dtype.code == kDLUInt) {
    if (dtype.bits == 64) return Const(dtype, std::numeric_limits<int64_t>::max());
    return Const(dtype, (int64_t{1} << dtype.bits) - 1);
  }
  if (dtype.code == kDLInt) {
    if (dtype.bits == 64) return Const(dtype, std::numeric_limits<int64_t>::max());
    return Const(dtype, (int64_t{1} << (dtype.bits - 1)) - 1);
  }
  TVM_FFI_THROW(ValueError) << "Cannot decide max_value for type " << DLDataTypeToString(dtype);
  TVM_FFI_UNREACHABLE();
}

inline Expr min_value(DLDataType dtype) {
  if (dtype.code == kDLUInt) {
    return Const(dtype, 0);
  }
  if (dtype.code == kDLInt) {
    if (dtype.bits == 64) return Const(dtype, std::numeric_limits<int64_t>::min());
    return Const(dtype, -(int64_t{1} << (dtype.bits - 1)));
  }
  TVM_FFI_THROW(ValueError) << "Cannot decide min_value for type " << DLDataTypeToString(dtype);
  TVM_FFI_UNREACHABLE();
}

inline Expr RangeMin(const Range& range) {
  if (range->start.has_value()) {
    return range->start.value();
  }
  return Const(DTypeOf(range->extent), 0);
}

inline Expr RangeExtent(const Range& range) { return range->extent; }

inline Expr CastDType(DLDataType dtype, Expr value) {
  if (DTypeOf(value) == dtype) {
    return value;
  }
  if (const auto* op = value.as<IntImmObj>()) {
    return Const(dtype, op->value);
  }
  if (const auto* op = value.as<BoolImmObj>()) {
    return Const(dtype, static_cast<int64_t>(op->value ? 1 : 0));
  }
  if (const auto* op = value.as<FloatImmObj>()) {
    return Const(dtype, op->value);
  }
  return Cast(PrimTy(dtype), std::move(value));
}

inline Expr cast(DLDataType dtype, Expr value) { return CastDType(dtype, std::move(value)); }

inline int64_t truncdiv(int64_t a, int64_t b) {
  TVM_FFI_CHECK(b != 0, ValueError) << "Division by zero";
  return a / b;
}

inline int64_t truncmod(int64_t a, int64_t b) {
  TVM_FFI_CHECK(b != 0, ValueError) << "Modulo by zero";
  return a % b;
}

inline int64_t floordiv(int64_t a, int64_t b) {
  TVM_FFI_CHECK(b != 0, ValueError) << "Division by zero";
  int64_t q = a / b;
  int64_t r = a % b;
  if (r != 0 && ((r > 0) != (b > 0))) {
    --q;
  }
  return q;
}

inline int64_t floormod(int64_t a, int64_t b) {
  TVM_FFI_CHECK(b != 0, ValueError) << "Modulo by zero";
  int64_t r = a % b;
  if (r != 0 && ((r > 0) != (b > 0))) {
    r += b;
  }
  return r;
}

static constexpr int64_t kPosInf = std::numeric_limits<int64_t>::max();
static constexpr int64_t kNegInf = -kPosInf;

struct SymbolicLimits {
  inline static Expr pos_inf_ =
      Var(PrimTy(DLDataType{static_cast<uint8_t>(kDLInt), 64, 1}), "pos_inf");
  inline static Expr neg_inf_ =
      Var(PrimTy(DLDataType{static_cast<uint8_t>(kDLInt), 64, 1}), "neg_inf");
};

inline Expr pos_inf() { return SymbolicLimits::pos_inf_; }
inline Expr neg_inf() { return SymbolicLimits::neg_inf_; }
inline bool is_pos_inf(const Expr& value) { return value.get() == SymbolicLimits::pos_inf_.get(); }
inline bool is_neg_inf(const Expr& value) { return value.get() == SymbolicLimits::neg_inf_.get(); }

/*! \brief Structure for representing result of known
 * Values are assigned to allow these flags to be used in bitwise
 * operations.
 */
enum class CompareResult : int {
  kInconsistent = 0,
  kEQ = 1,
  kLT = 2,
  kLE = 3,
  kGT = 4,
  kGE = 5,
  kNE = 6,
  kUnknown = 7
};

inline constexpr CompareResult operator&(CompareResult lhs, CompareResult rhs) {
  return CompareResult(static_cast<int>(lhs) & static_cast<int>(rhs));
}
inline constexpr CompareResult operator|(CompareResult lhs, CompareResult rhs) {
  return CompareResult(static_cast<int>(lhs) | static_cast<int>(rhs));
}

inline CompareResult Reverse(CompareResult res) {
  switch (res) {
    case CompareResult::kInconsistent:
      return CompareResult::kInconsistent;
    case CompareResult::kEQ:
      return CompareResult::kEQ;
    case CompareResult::kLT:
      return CompareResult::kGT;
    case CompareResult::kLE:
      return CompareResult::kGE;
    case CompareResult::kGT:
      return CompareResult::kLT;
    case CompareResult::kGE:
      return CompareResult::kLE;
    case CompareResult::kNE:
      return CompareResult::kNE;
    case CompareResult::kUnknown:
      return CompareResult::kUnknown;
  }
  return CompareResult::kUnknown;
}

inline CompareResult Negate(CompareResult res) {
  switch (res) {
    case CompareResult::kInconsistent:
      return CompareResult::kInconsistent;
    case CompareResult::kUnknown:
      return CompareResult::kUnknown;
    default:
      return CompareResult(~static_cast<int>(res) & static_cast<int>(CompareResult::kUnknown));
  }
  return CompareResult::kUnknown;
}
struct ConstraintContext {
  explicit ConstraintContext(AnalyzerObj::Impl* analyzer, Expr constraint);
  ~ConstraintContext() noexcept;

  AnalyzerObj::Impl* analyzer_;
  Expr constraint_;
  std::vector<std::function<void()>> recovery_functions_;
};

std::vector<Expr> ExtractConstraints(const Expr& expr, bool keep_composite_constraints = true);

std::vector<Expr> ExtractComponents(const Expr& expr);

Expr SimplifyAsAndOfOrs(const Expr& expr, AnalyzerObj::Impl* analyzer);

inline const int64_t* AsConstInt(const Expr& x) {
  if (const IntImmObj* op = x.as<IntImmObj>()) {
    return &(op->value);
  }
  if (const BoolImmObj* op = x.as<BoolImmObj>()) {
    static int64_t false_value = 0;
    static int64_t true_value = 1;
    return op->value ? &true_value : &false_value;
  }
  return nullptr;
}

inline bool IsConstInt(const Expr& x, int64_t value) {
  if (const int64_t* v = AsConstInt(x)) {
    return *v == value;
  }
  return false;
}

inline bool IsIndexType(const DLDataType& type) {
  return type.code == kDLInt && type.lanes == 1 && (type.bits == 32 || type.bits == 64);
}

/*!
 * \brief Use Extended Euclidean algorithm to solve ax + by = gcd(a, b)
 * \param a The first coefficient.
 * \param b The second coefficient.
 * \param x The solution of x.
 * \param y The solution of y.
 * \return The GCD of a and b.
 */
inline int64_t ExtendedEuclidean(int64_t a, int64_t b, int64_t* x, int64_t* y) {
  // Extended Euclidean algorithm
  // if a < 0, the problem can be convert into
  // |a|* (-x) + b * y = gcd(|a|, b)
  //
  // initial condition:
  // a * 0 + b * 1 = b
  // a * 1 + b * 0 = a
  int64_t s = 0, old_s = 1;
  int64_t r = b, old_r = a >= 0 ? a : -a;
  // Iteration (r2 < r1):
  // a * x1 + b * y1 = r1
  // a * x2 + b * y2 = r2
  // The above two eqs can derive the following eq (q = r1 / r2)
  // a * (x1 - x2 * q) + b * (y1 - y2 * q) = r1 - r2 * q = r3
  // Because r3 < r2, the iteration can eventually terminate
  while (r != 0) {
    int64_t q = old_r / r;
    int64_t tmp = old_r;
    old_r = r;
    r = tmp - q * r;
    tmp = old_s;
    old_s = s;
    s = tmp - q * s;
  }

  *x = a >= 0 ? old_s : -old_s;
  if (b != 0) {
    *y = (old_r - (*x) * a) / b;
  } else {
    *y = 1;
  }

  return old_r;
}

/*!
 * \brief Take GCD of a and b.
 * \param a The first operand.
 * \param b The second operand.
 * \return The result.
 */
inline int64_t ZeroAwareGCD(int64_t a, int64_t b) {
  if (a < 0) a = -a;
  if (b < 0) b = -b;
  if (a < b) std::swap(a, b);
  if (b == 0) return a;
  // perform GCD (greatest common divisor)
  // ax + by = gcd(a, b) z if a != 0, b != 0
  while (a % b != 0) {
    a = a % b;
    std::swap(a, b);
  }
  return b;
}

/*!
 * \brief Calculate the least common multiple for two values.
 * \param a an integer number
 * \param b an integer number
 * \return the least common multiple.
 */
inline int64_t LeastCommonMultiple(int64_t a, int64_t b) {
  int64_t x, y;
  return (a * b) / ExtendedEuclidean(a, b, &x, &y);
}

template <typename TNode, typename FLeaf>
inline void UnpackReduction(const Expr& value, FLeaf fleaf) {
  if (const TNode* node = value.as<TNode>()) {
    UnpackReduction<TNode, FLeaf>(node->a, fleaf);
    UnpackReduction<TNode, FLeaf>(node->b, fleaf);
  } else {
    fleaf(value);
  }
}

template <typename FLeaf>
inline void UnpackSum(const Expr& value, FLeaf fleaf, int sign = 1) {
  if (const auto* add = value.as<AddObj>()) {
    UnpackSum(add->a, fleaf, sign);
    UnpackSum(add->b, fleaf, sign);
  } else if (const auto* sub = value.as<SubObj>()) {
    UnpackSum(sub->a, fleaf, sign);
    UnpackSum(sub->b, fleaf, -sign);
  } else {
    fleaf(value, sign);
  }
}

inline Expr MulAndNormalize(const Expr& lhs, const Expr& rhs) {
  int64_t cscale = 1;
  Expr res = Const(DTypeOf(lhs), 1);
  auto fcollect = [&](const Expr& val) {
    if (const auto* intimm = val.as<IntImmObj>()) {
      cscale *= intimm->value;
    } else {
      res = res * val;
    }
  };
  UnpackReduction<MulObj>(lhs, fcollect);
  UnpackReduction<MulObj>(rhs, fcollect);
  if (cscale != 1) {
    res = res * cscale;
  }
  return res;
}

inline int32_t CheckPowOfTwo(uint64_t x) {
  if (x == 0 || (x & (x - 1)) != 0) {
    return -1;
  }
  int32_t shift = 0;
  while (x > 1) {
    x >>= 1;
    ++shift;
  }
  return shift;
}

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_UTILS_H_
