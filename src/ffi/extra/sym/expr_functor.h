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

#ifndef TVM_FFI_EXTRA_SYM_EXPR_FUNCTOR_H_
#define TVM_FFI_EXTRA_SYM_EXPR_FUNCTOR_H_

#include <tvm/ffi/extra/std.h>
#include <tvm/ffi/extra/structural_hash.h>

namespace tvm {
namespace ffi {
namespace std_ {

template <typename RefType, typename ObjType>
inline RefType RefFromPtr(const ObjType* ptr) {
  return RefType(
      ::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<typename RefType::ContainerType>(
          const_cast<ObjType*>(ptr)));
}

template <typename FType>
struct ExprFunctor;

// NOLINTBEGIN(portability-template-virtual-member-function)
template <typename R, typename... Args>
struct ExprFunctor<R(const Expr& n, Args...)> {
  R operator()(const Expr& n, Args... args) {
    return this->VisitExpr(n, std::forward<Args>(args)...);
  }

  virtual R VisitExpr(const Expr& n, Args... args) {
    if (const auto* op = n.as<VarObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<BoolImmObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<IntImmObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<FloatImmObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<CastObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<AddObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<SubObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<MulObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<CDivObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<CModObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<FloorDivObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<FloorModObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<MinObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<MaxObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<EqObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<NeObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<LtObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<LeObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<GtObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<GeObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<AndObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<OrObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<NotObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<IfExprObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<LShiftObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<RShiftObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<BitwiseAndObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<BitwiseOrObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<BitwiseXorObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<BitwiseNotObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<AbsObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    if (const auto* op = n.as<CallObj>()) return VisitExpr_(op, std::forward<Args>(args)...);
    return VisitExprDefault_(n, std::forward<Args>(args)...);
  }

  virtual R VisitExprDefault_(const Expr& obj, Args...) {
    TVM_FFI_THROW(InternalError) << "Do not have a default for: " << obj->GetTypeKey();
    TVM_FFI_UNREACHABLE();
  }

  virtual ~ExprFunctor() = default;

#define TVM_FFI_SYM_EXPR_FUNCTOR(TY)                                              \
  virtual R VisitExpr_(const TY* obj, Args... args) {                             \
    return VisitExprDefault_(RefFromPtr<Expr>(obj), std::forward<Args>(args)...); \
  }

  TVM_FFI_SYM_EXPR_FUNCTOR(VarObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(BoolImmObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(IntImmObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(FloatImmObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(CastObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(AddObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(SubObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(MulObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(CDivObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(CModObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(FloorDivObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(FloorModObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(MinObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(MaxObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(EqObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(NeObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(LtObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(LeObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(GtObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(GeObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(AndObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(OrObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(NotObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(IfExprObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(LShiftObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(RShiftObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(BitwiseAndObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(BitwiseOrObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(BitwiseXorObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(BitwiseNotObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(AbsObj)
  TVM_FFI_SYM_EXPR_FUNCTOR(CallObj)

#undef TVM_FFI_SYM_EXPR_FUNCTOR
};
// NOLINTEND(portability-template-virtual-member-function)

struct ExprVisitor : protected ExprFunctor<void(const Expr&)> {
  using ExprFunctor::operator();
  using ExprFunctor::VisitExpr;

 protected:
  void VisitExpr_(const VarObj* op) override;
  void VisitExpr_(const BoolImmObj* op) override;
  void VisitExpr_(const IntImmObj* op) override;
  void VisitExpr_(const FloatImmObj* op) override;
  void VisitExpr_(const CastObj* op) override;
  void VisitExpr_(const AddObj* op) override;
  void VisitExpr_(const SubObj* op) override;
  void VisitExpr_(const MulObj* op) override;
  void VisitExpr_(const CDivObj* op) override;
  void VisitExpr_(const CModObj* op) override;
  void VisitExpr_(const FloorDivObj* op) override;
  void VisitExpr_(const FloorModObj* op) override;
  void VisitExpr_(const MinObj* op) override;
  void VisitExpr_(const MaxObj* op) override;
  void VisitExpr_(const EqObj* op) override;
  void VisitExpr_(const NeObj* op) override;
  void VisitExpr_(const LtObj* op) override;
  void VisitExpr_(const LeObj* op) override;
  void VisitExpr_(const GtObj* op) override;
  void VisitExpr_(const GeObj* op) override;
  void VisitExpr_(const AndObj* op) override;
  void VisitExpr_(const OrObj* op) override;
  void VisitExpr_(const NotObj* op) override;
  void VisitExpr_(const IfExprObj* op) override;
  void VisitExpr_(const LShiftObj* op) override;
  void VisitExpr_(const RShiftObj* op) override;
  void VisitExpr_(const BitwiseAndObj* op) override;
  void VisitExpr_(const BitwiseOrObj* op) override;
  void VisitExpr_(const BitwiseXorObj* op) override;
  void VisitExpr_(const BitwiseNotObj* op) override;
  void VisitExpr_(const AbsObj* op) override;
  void VisitExpr_(const CallObj* op) override;
};

struct ExprMutator : protected ExprFunctor<Expr(const Expr&)> {
  using ExprFunctor::operator();
  using ExprFunctor::VisitExpr;

 protected:
  Expr VisitExprDefault_(const Expr& obj) override { return obj; }
  Expr VisitExpr_(const VarObj* op) override;
  Expr VisitExpr_(const BoolImmObj* op) override;
  Expr VisitExpr_(const IntImmObj* op) override;
  Expr VisitExpr_(const FloatImmObj* op) override;
  Expr VisitExpr_(const CastObj* op) override;
  Expr VisitExpr_(const AddObj* op) override;
  Expr VisitExpr_(const SubObj* op) override;
  Expr VisitExpr_(const MulObj* op) override;
  Expr VisitExpr_(const CDivObj* op) override;
  Expr VisitExpr_(const CModObj* op) override;
  Expr VisitExpr_(const FloorDivObj* op) override;
  Expr VisitExpr_(const FloorModObj* op) override;
  Expr VisitExpr_(const MinObj* op) override;
  Expr VisitExpr_(const MaxObj* op) override;
  Expr VisitExpr_(const EqObj* op) override;
  Expr VisitExpr_(const NeObj* op) override;
  Expr VisitExpr_(const LtObj* op) override;
  Expr VisitExpr_(const LeObj* op) override;
  Expr VisitExpr_(const GtObj* op) override;
  Expr VisitExpr_(const GeObj* op) override;
  Expr VisitExpr_(const AndObj* op) override;
  Expr VisitExpr_(const OrObj* op) override;
  Expr VisitExpr_(const NotObj* op) override;
  Expr VisitExpr_(const IfExprObj* op) override;
  Expr VisitExpr_(const LShiftObj* op) override;
  Expr VisitExpr_(const RShiftObj* op) override;
  Expr VisitExpr_(const BitwiseAndObj* op) override;
  Expr VisitExpr_(const BitwiseOrObj* op) override;
  Expr VisitExpr_(const BitwiseXorObj* op) override;
  Expr VisitExpr_(const BitwiseNotObj* op) override;
  Expr VisitExpr_(const AbsObj* op) override;
  Expr VisitExpr_(const CallObj* op) override;
};

struct ExprDeepEqual : protected ExprFunctor<bool(const Expr&, void* other)> {
  static bool Compare(const Expr& lhs, const Expr& rhs) { return ExprDeepEqual().Visit(lhs, rhs); }

  bool VisitExpr(const Expr& n, void* rhs_obj) override {
    auto* rhs = static_cast<ExprObj*>(rhs_obj);
    if (n->type_index() != rhs->type_index()) return false;
    return ExprFunctor::VisitExpr(n, rhs_obj);
  }

  bool Visit(const Expr& lhs, const Expr& rhs) {
    return this->VisitExpr(lhs, const_cast<ExprObj*>(rhs.get()));
  }

  bool operator()(const Expr& lhs, const Expr& rhs) { return this->Visit(lhs, rhs); }

 private:
  bool VisitExpr_(const VarObj* lhs, void* rhs) override;
  bool VisitExpr_(const BoolImmObj* lhs, void* rhs) override;
  bool VisitExpr_(const IntImmObj* lhs, void* rhs) override;
  bool VisitExpr_(const FloatImmObj* lhs, void* rhs) override;
  bool VisitExpr_(const CastObj* lhs, void* rhs) override;
  bool VisitExpr_(const AddObj* lhs, void* rhs) override;
  bool VisitExpr_(const SubObj* lhs, void* rhs) override;
  bool VisitExpr_(const MulObj* lhs, void* rhs) override;
  bool VisitExpr_(const CDivObj* lhs, void* rhs) override;
  bool VisitExpr_(const CModObj* lhs, void* rhs) override;
  bool VisitExpr_(const FloorDivObj* lhs, void* rhs) override;
  bool VisitExpr_(const FloorModObj* lhs, void* rhs) override;
  bool VisitExpr_(const MinObj* lhs, void* rhs) override;
  bool VisitExpr_(const MaxObj* lhs, void* rhs) override;
  bool VisitExpr_(const EqObj* lhs, void* rhs) override;
  bool VisitExpr_(const NeObj* lhs, void* rhs) override;
  bool VisitExpr_(const LtObj* lhs, void* rhs) override;
  bool VisitExpr_(const LeObj* lhs, void* rhs) override;
  bool VisitExpr_(const GtObj* lhs, void* rhs) override;
  bool VisitExpr_(const GeObj* lhs, void* rhs) override;
  bool VisitExpr_(const AndObj* lhs, void* rhs) override;
  bool VisitExpr_(const OrObj* lhs, void* rhs) override;
  bool VisitExpr_(const NotObj* lhs, void* rhs) override;
  bool VisitExpr_(const IfExprObj* lhs, void* rhs) override;
  bool VisitExpr_(const LShiftObj* lhs, void* rhs) override;
  bool VisitExpr_(const RShiftObj* lhs, void* rhs) override;
  bool VisitExpr_(const BitwiseAndObj* lhs, void* rhs) override;
  bool VisitExpr_(const BitwiseOrObj* lhs, void* rhs) override;
  bool VisitExpr_(const BitwiseXorObj* lhs, void* rhs) override;
  bool VisitExpr_(const BitwiseNotObj* lhs, void* rhs) override;
  bool VisitExpr_(const AbsObj* lhs, void* rhs) override;
  bool VisitExpr_(const CallObj* lhs, void* rhs) override;
};

struct ExprStructuralHash {
  size_t operator()(const Expr& expr) const {
    return static_cast<size_t>(StructuralHash::Hash(Any(expr), false, true));
  }
};

struct ExprStructuralEqual {
  bool operator()(const Expr& lhs, const Expr& rhs) const {
    return ExprDeepEqual::Compare(lhs, rhs);
  }
};

struct IRMutatorWithAnalyzer : public ExprMutator {
  explicit IRMutatorWithAnalyzer(AnalyzerObj* analyzer) : analyzer_(analyzer->impl_.get()) {}
  explicit IRMutatorWithAnalyzer(AnalyzerObj::Impl* analyzer) : analyzer_(analyzer) {}
  using ExprMutator::VisitExpr_;
  TVM_FFI_EXTRA_CXX_API Expr VisitExpr_(const IfExprObj* op) override;

 protected:
  AnalyzerObj::Impl* analyzer_;
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_EXPR_FUNCTOR_H_
