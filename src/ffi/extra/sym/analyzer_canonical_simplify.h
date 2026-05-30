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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_CANONICAL_SIMPLIFY_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_CANONICAL_SIMPLIFY_H_

#include <sstream>

#include "./utils.h"

namespace tvm {
namespace ffi {
namespace std_ {

enum class DivMode {
  kTruncDiv = 0,
  kFloorDiv = 1,
};

class CanonicalSimplifier {
 public:
  Expr operator()(const Expr& expr);
  void Update(const Var& var, const Expr& new_expr, bool allow_override = false);

  explicit CanonicalSimplifier(AnalyzerObj::Impl* parent);
  ~CanonicalSimplifier();
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

struct SplitExpr;
struct SumExpr;

struct SplitExprObj : public ExprObj {
  Expr index;
  int64_t lower_factor;
  int64_t upper_factor;
  int64_t scale;
  DivMode div_mode;

  SplitExprObj() = default;
  explicit SplitExprObj(DLDataType dtype, Expr index, int64_t lower_factor, int64_t upper_factor,
                        int64_t scale, DivMode div_mode)
      : ExprObj(PrimTy(dtype)),
        index(std::move(index)),
        lower_factor(lower_factor),
        upper_factor(upper_factor),
        scale(scale),
        div_mode(div_mode) {}

  void Verify() const {
    if (!(upper_factor == kPosInf || upper_factor % lower_factor == 0)) {
      TVM_FFI_THROW(InternalError) << "Failed verification";
    }
  }
  std::string Str() const {
    std::ostringstream os;
    os << "SplitExpr(index=" << this->index << ", lower_factor=" << this->lower_factor
       << ", upper_factor=" << this->upper_factor << ", scale=" << this->scale
       << ", div_mode=" << (this->div_mode == DivMode::kTruncDiv ? "kTruncDiv" : "kFloorDiv")
       << ")";
    return os.str();
  }
  Expr NormalizeWithScale(int64_t sscale) const;
  Expr Normalize() const { return NormalizeWithScale(1); }
  void MulToSelf(int64_t s) { this->scale *= s; }
  bool CanPushCastToChildren(DLDataType dtype, AnalyzerObj::Impl* analyzer) const;
  void PushCastToChildren(DLDataType dtype);
  inline bool IndexEqual(const SplitExpr& other) const;
  inline bool DivModeCompatibleTo(DivMode mode) const;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.SplitExpr", SplitExprObj, ExprObj);
};

struct SplitExpr : public Expr {
  SplitExpr(DLDataType dtype, Expr index, int64_t lower_factor = 1, int64_t upper_factor = kPosInf,
            int64_t scale = 1, DivMode div_mode = DivMode::kTruncDiv)
      : SplitExpr(make_object<SplitExprObj>(dtype, std::move(index), lower_factor, upper_factor,
                                            scale, div_mode)) {}

  explicit SplitExpr(const SplitExprObj* ptr)
      : SplitExpr(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<SplitExprObj>(
            const_cast<SplitExprObj*>(ptr))) {}

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(SplitExpr, Expr, SplitExprObj);

  SplitExprObj* CopyOnWrite() {
    if (!data_.unique()) {
      data_ = make_object<SplitExprObj>(*get());
    }
    return get();
  }
};

struct SumExprObj : public ExprObj {
  std::vector<SplitExpr> args;
  int64_t base{0};

  SumExprObj() = default;
  explicit SumExprObj(DLDataType dtype, std::vector<SplitExpr> args, int64_t base)
      : ExprObj(PrimTy(dtype)), args(std::move(args)), base(base) {}
  explicit SumExprObj(DLDataType dtype) : ExprObj(PrimTy(dtype)) {}

  bool IsZero() const { return base == 0 && args.size() == 0; }
  Expr Normalize() const;
  bool DivisibleBy(int64_t scale);
  void MulToSelf(int64_t scale);
  void DivideBy(int64_t scale);
  void AddToSelf(int64_t value) { this->base += value; }
  void AddToSelf(SplitExpr other, int64_t scale);
  void AddToSelf(const SumExpr& other, int64_t scale);
  bool CanPushCastToChildren(DLDataType dtype, AnalyzerObj::Impl* analyzer) const;
  void PushCastToChildren(DLDataType dtype);
  std::string Str() const {
    std::ostringstream os;
    os << "SumExpr(base=" << this->base << ", args=[";
    bool is_first = true;
    for (const auto& arg : this->args) {
      if (!is_first) {
        os << ", ";
      } else {
        is_first = false;
      }
      os << arg->Str();
    }
    os << "])";
    return os.str();
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.SumExpr", SumExprObj, ExprObj);

 private:
  static std::vector<SplitExpr> SimplifySplitExprs(std::vector<SplitExpr> args);
  static Expr Normalize_(DLDataType dtype, const std::vector<SplitExpr>& args, int64_t base);
};

struct SumExpr : public Expr {
  explicit SumExpr(DLDataType dtype) : SumExpr(make_object<SumExprObj>(dtype)) {}
  SumExpr(DLDataType dtype, std::vector<SplitExpr> args, int64_t base)
      : SumExpr(make_object<SumExprObj>(dtype, std::move(args), base)) {}

  explicit SumExpr(const SumExprObj* ptr)
      : SumExpr(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<SumExprObj>(
            const_cast<SumExprObj*>(ptr))) {}

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(SumExpr, Expr, SumExprObj);

  SumExprObj* CopyOnWrite() {
    if (!data_.unique()) {
      data_ = make_object<SumExprObj>(*get());
    }
    return get();
  }
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_CANONICAL_SIMPLIFY_H_
