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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_MODULAR_SET_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_MODULAR_SET_H_

#include <tvm/ffi/extra/std.h>

#include <sstream>

namespace tvm {
namespace ffi {
namespace std_ {

struct ModularSetObj : public Object {
  int64_t coeff;
  int64_t base;

  ModularSetObj() = default;
  explicit ModularSetObj(int64_t coeff, int64_t base) : coeff(coeff), base(base) {}

  std::string Str() const {
    std::ostringstream oss;
    oss << "ModularSet(coeff=" << coeff << ", base=" << base << ")";
    return oss.str();
  }

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.ModularSet", ModularSetObj, Object);
};

struct ModularSet : public ObjectRef {
  ModularSet(int64_t coeff, int64_t base) : ModularSet(make_object<ModularSetObj>(coeff, base)) {}

  explicit ModularSet(const ModularSetObj* ptr)
      : ModularSet(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<ModularSetObj>(
            const_cast<ModularSetObj*>(ptr))) {}

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(ModularSet, ObjectRef, ModularSetObj);
};

class ModularSetAnalyzer {
 public:
  ModularSet operator()(const Expr& expr);
  void Update(const Var& var, const ModularSet& info, bool allow_override = false);

  explicit ModularSetAnalyzer(AnalyzerObj::Impl* parent);
  ~ModularSetAnalyzer();
  std::function<void()> EnterConstraint(const Expr& constraint);
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_MODULAR_SET_H_
