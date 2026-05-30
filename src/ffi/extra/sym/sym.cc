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

#include <tvm/ffi/extra/structural_equal.h>
#include <tvm/ffi/function.h>
#include <tvm/ffi/reflection/registry.h>

#include <algorithm>
#include <exception>
#include <memory>
#include <unordered_set>

#include "./analyzer_impl.h"
#include "./utils.h"

namespace tvm {
namespace ffi {
namespace std_ {

namespace refl = ::tvm::ffi::reflection;

namespace {

constexpr DLDataType kScalarBoolType{static_cast<uint8_t>(kDLBool), 8, 1};

template <typename ObjType>
Expr RefExpr(const ObjType* op) {
  return RefFromPtr<Expr>(op);
}

template <typename ObjType>
void VisitBinary(const ObjType* op, ExprVisitor* visitor) {
  visitor->VisitExpr(op->a);
  visitor->VisitExpr(op->b);
}

template <typename ObjType>
Expr MutateBinary(const ObjType* op, ExprMutator* mutator) {
  Expr a = mutator->VisitExpr(op->a);
  Expr b = mutator->VisitExpr(op->b);
  if (a.same_as(op->a) && b.same_as(op->b)) {
    return RefExpr(op);
  }
  return BinaryOpMaker<ObjType>::Make(std::move(a), std::move(b));
}

}  // namespace

void ExprVisitor::VisitExpr_(const VarObj*) {}
void ExprVisitor::VisitExpr_(const BoolImmObj*) {}
void ExprVisitor::VisitExpr_(const IntImmObj*) {}
void ExprVisitor::VisitExpr_(const FloatImmObj*) {}
void ExprVisitor::VisitExpr_(const CastObj* op) { VisitExpr(op->value); }

#define TVM_FFI_SYM_VISIT_BINARY(ObjType) \
  void ExprVisitor::VisitExpr_(const ObjType* op) { VisitBinary(op, this); }

TVM_FFI_SYM_VISIT_BINARY(AddObj)
TVM_FFI_SYM_VISIT_BINARY(SubObj)
TVM_FFI_SYM_VISIT_BINARY(MulObj)
TVM_FFI_SYM_VISIT_BINARY(CDivObj)
TVM_FFI_SYM_VISIT_BINARY(CModObj)
TVM_FFI_SYM_VISIT_BINARY(FloorDivObj)
TVM_FFI_SYM_VISIT_BINARY(FloorModObj)
TVM_FFI_SYM_VISIT_BINARY(MinObj)
TVM_FFI_SYM_VISIT_BINARY(MaxObj)
TVM_FFI_SYM_VISIT_BINARY(EqObj)
TVM_FFI_SYM_VISIT_BINARY(NeObj)
TVM_FFI_SYM_VISIT_BINARY(LtObj)
TVM_FFI_SYM_VISIT_BINARY(LeObj)
TVM_FFI_SYM_VISIT_BINARY(GtObj)
TVM_FFI_SYM_VISIT_BINARY(GeObj)
TVM_FFI_SYM_VISIT_BINARY(AndObj)
TVM_FFI_SYM_VISIT_BINARY(OrObj)
TVM_FFI_SYM_VISIT_BINARY(LShiftObj)
TVM_FFI_SYM_VISIT_BINARY(RShiftObj)
TVM_FFI_SYM_VISIT_BINARY(BitwiseAndObj)
TVM_FFI_SYM_VISIT_BINARY(BitwiseOrObj)
TVM_FFI_SYM_VISIT_BINARY(BitwiseXorObj)

#undef TVM_FFI_SYM_VISIT_BINARY

void ExprVisitor::VisitExpr_(const NotObj* op) { VisitExpr(op->operand); }
void ExprVisitor::VisitExpr_(const BitwiseNotObj* op) { VisitExpr(op->operand); }
void ExprVisitor::VisitExpr_(const AbsObj* op) { VisitExpr(op->operand); }
void ExprVisitor::VisitExpr_(const IfExprObj* op) {
  VisitExpr(op->cond);
  VisitExpr(op->then_expr);
  VisitExpr(op->else_expr);
}
void ExprVisitor::VisitExpr_(const CallObj* op) {
  for (const Expr& arg : op->args) {
    VisitExpr(arg);
  }
}

Expr ExprMutator::VisitExpr_(const VarObj* op) { return RefExpr(op); }
Expr ExprMutator::VisitExpr_(const BoolImmObj* op) { return RefExpr(op); }
Expr ExprMutator::VisitExpr_(const IntImmObj* op) { return RefExpr(op); }
Expr ExprMutator::VisitExpr_(const FloatImmObj* op) { return RefExpr(op); }
Expr ExprMutator::VisitExpr_(const CastObj* op) {
  Expr value = VisitExpr(op->value);
  if (value.same_as(op->value)) {
    return RefExpr(op);
  }
  return Cast(op->ty, std::move(value));
}

#define TVM_FFI_SYM_MUTATE_BINARY(ObjType) \
  Expr ExprMutator::VisitExpr_(const ObjType* op) { return MutateBinary(op, this); }

TVM_FFI_SYM_MUTATE_BINARY(AddObj)
TVM_FFI_SYM_MUTATE_BINARY(SubObj)
TVM_FFI_SYM_MUTATE_BINARY(MulObj)
TVM_FFI_SYM_MUTATE_BINARY(CDivObj)
TVM_FFI_SYM_MUTATE_BINARY(CModObj)
TVM_FFI_SYM_MUTATE_BINARY(FloorDivObj)
TVM_FFI_SYM_MUTATE_BINARY(FloorModObj)
TVM_FFI_SYM_MUTATE_BINARY(MinObj)
TVM_FFI_SYM_MUTATE_BINARY(MaxObj)
TVM_FFI_SYM_MUTATE_BINARY(EqObj)
TVM_FFI_SYM_MUTATE_BINARY(NeObj)
TVM_FFI_SYM_MUTATE_BINARY(LtObj)
TVM_FFI_SYM_MUTATE_BINARY(LeObj)
TVM_FFI_SYM_MUTATE_BINARY(GtObj)
TVM_FFI_SYM_MUTATE_BINARY(GeObj)
TVM_FFI_SYM_MUTATE_BINARY(AndObj)
TVM_FFI_SYM_MUTATE_BINARY(OrObj)
TVM_FFI_SYM_MUTATE_BINARY(LShiftObj)
TVM_FFI_SYM_MUTATE_BINARY(RShiftObj)
TVM_FFI_SYM_MUTATE_BINARY(BitwiseAndObj)
TVM_FFI_SYM_MUTATE_BINARY(BitwiseOrObj)
TVM_FFI_SYM_MUTATE_BINARY(BitwiseXorObj)

#undef TVM_FFI_SYM_MUTATE_BINARY

Expr ExprMutator::VisitExpr_(const NotObj* op) {
  Expr operand = VisitExpr(op->operand);
  if (operand.same_as(op->operand)) return RefExpr(op);
  return logical_not(std::move(operand));
}

Expr ExprMutator::VisitExpr_(const BitwiseNotObj* op) {
  Expr operand = VisitExpr(op->operand);
  if (operand.same_as(op->operand)) return RefExpr(op);
  return bitwise_not(std::move(operand));
}

Expr ExprMutator::VisitExpr_(const AbsObj* op) {
  Expr operand = VisitExpr(op->operand);
  if (operand.same_as(op->operand)) return RefExpr(op);
  return abs(std::move(operand));
}

Expr ExprMutator::VisitExpr_(const IfExprObj* op) {
  Expr cond = VisitExpr(op->cond);
  Expr then_expr = VisitExpr(op->then_expr);
  Expr else_expr = VisitExpr(op->else_expr);
  if (cond.same_as(op->cond) && then_expr.same_as(op->then_expr) &&
      else_expr.same_as(op->else_expr)) {
    return RefExpr(op);
  }
  return select(std::move(cond), std::move(then_expr), std::move(else_expr));
}

Expr ExprMutator::VisitExpr_(const CallObj* op) {
  bool changed = false;
  List<Expr> args;
  for (const Expr& arg : op->args) {
    Expr new_arg = VisitExpr(arg);
    changed = changed || !new_arg.same_as(arg);
    args.push_back(new_arg);
  }
  if (!changed) return RefExpr(op);
  return Call(op->ty, op->callee, std::move(args), op->attr);
}

bool DeepEqualTy(const ExprObj* lhs, const ExprObj* rhs) {
  return StructuralEqual::Equal(Any(lhs->ty), Any(rhs->ty), false, true);
}

bool ExprDeepEqual::VisitExpr_(const VarObj* lhs, void* rhs) {
  return RefFromPtr<Var>(lhs).same_as(RefFromPtr<Var>(static_cast<const VarObj*>(rhs)));
}

bool ExprDeepEqual::VisitExpr_(const BoolImmObj* lhs, void* rhs) {
  auto* other = static_cast<const BoolImmObj*>(rhs);
  return lhs->value == other->value && DeepEqualTy(lhs, other);
}

bool ExprDeepEqual::VisitExpr_(const IntImmObj* lhs, void* rhs) {
  auto* other = static_cast<const IntImmObj*>(rhs);
  return lhs->value == other->value && DeepEqualTy(lhs, other);
}

bool ExprDeepEqual::VisitExpr_(const FloatImmObj* lhs, void* rhs) {
  auto* other = static_cast<const FloatImmObj*>(rhs);
  return lhs->value == other->value && DeepEqualTy(lhs, other);
}

bool ExprDeepEqual::VisitExpr_(const CastObj* lhs, void* rhs) {
  auto* other = static_cast<const CastObj*>(rhs);
  return DeepEqualTy(lhs, other) && ExprDeepEqual()(lhs->value, other->value);
}

template <typename ObjType>
bool DeepEqualBinaryObj(const ObjType* lhs, void* rhs) {
  auto* other = static_cast<const ObjType*>(rhs);
  ExprDeepEqual equal;
  return DeepEqualTy(lhs, other) && equal(lhs->a, other->a) && equal(lhs->b, other->b);
}

#define TVM_FFI_SYM_DEEP_EQUAL_BINARY(ObjType)                    \
  bool ExprDeepEqual::VisitExpr_(const ObjType* lhs, void* rhs) { \
    return DeepEqualBinaryObj(lhs, rhs);                          \
  }

TVM_FFI_SYM_DEEP_EQUAL_BINARY(AddObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(SubObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(MulObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(CDivObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(CModObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(FloorDivObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(FloorModObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(MinObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(MaxObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(EqObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(NeObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(LtObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(LeObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(GtObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(GeObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(AndObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(OrObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(LShiftObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(RShiftObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(BitwiseAndObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(BitwiseOrObj)
TVM_FFI_SYM_DEEP_EQUAL_BINARY(BitwiseXorObj)

#undef TVM_FFI_SYM_DEEP_EQUAL_BINARY

template <typename ObjType>
bool DeepEqualUnaryObj(const ObjType* lhs, void* rhs) {
  auto* other = static_cast<const ObjType*>(rhs);
  return DeepEqualTy(lhs, other) && ExprDeepEqual()(lhs->operand, other->operand);
}

bool ExprDeepEqual::VisitExpr_(const NotObj* lhs, void* rhs) { return DeepEqualUnaryObj(lhs, rhs); }
bool ExprDeepEqual::VisitExpr_(const BitwiseNotObj* lhs, void* rhs) {
  return DeepEqualUnaryObj(lhs, rhs);
}
bool ExprDeepEqual::VisitExpr_(const AbsObj* lhs, void* rhs) { return DeepEqualUnaryObj(lhs, rhs); }

bool ExprDeepEqual::VisitExpr_(const IfExprObj* lhs, void* rhs) {
  auto* other = static_cast<const IfExprObj*>(rhs);
  ExprDeepEqual equal;
  return DeepEqualTy(lhs, other) && equal(lhs->cond, other->cond) &&
         equal(lhs->then_expr, other->then_expr) && equal(lhs->else_expr, other->else_expr);
}

bool ExprDeepEqual::VisitExpr_(const CallObj* lhs, void* rhs) {
  auto* other = static_cast<const CallObj*>(rhs);
  if (!DeepEqualTy(lhs, other) || lhs->args.size() != other->args.size()) return false;
  if (!StructuralEqual::Equal(lhs->callee, other->callee, false, true)) return false;
  if (!StructuralEqual::Equal(lhs->attr, other->attr, false, true)) return false;
  ExprDeepEqual equal;
  for (int64_t i = 0, n = static_cast<int64_t>(lhs->args.size()); i < n; ++i) {
    if (!equal(lhs->args[i], other->args[i])) return false;
  }
  return true;
}

template <typename F>
void CollectConstraints(const Expr& expr, F callback, bool keep_composite_constraints) {
  if (keep_composite_constraints) {
    callback(expr);
  }
  PVar<Expr> x, y;
  if ((x && y).Match(expr)) {
    CollectConstraints(x.Eval(), callback, keep_composite_constraints);
    CollectConstraints(y.Eval(), callback, keep_composite_constraints);
  } else if (!keep_composite_constraints) {
    callback(expr);
  }
}

template <typename F>
void CollectComponents(const Expr& expr, F callback) {
  PVar<Expr> x, y;
  if ((x || y).Match(expr)) {
    CollectComponents(x.Eval(), callback);
    CollectComponents(y.Eval(), callback);
  } else {
    callback(expr);
  }
}

std::vector<Expr> ExtractConstraints(const Expr& expr, bool keep_composite_constraints) {
  std::vector<Expr> out;
  CollectConstraints(
      expr, [&](const Expr& part) { out.push_back(part); }, keep_composite_constraints);
  return out;
}

std::vector<Expr> ExtractComponents(const Expr& expr) {
  std::vector<Expr> out;
  CollectComponents(expr, [&](const Expr& part) { out.push_back(part); });
  return out;
}

ConstraintContext::ConstraintContext(AnalyzerObj::Impl* analyzer, Expr constraint)
    : analyzer_(analyzer), constraint_(std::move(constraint)) {
  recovery_functions_.push_back(analyzer_->const_int_bound.EnterConstraint(constraint_));
  recovery_functions_.push_back(analyzer_->modular_set.EnterConstraint(constraint_));
  recovery_functions_.push_back(analyzer_->rewrite_simplify.EnterConstraint(constraint_));
  recovery_functions_.push_back(analyzer_->interval_set.EnterConstraint(constraint_));
  recovery_functions_.push_back(analyzer_->transitive_comparisons.EnterConstraint(constraint_));
}

ConstraintContext::~ConstraintContext() noexcept {
  while (!recovery_functions_.empty()) {
    if (auto& func = recovery_functions_.back(); func) {
      try {
        func();
      } catch (...) {
        std::terminate();
      }
    }
    recovery_functions_.pop_back();
  }
}

namespace {

class AndOfOrs {
 public:
  explicit AndOfOrs(const Expr& expr);
  Expr AsExpr() const;
  void Simplify(AnalyzerObj::Impl* analyzer);
  void SimplifyWithinChunks(AnalyzerObj::Impl* analyzer);
  void SimplifyAcrossChunks(AnalyzerObj::Impl* analyzer);
  void RemoveTrueFalse();

  static void VisitAndExpressions(const Expr& expr, std::function<void(const Expr&)> callback);
  static void VisitOrExpressions(const Expr& expr, std::function<void(const Expr&)> callback);

  using Key = size_t;
  Key GetKey(const Expr& expr);
  Expr GetExpr(Key key) const;
  void TrySimplifyOr(Key* a, Key* b, AnalyzerObj::Impl* analyzer);
  void TrySimplifyAnd(Key* a, Key* b, AnalyzerObj::Impl* analyzer);

  std::vector<std::vector<Key>> chunks_;
  std::unordered_map<Key, Expr> key_to_expr_;
  std::unordered_map<Expr, Key, ExprStructuralHash, ExprStructuralEqual> expr_to_key_;
  Key key_true_;
  Key key_false_;
};

AndOfOrs::AndOfOrs(const Expr& expr)
    : key_true_(GetKey(Const(kScalarBoolType, true))),
      key_false_(GetKey(Const(kScalarBoolType, false))) {
  VisitAndExpressions(expr, [&](const Expr& outer_expr) {
    std::vector<Key> or_components;
    VisitOrExpressions(outer_expr, [&](const Expr& inner_expr) {
      Key key = GetKey(inner_expr);
      bool is_duplicate = std::any_of(or_components.begin(), or_components.end(),
                                      [&](Key prev) { return prev == key; });
      if (!is_duplicate) {
        or_components.push_back(key);
      }
    });
    bool is_permutation =
        std::any_of(chunks_.begin(), chunks_.end(), [&](const std::vector<Key>& prev_components) {
          return or_components.size() == prev_components.size() &&
                 std::is_permutation(prev_components.begin(), prev_components.end(),
                                     or_components.begin());
        });
    if (!is_permutation) {
      chunks_.push_back(std::move(or_components));
    }
  });
}

void AndOfOrs::VisitAndExpressions(const Expr& expr, std::function<void(const Expr&)> callback) {
  PVar<Expr> x, y;
  if ((x && y).Match(expr)) {
    VisitAndExpressions(x.Eval(), callback);
    VisitAndExpressions(y.Eval(), callback);
  } else if ((x || y).Match(expr)) {
    VisitAndExpressions(x.Eval(), [&](const Expr& x_part) {
      VisitAndExpressions(y.Eval(), [&](const Expr& y_part) { callback(x_part || y_part); });
    });
  } else {
    callback(expr);
  }
}

void AndOfOrs::VisitOrExpressions(const Expr& expr, std::function<void(const Expr&)> callback) {
  PVar<Expr> x, y;
  if ((x || y).Match(expr)) {
    VisitOrExpressions(x.Eval(), callback);
    VisitOrExpressions(y.Eval(), callback);
  } else if ((x && y).Match(expr)) {
    VisitOrExpressions(x.Eval(), [&](const Expr& x_part) {
      VisitOrExpressions(y.Eval(), [&](const Expr& y_part) { callback(x_part && y_part); });
    });
  } else {
    callback(expr);
  }
}

AndOfOrs::Key AndOfOrs::GetKey(const Expr& expr) {
  auto it = expr_to_key_.find(expr);
  if (it != expr_to_key_.end()) {
    return it->second;
  }
  Key key{expr_to_key_.size()};
  expr_to_key_[expr] = key;
  key_to_expr_.emplace(key, expr);
  return key;
}

Expr AndOfOrs::GetExpr(AndOfOrs::Key key) const {
  auto it = key_to_expr_.find(key);
  TVM_FFI_CHECK(it != key_to_expr_.end(), InternalError);
  return it->second;
}

Expr AndOfOrs::AsExpr() const {
  Expr expr = Const(kScalarBoolType, true);
  for (const auto& chunk : chunks_) {
    Expr chunk_expr = Const(kScalarBoolType, false);
    for (Key j : chunk) {
      chunk_expr = chunk_expr || GetExpr(j);
    }
    expr = expr && chunk_expr;
  }
  return expr;
}

void AndOfOrs::TrySimplifyOr(Key* a_ptr, Key* b_ptr, AnalyzerObj::Impl* analyzer) {
  Key& a = *a_ptr;
  Key& b = *b_ptr;
  Expr joint = GetExpr(a) || GetExpr(b);
  Expr simplified = analyzer->rewrite_simplify(joint);
  if (!ExprDeepEqual()(simplified, joint)) {
    if (auto* simplified_or = simplified.as<OrObj>()) {
      a = GetKey(simplified_or->a);
      b = GetKey(simplified_or->b);
    } else {
      a = key_false_;
      b = GetKey(simplified);
    }
  }
}

void AndOfOrs::TrySimplifyAnd(Key* a_ptr, Key* b_ptr, AnalyzerObj::Impl* analyzer) {
  Key& a = *a_ptr;
  Key& b = *b_ptr;
  Expr joint = GetExpr(a) && GetExpr(b);
  Expr simplified = analyzer->rewrite_simplify(joint);
  if (!ExprDeepEqual()(simplified, joint)) {
    if (auto* simplified_and = simplified.as<AndObj>()) {
      a = GetKey(simplified_and->a);
      b = GetKey(simplified_and->b);
    } else {
      a = key_true_;
      b = GetKey(simplified);
    }
  }
}

void AndOfOrs::Simplify(AnalyzerObj::Impl* analyzer) {
  SimplifyWithinChunks(analyzer);
  RemoveTrueFalse();
  SimplifyAcrossChunks(analyzer);
  RemoveTrueFalse();
}

void AndOfOrs::SimplifyWithinChunks(AnalyzerObj::Impl* analyzer) {
  for (auto& chunk : chunks_) {
    for (size_t expr_i = 0; expr_i < chunk.size(); expr_i++) {
      for (size_t expr_j = expr_i + 1; expr_j < chunk.size(); expr_j++) {
        TrySimplifyOr(&chunk[expr_i], &chunk[expr_j], analyzer);
      }
    }
  }
}

void AndOfOrs::SimplifyAcrossChunks(AnalyzerObj::Impl* analyzer) {
  for (size_t i_and = 0; i_and < chunks_.size(); i_and++) {
    for (size_t j_and = i_and + 1; j_and < chunks_.size(); j_and++) {
      auto& i_chunk = chunks_[i_and];
      auto& j_chunk = chunks_[j_and];
      if (i_chunk.size() == 1 && j_chunk.size() == 1) {
        TrySimplifyAnd(&i_chunk[0], &j_chunk[0], analyzer);
        continue;
      }
      constexpr size_t kNonExist = std::numeric_limits<size_t>::max();
      std::unordered_set<Key> j_set(j_chunk.begin(), j_chunk.end());
      size_t i_distinct_index = kNonExist;
      for (size_t i = 0; i < i_chunk.size(); i++) {
        if (!j_set.count(i_chunk[i])) {
          i_distinct_index = i;
          break;
        }
      }
      if (i_distinct_index == kNonExist) {
        j_chunk = {key_true_};
        continue;
      }
      std::unordered_set<Key> i_set(i_chunk.begin(), i_chunk.end());
      size_t j_distinct_index = kNonExist;
      for (size_t j = 0; j < j_chunk.size(); j++) {
        if (!i_set.count(j_chunk[j])) {
          j_distinct_index = j;
          break;
        }
      }
      if (j_distinct_index == kNonExist) {
        i_chunk = {key_true_};
        continue;
      }
      if (i_chunk.size() == j_chunk.size()) {
        size_t num_shared_exprs = 0;
        for (const auto& j_key : j_chunk) {
          if (i_set.count(j_key)) ++num_shared_exprs;
        }
        if (num_shared_exprs + 1 == i_chunk.size()) {
          auto& key_i = i_chunk[i_distinct_index];
          auto& key_j = j_chunk[j_distinct_index];
          Expr known = [&]() {
            Expr known = Const(kScalarBoolType, true);
            for (const auto& key : i_chunk) {
              if (&key != &key_i) {
                known = known && analyzer->Simplify(!GetExpr(key));
              }
            }
            return known;
          }();
          {
            ConstraintContext context(analyzer, known);
            TrySimplifyAnd(&key_i, &key_j, analyzer);
          }
        }
      }
    }
  }
}

void AndOfOrs::RemoveTrueFalse() {
  for (auto& chunk : chunks_) {
    if (std::any_of(chunk.begin(), chunk.end(), [&](Key key) { return key == key_true_; })) {
      chunk = {key_true_};
    } else {
      chunk.erase(
          std::remove_if(chunk.begin(), chunk.end(), [&](Key key) { return key == key_false_; }),
          chunk.end());
    }
  }
  if (std::any_of(chunks_.begin(), chunks_.end(),
                  [&](const std::vector<Key>& chunk) { return chunk.empty(); })) {
    chunks_ = {{}};
  } else {
    chunks_.erase(std::remove_if(chunks_.begin(), chunks_.end(),
                                 [&](const std::vector<Key>& chunk) {
                                   return chunk.size() == 1 && chunk[0] == key_true_;
                                 }),
                  chunks_.end());
  }
}

class DisableAndOfOrRecursion {
 public:
  explicit DisableAndOfOrRecursion(AnalyzerObj::Impl* analyzer)
      : analyzer_(analyzer), cached_flags_(analyzer->rewrite_simplify.GetEnabledExtensions()) {
    auto new_flags = static_cast<RewriteSimplifier::Extension>(
        cached_flags_ & (~RewriteSimplifier::kConvertBooleanToAndOfOrs));
    analyzer->rewrite_simplify.SetEnabledExtensions(new_flags);
  }
  ~DisableAndOfOrRecursion() { analyzer_->rewrite_simplify.SetEnabledExtensions(cached_flags_); }

  DisableAndOfOrRecursion(const DisableAndOfOrRecursion&) = delete;
  DisableAndOfOrRecursion& operator=(const DisableAndOfOrRecursion&) = delete;

  AnalyzerObj::Impl* analyzer_;
  RewriteSimplifier::Extension cached_flags_;
};

}  // namespace

Expr SimplifyAsAndOfOrs(const Expr& expr, AnalyzerObj::Impl* analyzer) {
  DisableAndOfOrRecursion context(analyzer);
  AndOfOrs repr(analyzer->Simplify(expr));
  repr.Simplify(analyzer);
  return repr.AsExpr();
}

Expr IRMutatorWithAnalyzer::VisitExpr_(const IfExprObj* op) {
  Expr cond = this->VisitExpr(op->cond);
  Expr then_expr = [this, cond, e = op->then_expr]() {
    ConstraintContext constraint(this->analyzer_, cond);
    return this->VisitExpr(e);
  }();
  Expr else_expr = [this, cond, e = op->else_expr]() {
    ConstraintContext constraint(this->analyzer_,
                                 this->analyzer_->rewrite_simplify(logical_not(cond)));
    return this->VisitExpr(e);
  }();
  if (IsConstInt(cond, 0)) {
    return else_expr;
  }
  if (IsConstInt(cond, 1)) {
    return then_expr;
  }
  if (cond.same_as(op->cond) && then_expr.same_as(op->then_expr) &&
      else_expr.same_as(op->else_expr)) {
    return RefExpr(op);
  }
  return select(std::move(cond), std::move(then_expr), std::move(else_expr));
}

struct AnalyzerObj::Testing {
  static int32_t Register() {
    refl::GlobalDef()
        .def("ffi.std._AnalyzerCanProve",
             [](AnalyzerObj* analyzer, const Expr& cond, int64_t strength) {
               return analyzer->CanProve(cond, static_cast<AnalyzerObj::ProofStrength>(strength));
             })
        .def("ffi.std._AnalyzerCanProveEqual",
             [](AnalyzerObj* analyzer, const Expr& lhs, const Expr& rhs) {
               return analyzer->CanProveEqual(lhs, rhs);
             })
        .def("ffi.std._AnalyzerSimplify",
             [](AnalyzerObj* analyzer, const Expr& expr, int64_t steps) {
               return analyzer->Simplify(expr, static_cast<int>(steps));
             })
        .def("ffi.std._AnalyzerConstIntBound",
             [](AnalyzerObj* analyzer, const Expr& expr) {
               return analyzer->impl_->const_int_bound(expr);
             })
        .def("ffi.std._AnalyzerModularSet",
             [](AnalyzerObj* analyzer, const Expr& expr) {
               return analyzer->impl_->modular_set(expr);
             })
        .def("ffi.std._AnalyzerRewriteSimplify",
             [](AnalyzerObj* analyzer, const Expr& expr) {
               return analyzer->impl_->rewrite_simplify(expr);
             })
        .def("ffi.std._AnalyzerCanonicalSimplify",
             [](AnalyzerObj* analyzer, const Expr& expr) {
               return analyzer->impl_->canonical_simplify(expr);
             })
        .def("ffi.std._AnalyzerIntervalSet",
             [](AnalyzerObj* analyzer, const Expr& expr, const Dict<Var, IntervalSet>& dom_map) {
               return analyzer->impl_->interval_set(expr, dom_map);
             })
        .def("ffi.std._AnalyzerConstIntBoundUpdate",
             [](AnalyzerObj* analyzer, const Var& var, const ConstIntBound& info,
                bool allow_override) {
               analyzer->impl_->const_int_bound.Update(var, info, allow_override);
             })
        .def(
            "ffi.std._AnalyzerGetEnabledExtensions",
            [](AnalyzerObj* analyzer) {
              return static_cast<int64_t>(analyzer->impl_->rewrite_simplify.GetEnabledExtensions());
            })
        .def("ffi.std._AnalyzerSetEnabledExtensions",
             [](AnalyzerObj* analyzer, int64_t flags) {
               analyzer->impl_->rewrite_simplify.SetEnabledExtensions(
                   static_cast<RewriteSimplifier::Extension>(flags));
             })
        .def("ffi.std._AnalyzerEnterConstraint", [](AnalyzerObj* analyzer, Expr constraint) {
          auto ctx_holder = std::make_shared<std::shared_ptr<ConstraintContext>>(
              std::make_shared<ConstraintContext>(analyzer->impl_.get(), std::move(constraint)));
          return Function::FromTyped([ctx_holder]() { ctx_holder->reset(); });
        });
    return 0;
  }
};

[[maybe_unused]] int32_t reg = AnalyzerObj::Testing::Register();

AnalyzerObj::AnalyzerObj() : impl_(std::make_unique<Impl>()) {}
AnalyzerObj::~AnalyzerObj() = default;
void AnalyzerObj::MarkGlobalNonNegValue(const Expr& value) { impl_->MarkGlobalNonNegValue(value); }
void AnalyzerObj::Bind(const Var& var, const Expr& expr, bool allow_override) {
  impl_->Bind(var, expr, allow_override);
}
void AnalyzerObj::Bind(const Var& var, const Range& range, bool allow_override) {
  impl_->Bind(var, range, allow_override);
}
void AnalyzerObj::Bind(const Dict<Var, Range>& variables, bool allow_override) {
  impl_->Bind(variables, allow_override);
}
bool AnalyzerObj::CanProveGreaterEqual(const Expr& expr, int64_t lower_bound) {
  return impl_->CanProveGreaterEqual(expr, lower_bound);
}
bool AnalyzerObj::CanProveLess(const Expr& expr, int64_t upper_bound) {
  return impl_->CanProveLess(expr, upper_bound);
}
bool AnalyzerObj::CanProveEqual(const Expr& lhs, const Expr& rhs) {
  return impl_->CanProveEqual(lhs, rhs);
}
bool AnalyzerObj::CanProveLessEqualThanSymbolicShapeValue(const Expr& lhs, const Expr& shape) {
  return impl_->CanProveLessEqualThanSymbolicShapeValue(lhs, shape);
}
bool AnalyzerObj::CanProve(const Expr& cond, ProofStrength strength) {
  return impl_->CanProve(cond, strength);
}
Expr AnalyzerObj::Simplify(const Expr& expr, int steps) { return impl_->Simplify(expr, steps); }

namespace {

int RegisterReflection() {
  refl::ObjectDef<ConstIntBoundObj>()
      .def(refl::init<int64_t, int64_t>())
      .def_ro("min_value", &ConstIntBoundObj::min_value)
      .def_ro("max_value", &ConstIntBoundObj::max_value)
      .def("__str__", &ConstIntBoundObj::Str);
  refl::ObjectDef<ModularSetObj>()
      .def(refl::init<int64_t, int64_t>())
      .def_ro("coeff", &ModularSetObj::coeff)
      .def_ro("base", &ModularSetObj::base)
      .def("__str__", &ModularSetObj::Str);
  refl::ObjectDef<IntervalSetObj>()
      .def(refl::init<Expr, Expr>())
      .def_ro("min_value", &IntervalSetObj::min_value)
      .def_ro("max_value", &IntervalSetObj::max_value)
      .def("__str__", &IntervalSetObj::Str);
  refl::ObjectDef<SplitExprObj>(refl::init(false)).def("__str__", &SplitExprObj::Str);
  refl::ObjectDef<SumExprObj>(refl::init(false)).def("__str__", &SumExprObj::Str);
  refl::ObjectDef<AnalyzerObj>()
      .def(refl::init<>())
      .def("mark_global_non_neg_value", &AnalyzerObj::MarkGlobalNonNegValue)
      .def("bind_expr", [](AnalyzerObj* self, const Var& var, const Expr& expr,
                           bool allow_override) { self->Bind(var, expr, allow_override); })
      .def("bind_range", [](AnalyzerObj* self, const Var& var, const Range& range,
                            bool allow_override) { self->Bind(var, range, allow_override); })
      .def("can_prove_greater_equal", &AnalyzerObj::CanProveGreaterEqual)
      .def("can_prove_less", &AnalyzerObj::CanProveLess)
      .def("can_prove_less_equal_than_symbolic_shape_value",
           &AnalyzerObj::CanProveLessEqualThanSymbolicShapeValue);
  return 0;
}

[[maybe_unused]] int register_reflection = RegisterReflection();

}  // namespace

}  // namespace std_
}  // namespace ffi
}  // namespace tvm
