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

#ifndef TVM_FFI_EXTRA_SYM_ANALYZER_INTERVAL_SET_H_
#define TVM_FFI_EXTRA_SYM_ANALYZER_INTERVAL_SET_H_

#include <tvm/ffi/extra/std.h>

#include <sstream>

namespace tvm {
namespace ffi {
namespace std_ {

struct IntervalSet;

struct IntervalSetObj : public Object {
  Expr min_value;
  Expr max_value;

  IntervalSetObj() = default;
  explicit IntervalSetObj(Expr min_value, Expr max_value)
      : min_value(std::move(min_value)), max_value(std::move(max_value)) {}

  bool HasUpperBound() const;
  bool HasLowerBound() const;
  bool IsSinglePoint() const;
  bool IsEmpty() const;
  bool IsEverything() const;
  std::string Str() const {
    std::ostringstream os;
    os << "IntervalSet[" << min_value << ", " << max_value << "]";
    return os.str();
  }
  IntervalSet Union(const IntervalSetObj* b, AnalyzerObj::Impl* analyzer) const;
  IntervalSet Intersect(const IntervalSetObj* b, AnalyzerObj::Impl* analyzer) const;

  TVM_FFI_DECLARE_OBJECT_INFO("ffi.std.IntervalSet", IntervalSetObj, Object);
};

struct IntervalSet : public ObjectRef {
  IntervalSet(Expr min_value, Expr max_value)
      : IntervalSet(make_object<IntervalSetObj>(std::move(min_value), std::move(max_value))) {}

  explicit IntervalSet(const IntervalSetObj* ptr)
      : IntervalSet(::tvm::ffi::details::ObjectUnsafe::ObjectPtrFromUnowned<IntervalSetObj>(
            const_cast<IntervalSetObj*>(ptr))) {}

  static IntervalSet Nothing() { return IntervalSet::Empty(); }
  static IntervalSet SinglePoint(const Expr& value) { return IntervalSet(value, value); }
  static IntervalSet Everything();
  static IntervalSet Empty();
  static IntervalSet FromRange(const Range& range);
  static IntervalSet Interval(const Expr& min, const Expr& max);

  TVM_FFI_DEFINE_OBJECT_REF_METHODS_NULLABLE(IntervalSet, ObjectRef, IntervalSetObj);
};

IntervalSet IntersectIntervalSets(const List<IntervalSet>& sets, AnalyzerObj::Impl* analyzer);

struct IntervalSetAnalyzer {
  IntervalSet operator()(const Expr& expr, const Dict<Var, IntervalSet>& dom_map);
  IntervalSet operator()(const Expr& expr);
  void Update(const Var& var, const IntervalSet& new_interval_set, bool allow_override = false);
  void Bind(const Var& var, const Range& new_range, bool allow_override = false);
  std::function<void()> EnterConstraint(const Expr& constraint);
  explicit IntervalSetAnalyzer(AnalyzerObj::Impl* parent);
  ~IntervalSetAnalyzer();
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace std_
}  // namespace ffi
}  // namespace tvm

#endif  // TVM_FFI_EXTRA_SYM_ANALYZER_INTERVAL_SET_H_
