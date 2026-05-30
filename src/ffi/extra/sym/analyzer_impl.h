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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_IMPL_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_IMPL_H_

#include <tvm/ffi/extra/std.h>

#include "./analyzer_canonical_simplify.h"
#include "./analyzer_const_int_bound.h"
#include "./analyzer_interval_set.h"
#include "./analyzer_modular_set.h"
#include "./analyzer_rewrite_simplify.h"
#include "./analyzer_transitive_comparisons.h"
#include "./expr_functor.h"
#include "./pattern_match.h"
#include "./utils.h"

namespace tvm {
namespace ffi {
namespace std_ {

struct AnalyzerObj::Impl {
  ConstIntBoundAnalyzer const_int_bound;
  ModularSetAnalyzer modular_set;
  RewriteSimplifier rewrite_simplify;
  CanonicalSimplifier canonical_simplify;
  IntervalSetAnalyzer interval_set;
  TransitiveComparisonAnalyzer transitive_comparisons;
  Impl()
      : const_int_bound(this),
        modular_set(this),
        rewrite_simplify(this),
        canonical_simplify(this),
        interval_set(this),
        transitive_comparisons(this) {}

  void MarkGlobalNonNegValue(const Expr& value) {
    // decompose value as symbol * scale + offset
    int64_t offset = 0;
    Expr symbol_scale = Const(DTypeOf(value), 0);
    auto fcollect_sum = [&](const Expr& val, int sign) {
      if (const auto* intimm = val.as<IntImmObj>()) {
        offset += intimm->value * sign;
      } else {
        if (sign > 0) {
          symbol_scale = symbol_scale + val;
        } else {
          symbol_scale = symbol_scale - val;
        }
      }
    };
    UnpackSum(value, fcollect_sum);

    // split out the symbol and non-symbolic part
    int64_t cscale = 1;
    Expr symbol = Const(DTypeOf(value), 1);
    auto fcollect_prod = [&](const Expr& val) {
      if (const auto* intimm = val.as<IntImmObj>()) {
        cscale *= intimm->value;
      } else {
        symbol = symbol * val;
      }
    };
    UnpackReduction<MulObj>(symbol_scale, fcollect_prod);
    if (cscale <= 0) return;
    // override the constant int bound by marking it as non-negative
    // NOTE: there might be future opportunities of more bound hint
    // this is a simple step and covers all the current needs
    //
    // We may consider enhance the sub analyzer to directly take
    // MarkPositiveVar so their bounds do not overlap
    if (const auto* var_ptr = symbol.as<VarObj>()) {
      Var var = RefFromPtr<Var>(var_ptr);
      // skip non-index type, keep it to be compatible
      // with any_dim that do not represent any value
      if (!IsIndexType(DTypeOf(var))) return;
      bool allow_override = true;
      // mark the constant bound is sufficient
      // we cannot mark interval set as that will cause relaxation of the var
      // during bound proof which is not our intention
      this->const_int_bound.Update(var, ConstIntBound(-offset, kPosInf), allow_override);
    }
  }
  void Bind(const Var& var, const Expr& expr, bool allow_override = false) {
    Expr new_expr = expr;
    new_expr = this->canonical_simplify(new_expr);
    new_expr = this->rewrite_simplify(new_expr);
    this->const_int_bound.Update(var, this->const_int_bound(new_expr), allow_override);
    this->modular_set.Update(var, this->modular_set(new_expr), allow_override);
    this->rewrite_simplify.Update(var, new_expr, allow_override);
    this->canonical_simplify.Update(var, new_expr, allow_override);
    this->interval_set.Update(var, this->interval_set(new_expr), allow_override);
    this->transitive_comparisons.Bind(var, expr, allow_override);
  }
  void Bind(const Var& var, const Range& range, bool allow_override = false) {
    if (IsConstInt(RangeExtent(range), 1)) {
      this->Bind(var, RangeMin(range), allow_override);
    } else {
      this->const_int_bound.Bind(var, range, allow_override);
      this->interval_set.Bind(var, range, allow_override);
      this->transitive_comparisons.Bind(var, range, allow_override);
    }
  }
  void Bind(const Dict<Var, Range>& variables, bool allow_override = false) {
    for (const auto& iter : variables) {
      this->Bind(iter.first, iter.second, allow_override);
    }
  }
  bool CanProveGreaterEqual(const Expr& expr, int64_t lower_bound) {
    if (const auto* ptr = expr.as<IntImmObj>()) {
      return ptr->value >= lower_bound;
    }
    auto bd = this->const_int_bound(this->rewrite_simplify(expr));
    if (bd->min_value >= lower_bound) return true;
    return false;
  }
  bool CanProveLess(const Expr& expr, int64_t upper_bound) {
    if (const auto* ptr = expr.as<IntImmObj>()) {
      return ptr->value < upper_bound;
    }
    auto bd = this->const_int_bound(this->rewrite_simplify(expr));
    if (bd->max_value < upper_bound) return true;
    return false;
  }
  bool CanProveEqual(const Expr& lhs, const Expr& rhs) {
    const auto* clhs = lhs.as<IntImmObj>();
    const auto* crhs = rhs.as<IntImmObj>();
    if (clhs && crhs) return clhs->value == crhs->value;
    if (DTypeOf(lhs).code == kDLOpaqueHandle || DTypeOf(rhs).code == kDLOpaqueHandle) {
      return lhs.same_as(rhs);
    }
    Expr sub = lhs - rhs;
    if (const int64_t* value = AsConstInt(Simplify(sub)); value != nullptr && *value == 0) {
      return true;
    }
    Expr zero = Const(DTypeOf(sub), 0);
    return CanProve(sub == zero);
  }
  bool CanProveLessEqualThanSymbolicShapeValue(const Expr& lhs, const Expr& shape) {
    if (this->CanProve(lhs <= shape, ProofStrength::kSymbolicBound)) return true;
    // no need to do further attempt if shape is already a constant.
    if (AsConstInt(shape) != nullptr) return false;
    // collect constant scale and ignore symbolic part
    // so 32 * n => cscale = 32
    int64_t cscale = 1;
    auto fcollect = [&](const Expr& expr) {
      if (auto* ptr = expr.as<IntImmObj>()) {
        cscale *= ptr->value;
      }
    };
    UnpackReduction<MulObj>(shape, fcollect);
    if (this->CanProve(lhs <= std::abs(cscale), ProofStrength::kSymbolicBound)) return true;
    return false;
  }
  bool CanProve(const Expr& expr, AnalyzerObj::ProofStrength strength = ProofStrength::kDefault) {
    // Avoid potentially expensive simplification unless required.
    if (const auto* ptr = expr.as<IntImmObj>()) {
      return ptr->value != 0;
    }
    Expr simplified = Simplify(expr);
    const int64_t* as_int = AsConstInt(simplified);
    if (as_int && *as_int) return true;
    if (strength >= ProofStrength::kSymbolicBound) {
      // NOTE: we intentionally only pattern match common bound predicate i < bound
      // and put this implementation at the top-level.
      // This is to avoid repeatitive calling of this function
      // that causes speed issues.
      // This strategy can only be called from top-level and not from sub-analyzers.
      Optional<Expr> pos_diff;
      int lower_bound = 0;
      if (const auto* ptr_lt = expr.as<LtObj>()) {
        pos_diff = ptr_lt->b - ptr_lt->a;
        lower_bound = 1;
      }
      if (const auto* ptr_le = expr.as<LeObj>()) {
        pos_diff = ptr_le->b - ptr_le->a;
        lower_bound = 0;
      }
      if (const auto* ptr_gt = expr.as<GtObj>()) {
        pos_diff = ptr_gt->a - ptr_gt->b;
        lower_bound = 1;
      }
      if (const auto* ptr_ge = expr.as<GeObj>()) {
        pos_diff = ptr_ge->a - ptr_ge->b;
        lower_bound = 0;
      }
      if (pos_diff) {
        (void)lower_bound;
        IntervalSet iset = this->interval_set(this->Simplify(pos_diff.value()));
        if (iset->HasLowerBound()) {
          ConstIntBound relaxed_lower_bound =
              this->const_int_bound(this->Simplify(iset->min_value));
          if (relaxed_lower_bound->min_value >= lower_bound) return true;
        }
      }
    }
    return false;
  }
  Expr Simplify(const Expr& expr, int steps = 2) {
    Expr res = expr;
    // Always starts with a canonical simplification, as some structural property
    // of an expression might be destroyed by rewrite simplification.
    res = this->canonical_simplify(res);
    for (int i = 0; i < steps; ++i) {
      if (AsConstInt(res)) {
        return res;
      }
      if (i % 2 == 0) {
        res = this->rewrite_simplify(res);
      } else {
        res = this->canonical_simplify(res);
      }
    }
    return res;
  }
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_IMPL_H_
