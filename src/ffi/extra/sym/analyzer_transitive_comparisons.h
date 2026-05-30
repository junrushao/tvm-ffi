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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_TRANSITIVE_COMPARISONS_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_TRANSITIVE_COMPARISONS_H_

#include "./utils.h"

namespace tvm {
namespace ffi {
namespace std_ {

class TransitiveComparisonAnalyzer {
 public:
  CompareResult TryCompare(const Expr& lhs, const Expr& rhs, bool propagate_inequalities = true);
  void Bind(const Var& var, const Expr& expr, bool allow_override = false);
  void Bind(const Var& var, const Range& range, bool allow_override = false);
  std::function<void()> EnterConstraint(const Expr& constraint);

  explicit TransitiveComparisonAnalyzer(AnalyzerObj::Impl* analyzer);
  ~TransitiveComparisonAnalyzer();
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_TRANSITIVE_COMPARISONS_H_
