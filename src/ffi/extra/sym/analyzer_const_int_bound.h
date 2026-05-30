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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_CONST_INT_BOUND_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_CONST_INT_BOUND_H_

#include <tvm/ffi/extra/std.h>

#include <sstream>

namespace tvm {
namespace ffi {
namespace std_ {

struct ConstIntBoundObj : public Object {
  int64_t min_value;
  int64_t max_value;

  ConstIntBoundObj() = default;
  explicit ConstIntBoundObj(int64_t min_value, int64_t max_value)
      : min_value(min_value), max_value(max_value) {}

  std::string Str() const {
    std::ostringstream oss;
    oss << "ConstIntBound[" << min_value << ", " << max_value << "]";
    return oss.str();
  }

  static constexpr int64_t kPosInf = std::numeric_limits<int64_t>::max();
  static constexpr int64_t kNegInf = -kPosInf;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.ConstIntBound", ConstIntBoundObj, Object);
};

struct ConstIntBound : public ObjectRef {
  ConstIntBound(int64_t min_value, int64_t max_value)
      : ConstIntBound(make_object<ConstIntBoundObj>(min_value, max_value)) {}

  explicit ConstIntBound(const ConstIntBoundObj* ptr)
      : ConstIntBound(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<ConstIntBoundObj>(
            const_cast<ConstIntBoundObj*>(ptr))) {}

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(ConstIntBound, ObjectRef, ConstIntBoundObj);
};

struct ConstIntBoundAnalyzer {
  using BoundMapType = Dict<Expr, ConstIntBound>;
  ConstIntBound operator()(const Expr& expr) const;
  ConstIntBound operator()(const Expr& expr, BoundMapType* bound);
  void Update(const Var& var, const ConstIntBound& info, bool allow_override = false);
  void Bind(const Var& var, const Range& range, bool allow_override = false);

  explicit ConstIntBoundAnalyzer(AnalyzerObj::Impl* parent);
  ~ConstIntBoundAnalyzer();
  std::function<void()> EnterConstraint(const Expr& constraint);
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_CONST_INT_BOUND_H_
