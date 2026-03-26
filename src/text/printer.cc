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
/*!
 * \file src/text/printer.cc
 * \brief Python-style text printer: converts text format AST to Python source.
 */
#include <tvm/ffi/base_details.h>
#include <tvm/ffi/cast.h>
#include <tvm/ffi/reflection/accessor.h>
#include <tvm/ffi/reflection/registry.h>
#include <tvm/ffi/string.h>
#include <tvm/ffi/text/printer.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace tvm {
namespace ffi {
namespace text {
namespace {

// ============================================================================
// Byte span helpers
// ============================================================================

using ByteSpan = std::pair<size_t, size_t>;

// ============================================================================
// DocPrinter — abstract base for rendering the text format AST
// ============================================================================

class DocPrinter {
 public:
  explicit DocPrinter(PrinterConfig options);
  virtual ~DocPrinter() = default;

  void Append(const NodeAST& doc);
  void Append(const NodeAST& doc, const PrinterConfig& cfg);
  String GetString() const;

 protected:
  void PrintDoc(const NodeAST& doc);
  virtual void PrintTypedDoc(const LiteralAST& doc) = 0;
  virtual void PrintTypedDoc(const IdAST& doc) = 0;
  virtual void PrintTypedDoc(const AttrAST& doc) = 0;
  virtual void PrintTypedDoc(const IndexAST& doc) = 0;
  virtual void PrintTypedDoc(const OperationAST& doc) = 0;
  virtual void PrintTypedDoc(const CallAST& doc) = 0;
  virtual void PrintTypedDoc(const LambdaAST& doc) = 0;
  virtual void PrintTypedDoc(const ListAST& doc) = 0;
  virtual void PrintTypedDoc(const TupleAST& doc) = 0;
  virtual void PrintTypedDoc(const DictAST& doc) = 0;
  virtual void PrintTypedDoc(const SliceAST& doc) = 0;
  virtual void PrintTypedDoc(const StmtBlockAST& doc) = 0;
  virtual void PrintTypedDoc(const AssignAST& doc) = 0;
  virtual void PrintTypedDoc(const IfAST& doc) = 0;
  virtual void PrintTypedDoc(const WhileAST& doc) = 0;
  virtual void PrintTypedDoc(const ForAST& doc) = 0;
  virtual void PrintTypedDoc(const WithAST& doc) = 0;
  virtual void PrintTypedDoc(const ExprStmtAST& doc) = 0;
  virtual void PrintTypedDoc(const AssertAST& doc) = 0;
  virtual void PrintTypedDoc(const ReturnAST& doc) = 0;
  virtual void PrintTypedDoc(const FunctionAST& doc) = 0;
  virtual void PrintTypedDoc(const ClassAST& doc) = 0;
  virtual void PrintTypedDoc(const CommentAST& doc) = 0;
  virtual void PrintTypedDoc(const DocStringAST& doc) = 0;

  void PrintTypedDoc(const NodeASTObj* doc) {
    using PrinterVTable =
        std::unordered_map<int32_t, std::function<void(DocPrinter*, const NodeASTObj*)>>;
    // clang-format off
    #define TVM_FFI_PRINTER_VTABLE_ENTRY_(Type)                                    \
      { Type##Obj::RuntimeTypeIndex(),                                             \
        [](DocPrinter* printer, const NodeASTObj* d) {                         \
          printer->PrintTypedDoc(Type(GetObjectPtr<Type##Obj>(                     \
              const_cast<Type##Obj*>(static_cast<const Type##Obj*>(d)))));          \
        } }
    // clang-format on
    static PrinterVTable vtable{
        TVM_FFI_PRINTER_VTABLE_ENTRY_(LiteralAST),   TVM_FFI_PRINTER_VTABLE_ENTRY_(IdAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(AttrAST),      TVM_FFI_PRINTER_VTABLE_ENTRY_(IndexAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(OperationAST), TVM_FFI_PRINTER_VTABLE_ENTRY_(CallAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(LambdaAST),    TVM_FFI_PRINTER_VTABLE_ENTRY_(ListAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(TupleAST),     TVM_FFI_PRINTER_VTABLE_ENTRY_(DictAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(SliceAST),     TVM_FFI_PRINTER_VTABLE_ENTRY_(StmtBlockAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(AssignAST),    TVM_FFI_PRINTER_VTABLE_ENTRY_(IfAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(WhileAST),     TVM_FFI_PRINTER_VTABLE_ENTRY_(ForAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(WithAST),      TVM_FFI_PRINTER_VTABLE_ENTRY_(ExprStmtAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(AssertAST),    TVM_FFI_PRINTER_VTABLE_ENTRY_(ReturnAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(FunctionAST),  TVM_FFI_PRINTER_VTABLE_ENTRY_(ClassAST),
        TVM_FFI_PRINTER_VTABLE_ENTRY_(CommentAST),   TVM_FFI_PRINTER_VTABLE_ENTRY_(DocStringAST),
    };
    // clang-format off
    #undef TVM_FFI_PRINTER_VTABLE_ENTRY_
    // clang-format on
    vtable.at(doc->type_index())(this, doc);
  }

  void IncreaseIndent() { indent_ += options_->indent_spaces; }
  void DecreaseIndent() { indent_ -= options_->indent_spaces; }
  std::ostream& NewLine() {
    size_t start_pos = output_.tellp();
    output_ << "\n";
    line_starts_.push_back(output_.tellp());
    for (int i = 0; i < indent_; ++i) {
      output_ << ' ';
    }
    size_t end_pos = output_.tellp();
    underlines_exempted_.emplace_back(start_pos, end_pos);
    return output_;
  }
  std::ostringstream output_;
  std::vector<ByteSpan> underlines_exempted_;

 private:
  void MarkSpan(const ByteSpan& span, const AccessPath& path);
  PrinterConfig options_;
  int indent_ = 0;
  std::vector<size_t> line_starts_;
  List<AccessPath> path_to_underline_;
  std::vector<std::vector<ByteSpan>> current_underline_candidates_;
  std::vector<int> current_max_path_length_;
  std::vector<ByteSpan> underlines_;
};

// ============================================================================
// OpKind helpers
// ============================================================================

inline const char* OpKindToString(OperationASTObj::Kind kind) {
  switch (kind) {
    case OperationASTObj::Kind::kUSub:
      return "-";
    case OperationASTObj::Kind::kInvert:
      return "~";
    case OperationASTObj::Kind::kNot:
      return "not ";
    case OperationASTObj::Kind::kAdd:
      return "+";
    case OperationASTObj::Kind::kSub:
      return "-";
    case OperationASTObj::Kind::kMult:
      return "*";
    case OperationASTObj::Kind::kDiv:
      return "/";
    case OperationASTObj::Kind::kFloorDiv:
      return "//";
    case OperationASTObj::Kind::kMod:
      return "%";
    case OperationASTObj::Kind::kPow:
      return "**";
    case OperationASTObj::Kind::kLShift:
      return "<<";
    case OperationASTObj::Kind::kRShift:
      return ">>";
    case OperationASTObj::Kind::kBitAnd:
      return "&";
    case OperationASTObj::Kind::kBitOr:
      return "|";
    case OperationASTObj::Kind::kBitXor:
      return "^";
    case OperationASTObj::Kind::kLt:
      return "<";
    case OperationASTObj::Kind::kLtE:
      return "<=";
    case OperationASTObj::Kind::kEq:
      return "==";
    case OperationASTObj::Kind::kNotEq:
      return "!=";
    case OperationASTObj::Kind::kGt:
      return ">";
    case OperationASTObj::Kind::kGtE:
      return ">=";
    case OperationASTObj::Kind::kAnd:
      return "and";
    case OperationASTObj::Kind::kOr:
      return "or";
    default:
      TVM_FFI_THROW(ValueError) << "Unknown operation kind: " << static_cast<int>(kind);
  }
  TVM_FFI_UNREACHABLE();
}

inline const char* OpKindToString(int64_t kind) {
  return OpKindToString(static_cast<OperationASTObj::Kind>(kind));
}

// ============================================================================
// ExprPrecedence
// ============================================================================

/*!
 * \brief Operator precedence based on
 * https://docs.python.org/3/reference/expressions.html#operator-precedence
 */
enum class ExprPrecedence : int32_t {
  /*! \brief Unknown precedence */
  kUnkown = 0,
  /*! \brief Lambda Expression */
  kLambda = 1,
  /*! \brief Conditional Expression */
  kIfThenElse = 2,
  /*! \brief Boolean OR */
  kBooleanOr = 3,
  /*! \brief Boolean AND */
  kBooleanAnd = 4,
  /*! \brief Boolean NOT */
  kBooleanNot = 5,
  /*! \brief Comparisons */
  kComparison = 6,
  /*! \brief Bitwise OR */
  kBitwiseOr = 7,
  /*! \brief Bitwise XOR */
  kBitwiseXor = 8,
  /*! \brief Bitwise AND */
  kBitwiseAnd = 9,
  /*! \brief Shift Operators */
  kShift = 10,
  /*! \brief Addition and subtraction */
  kAdd = 11,
  /*! \brief Multiplication, division, floor division, remainder */
  kMult = 12,
  /*! \brief Positive negative and bitwise NOT */
  kUnary = 13,
  /*! \brief Exponentiation */
  kExp = 14,
  /*! \brief Index access, attribute access, call and atom expression */
  kIdentity = 15,
};

inline ExprPrecedence GetExprPrecedence(const ExprAST& doc) {
  // Key is the type index of Doc
  static const std::unordered_map<uint32_t, ExprPrecedence> doc_type_precedence = {
      {LiteralASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {IdASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {AttrASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {IndexASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {CallASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {LambdaASTObj::RuntimeTypeIndex(), ExprPrecedence::kLambda},
      {TupleASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {ListASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
      {DictASTObj::RuntimeTypeIndex(), ExprPrecedence::kIdentity},
  };
  // Key is the value of OperationASTObj::Kind
  static const std::vector<ExprPrecedence> op_kind_precedence = []() {
    using OpKind = OperationASTObj::Kind;
    std::map<OpKind, ExprPrecedence> raw_table = {
        {OpKind::kUSub, ExprPrecedence::kUnary},
        {OpKind::kInvert, ExprPrecedence::kUnary},
        {OpKind::kNot, ExprPrecedence::kBooleanNot},
        {OpKind::kAdd, ExprPrecedence::kAdd},
        {OpKind::kSub, ExprPrecedence::kAdd},
        {OpKind::kMult, ExprPrecedence::kMult},
        {OpKind::kDiv, ExprPrecedence::kMult},
        {OpKind::kFloorDiv, ExprPrecedence::kMult},
        {OpKind::kMod, ExprPrecedence::kMult},
        {OpKind::kPow, ExprPrecedence::kExp},
        {OpKind::kLShift, ExprPrecedence::kShift},
        {OpKind::kRShift, ExprPrecedence::kShift},
        {OpKind::kBitAnd, ExprPrecedence::kBitwiseAnd},
        {OpKind::kBitOr, ExprPrecedence::kBitwiseOr},
        {OpKind::kBitXor, ExprPrecedence::kBitwiseXor},
        {OpKind::kLt, ExprPrecedence::kComparison},
        {OpKind::kLtE, ExprPrecedence::kComparison},
        {OpKind::kEq, ExprPrecedence::kComparison},
        {OpKind::kNotEq, ExprPrecedence::kComparison},
        {OpKind::kGt, ExprPrecedence::kComparison},
        {OpKind::kGtE, ExprPrecedence::kComparison},
        {OpKind::kAnd, ExprPrecedence::kBooleanAnd},
        {OpKind::kOr, ExprPrecedence::kBooleanOr},
        {OpKind::kIfThenElse, ExprPrecedence::kIfThenElse},
    };
    std::vector<ExprPrecedence> table(static_cast<size_t>(OpKind::kSpecialEnd) + 1,
                                      ExprPrecedence::kUnkown);
    for (const auto& kv : raw_table) {
      table[static_cast<int>(kv.first)] = kv.second;
    }
    return table;
  }();
  if (const auto* op_doc = doc->IsInstance<OperationASTObj>()
                               ? static_cast<const OperationASTObj*>(doc.get())
                               : nullptr) {
    ExprPrecedence precedence = op_kind_precedence.at(op_doc->op);
    if (precedence == ExprPrecedence::kUnkown) {
      TVM_FFI_THROW(ValueError) << "Unknown precedence for operator: " << op_doc->op;
    }
    return precedence;
  } else if (auto it = doc_type_precedence.find(doc->type_index());
             it != doc_type_precedence.end()) {
    return it->second;
  }
  TVM_FFI_THROW(ValueError) << "Unknown precedence for doc type: " << doc->GetTypeKey();
  TVM_FFI_UNREACHABLE();
}

// ============================================================================
// Span / underline helpers
// ============================================================================

inline std::vector<ByteSpan> MergeAndExemptSpans(const std::vector<ByteSpan>& spans,
                                                 const std::vector<ByteSpan>& spans_exempted) {
  std::vector<ByteSpan> res;
  std::vector<std::pair<size_t, int>> prefix_stamp;
  for (ByteSpan span : spans) {
    prefix_stamp.emplace_back(span.first, 1);
    prefix_stamp.emplace_back(span.second, -1);
  }
  int max_n = static_cast<int>(spans.size()) + 1;
  for (ByteSpan span : spans_exempted) {
    prefix_stamp.emplace_back(span.first, -max_n);
    prefix_stamp.emplace_back(span.second, max_n);
  }
  std::sort(prefix_stamp.begin(), prefix_stamp.end());
  int prefix_sum = 0;
  int n = static_cast<int>(prefix_stamp.size());
  for (int i = 0; i < n - 1; ++i) {
    prefix_sum += prefix_stamp[i].second;
    if (prefix_sum > 0 && prefix_stamp[i].first < prefix_stamp[i + 1].first) {
      if (res.size() && res.back().second == prefix_stamp[i].first) {
        res.back().second = prefix_stamp[i + 1].first;
      } else {
        res.emplace_back(prefix_stamp[i].first, prefix_stamp[i + 1].first);
      }
    }
  }
  return res;
}

inline size_t GetTextWidth(const String& text, const ByteSpan& span) {
  // FIXME: this only works for ASCII characters.
  size_t ret = 0;
  for (size_t i = span.first; i != span.second; ++i) {
    if (isprint(text.data()[i])) {
      ret += 1;
    }
  }
  return ret;
}

inline size_t MoveBack(size_t pos, size_t distance) { return distance > pos ? 0 : pos - distance; }

inline size_t MoveForward(size_t pos, size_t distance, size_t max) {
  return distance > max - pos ? max : pos + distance;
}

inline size_t GetLineIndex(size_t byte_pos, const std::vector<size_t>& line_starts) {
  auto it = std::upper_bound(line_starts.begin(), line_starts.end(), byte_pos);
  return (it - line_starts.begin()) - 1;
}

using UnderlineIter = typename std::vector<ByteSpan>::const_iterator;

inline ByteSpan PopNextUnderline(UnderlineIter* next_underline, UnderlineIter end_underline) {
  if (*next_underline == end_underline) {
    constexpr size_t kMaxSizeT = 18446744073709551615U;
    return {kMaxSizeT, kMaxSizeT};
  } else {
    return *(*next_underline)++;
  }
}

inline void PrintChunk(const std::pair<size_t, size_t>& lines_range,
                       const std::pair<UnderlineIter, UnderlineIter>& underlines,
                       const String& text, const std::vector<size_t>& line_starts,
                       const PrinterConfig& options, size_t line_number_width,
                       std::ostringstream* out) {
  UnderlineIter next_underline = underlines.first;
  ByteSpan current_underline = PopNextUnderline(&next_underline, underlines.second);

  for (size_t line_idx = lines_range.first; line_idx < lines_range.second; ++line_idx) {
    if (options->print_line_numbers) {
      (*out) << std::setw(static_cast<int>(line_number_width)) << std::right
             << std::to_string(line_idx + 1) << ' ';
    }
    size_t line_start = line_starts.at(line_idx);
    size_t line_end =
        line_idx + 1 == line_starts.size() ? text.size() : line_starts.at(line_idx + 1);
    (*out) << std::string_view(text.data() + line_start, line_end - line_start);
    bool printed_underline = false;
    size_t line_pos = line_start;
    bool printed_extra_caret = false;
    while (current_underline.first < line_end) {
      if (!printed_underline) {
        for (size_t i = 0; i < line_number_width; ++i) {
          (*out) << ' ';
        }
        printed_underline = true;
      }
      size_t underline_end_for_line = std::min<size_t>(line_end, current_underline.second);
      size_t num_spaces = GetTextWidth(text, {line_pos, current_underline.first});
      if (num_spaces > 0 && printed_extra_caret) {
        num_spaces -= 1;
        printed_extra_caret = false;
      }
      for (size_t i = 0; i < num_spaces; ++i) {
        (*out) << ' ';
      }
      size_t num_carets = GetTextWidth(text, {current_underline.first, underline_end_for_line});
      if (num_carets == 0 && !printed_extra_caret) {
        num_carets = 1;
        printed_extra_caret = true;
      } else if (num_carets > 0 && printed_extra_caret) {
        num_carets -= 1;
        printed_extra_caret = false;
      }
      for (size_t i = 0; i < num_carets; ++i) {
        (*out) << '^';
      }
      line_pos = current_underline.first = underline_end_for_line;
      if (current_underline.first == current_underline.second) {
        current_underline = PopNextUnderline(&next_underline, underlines.second);
      }
    }
    if (printed_underline) {
      (*out) << '\n';
    }
  }
}

inline void PrintCut(size_t num_lines_skipped, std::ostringstream* out) {
  if (num_lines_skipped != 0) {
    (*out) << "(... " << num_lines_skipped << " lines skipped ...)\n";
  }
}

inline std::pair<size_t, size_t> GetLinesForUnderline(const ByteSpan& underline,
                                                      const std::vector<size_t>& line_starts,
                                                      size_t num_lines,
                                                      const PrinterConfig& options) {
  size_t first_line_of_underline = GetLineIndex(underline.first, line_starts);
  size_t first_line_of_chunk = MoveBack(first_line_of_underline, options->num_context_lines);
  size_t end_line_of_underline = GetLineIndex(underline.second - 1, line_starts) + 1;
  size_t end_line_of_chunk =
      MoveForward(end_line_of_underline, options->num_context_lines, num_lines);
  return {first_line_of_chunk, end_line_of_chunk};
}

constexpr const size_t kMinLinesToCutOut = 2;

inline bool TryMergeChunks(std::pair<size_t, size_t>* cur_chunk,
                           const std::pair<size_t, size_t>& new_chunk) {
  if (new_chunk.first < cur_chunk->second + kMinLinesToCutOut) {
    cur_chunk->second = new_chunk.second;
    return true;
  } else {
    return false;
  }
}

inline size_t GetNumLines(const String& text, const std::vector<size_t>& line_starts) {
  if (static_cast<int64_t>(line_starts.back()) == static_cast<int64_t>(text.size())) {
    return line_starts.size() - 1;
  } else {
    return line_starts.size();
  }
}

inline size_t GetLineNumberWidth(size_t num_lines, const PrinterConfig& options) {
  if (options->print_line_numbers) {
    return std::to_string(num_lines).size() + 1;
  } else {
    return 0;
  }
}

inline String DecorateText(const String& text, const std::vector<size_t>& line_starts,
                           const PrinterConfig& options, const std::vector<ByteSpan>& underlines) {
  size_t num_lines = GetNumLines(text, line_starts);
  size_t line_number_width = GetLineNumberWidth(num_lines, options);

  std::ostringstream ret;
  if (underlines.empty()) {
    PrintChunk({0, num_lines}, {underlines.begin(), underlines.begin()}, text, line_starts, options,
               line_number_width, &ret);
    return String(ret.str());
  }

  size_t last_end_line = 0;
  std::pair<size_t, size_t> cur_chunk =
      GetLinesForUnderline(underlines[0], line_starts, num_lines, options);
  if (cur_chunk.first < kMinLinesToCutOut) {
    cur_chunk.first = 0;
  }

  auto first_underline_in_cur_chunk = underlines.begin();
  for (auto underline_it = underlines.begin() + 1; underline_it != underlines.end();
       ++underline_it) {
    std::pair<size_t, size_t> new_chunk =
        GetLinesForUnderline(*underline_it, line_starts, num_lines, options);
    if (!TryMergeChunks(&cur_chunk, new_chunk)) {
      PrintCut(cur_chunk.first - last_end_line, &ret);
      PrintChunk(cur_chunk, {first_underline_in_cur_chunk, underline_it}, text, line_starts,
                 options, line_number_width, &ret);
      last_end_line = cur_chunk.second;
      cur_chunk = new_chunk;
      first_underline_in_cur_chunk = underline_it;
    }
  }

  PrintCut(cur_chunk.first - last_end_line, &ret);
  if (num_lines - cur_chunk.second < kMinLinesToCutOut) {
    cur_chunk.second = num_lines;
  }
  PrintChunk(cur_chunk, {first_underline_in_cur_chunk, underlines.end()}, text, line_starts,
             options, line_number_width, &ret);
  PrintCut(num_lines - cur_chunk.second, &ret);
  return String(ret.str());
}

// ============================================================================
// DocPrinter implementation
// ============================================================================

inline DocPrinter::DocPrinter(PrinterConfig options) : options_(std::move(options)) {
  line_starts_.push_back(0);
}

inline void DocPrinter::Append(const NodeAST& doc) { Append(doc, PrinterConfig()); }

inline void DocPrinter::Append(const NodeAST& doc, const PrinterConfig& cfg) {
  for (AccessPath p : cfg->path_to_underline) {
    path_to_underline_.push_back(p);
    current_max_path_length_.push_back(0);
    current_underline_candidates_.emplace_back();
  }
  PrintDoc(doc);
  for (const auto& c : current_underline_candidates_) {
    underlines_.insert(underlines_.end(), c.begin(), c.end());
  }
}

inline String DocPrinter::GetString() const {
  std::string text = output_.str();
  // Remove any trailing indentation
  while (!text.empty() && text.back() == ' ') {
    text.pop_back();
  }
  if (!text.empty() && text.back() != '\n') {
    text.push_back('\n');
  }
  String text_str(text);
  return DecorateText(text_str, line_starts_, options_,
                      MergeAndExemptSpans(underlines_, underlines_exempted_));
}

inline void DocPrinter::PrintDoc(const NodeAST& doc) {
  size_t start_pos = output_.tellp();
  this->PrintTypedDoc(doc.get());
  size_t end_pos = output_.tellp();
  for (AccessPath path : doc->source_paths) {
    MarkSpan({start_pos, end_pos}, path);
  }
}

inline void DocPrinter::MarkSpan(const ByteSpan& span, const AccessPath& path) {
  int n = static_cast<int>(path_to_underline_.size());
  for (int i = 0; i < n; ++i) {
    AccessPath p = path_to_underline_[i];
    if (path->depth >= current_max_path_length_[i] && path->IsPrefixOf(p)) {
      if (path->depth > current_max_path_length_[i]) {
        current_max_path_length_[i] = static_cast<int>(path->depth);
        current_underline_candidates_[i].clear();
      }
      current_underline_candidates_[i].push_back(span);
    }
  }
}

// ============================================================================
// PythonDocPrinter
// ============================================================================

class PythonDocPrinter : public DocPrinter {
 public:
  explicit PythonDocPrinter(const PrinterConfig& options) : DocPrinter(options) {}

 protected:
  using DocPrinter::PrintDoc;

  void PrintTypedDoc(const LiteralAST& doc) final;
  void PrintTypedDoc(const IdAST& doc) final;
  void PrintTypedDoc(const AttrAST& doc) final;
  void PrintTypedDoc(const IndexAST& doc) final;
  void PrintTypedDoc(const OperationAST& doc) final;
  void PrintTypedDoc(const CallAST& doc) final;
  void PrintTypedDoc(const LambdaAST& doc) final;
  void PrintTypedDoc(const ListAST& doc) final;
  void PrintTypedDoc(const DictAST& doc) final;
  void PrintTypedDoc(const TupleAST& doc) final;
  void PrintTypedDoc(const SliceAST& doc) final;
  void PrintTypedDoc(const StmtBlockAST& doc) final;
  void PrintTypedDoc(const AssignAST& doc) final;
  void PrintTypedDoc(const IfAST& doc) final;
  void PrintTypedDoc(const WhileAST& doc) final;
  void PrintTypedDoc(const ForAST& doc) final;
  void PrintTypedDoc(const ExprStmtAST& doc) final;
  void PrintTypedDoc(const AssertAST& doc) final;
  void PrintTypedDoc(const ReturnAST& doc) final;
  void PrintTypedDoc(const WithAST& doc) final;
  void PrintTypedDoc(const FunctionAST& doc) final;
  void PrintTypedDoc(const ClassAST& doc) final;
  void PrintTypedDoc(const CommentAST& doc) final;
  void PrintTypedDoc(const DocStringAST& doc) final;

 private:
  void NewLineWithoutIndent() {
    size_t start_pos = output_.tellp();
    output_ << "\n";
    size_t end_pos = output_.tellp();
    underlines_exempted_.emplace_back(start_pos, end_pos);
  }

  template <typename DocType>
  void PrintJoinedDocs(const List<DocType>& docs, const char* separator) {
    bool is_first = true;
    for (DocType doc : docs) {
      if (is_first) {
        is_first = false;
      } else {
        output_ << separator;
      }
      PrintDoc(doc);
    }
  }

  void PrintIndentedBlock(const List<StmtAST>& docs) {
    IncreaseIndent();
    for (StmtAST d : docs) {
      NewLine();
      PrintDoc(d);
    }
    if (docs.empty()) {
      NewLine();
      output_ << "pass";
    }
    DecreaseIndent();
  }

  void PrintDecorators(const List<ExprAST>& decorators) {
    for (ExprAST decorator : decorators) {
      output_ << "@";
      PrintDoc(decorator);
      NewLine();
    }
  }

  /*!
   * \brief Print expression and add parenthesis if needed.
   */
  void PrintChildExpr(const ExprAST& doc, ExprPrecedence parent_precedence,
                      bool parenthesis_for_same_precedence = false) {
    ExprPrecedence doc_precedence = GetExprPrecedence(doc);
    if (doc_precedence < parent_precedence ||
        (parenthesis_for_same_precedence && doc_precedence == parent_precedence)) {
      output_ << "(";
      PrintDoc(doc);
      output_ << ")";
    } else {
      PrintDoc(doc);
    }
  }

  /*!
   * \brief Print expression and add parenthesis if doc has lower precedence than parent.
   */
  void PrintChildExpr(const ExprAST& doc, const ExprAST& parent,
                      bool parenthesis_for_same_precedence = false) {
    ExprPrecedence parent_precedence = GetExprPrecedence(parent);
    return PrintChildExpr(doc, parent_precedence, parenthesis_for_same_precedence);
  }

  /*!
   * \brief Print expression and add parenthesis if doc doesn't have higher precedence than parent.
   */
  void PrintChildExprConservatively(const ExprAST& doc, const ExprAST& parent) {
    PrintChildExpr(doc, parent, /*parenthesis_for_same_precedence=*/true);
  }

  void MaybePrintCommentInline(const StmtAST& stmt) {
    if (stmt->comment.has_value()) {
      String comment = stmt->comment.value();
      std::string_view sv(comment.data(), comment.size());
      bool has_newline = sv.find('\n') != std::string_view::npos;
      if (has_newline) {
        TVM_FFI_THROW(ValueError) << "ValueError: Comment string of " << stmt->GetTypeKey()
                                  << " cannot have newline, but got: " << comment;
      }
      size_t start_pos = output_.tellp();
      output_ << "  # " << comment.data();
      size_t end_pos = output_.tellp();
      underlines_exempted_.emplace_back(start_pos, end_pos);
    }
  }

  void MaybePrintCommentMultiLines(const StmtAST& stmt, bool new_line = false) {
    if (stmt->comment.has_value()) {
      String comment = stmt->comment.value();
      bool first_line = true;
      size_t start_pos = output_.tellp();
      for (const std::string_view& line : comment.Split('\n')) {
        if (first_line) {
          output_ << "# " << line;
          first_line = false;
        } else {
          NewLine() << "# " << line;
        }
      }
      size_t end_pos = output_.tellp();
      underlines_exempted_.emplace_back(start_pos, end_pos);
      if (new_line) {
        NewLine();
      }
    }
  }

  void PrintDocString(const String& comment) {
    size_t start_pos = output_.tellp();
    output_ << R"(""")";
    for (const std::string_view& line : comment.Split('\n')) {
      if (line.empty()) {
        output_ << "\n";
      } else {
        NewLine() << line;
      }
    }
    NewLine() << R"(""")";

    size_t end_pos = output_.tellp();
    underlines_exempted_.emplace_back(start_pos, end_pos);
  }

  void PrintBlockComment(const String& comment) {
    IncreaseIndent();
    NewLine();
    PrintDocString(comment);
    DecreaseIndent();
  }
};

// ============================================================================
// PythonDocPrinter — typed doc printing methods
// ============================================================================

inline void PythonDocPrinter::PrintTypedDoc(const LiteralAST& doc) {
  Any value = doc->value;
  int32_t type_index = value.type_index();
  if (type_index == TypeIndex::kTVMFFINone) {
    output_ << "None";
  } else if (type_index == TypeIndex::kTVMFFIBool) {
    output_ << (value.cast<bool>() ? "True" : "False");
  } else if (type_index == TypeIndex::kTVMFFIInt) {
    output_ << value.cast<int64_t>();
  } else if (type_index == TypeIndex::kTVMFFIFloat) {
    double v = value.cast<double>();
    if (std::isinf(v) || std::isnan(v)) {
      output_ << '"' << v << '"';
    } else if (std::nearbyint(v) == v) {
      std::showpoint(output_);
      std::fixed(output_);
      output_.precision(1);
      output_ << v;
    } else {
      std::defaultfloat(output_);
      std::noshowpoint(output_);
      output_.precision(17);
      output_ << v;
    }
  } else if (type_index == TypeIndex::kTVMFFIStr || type_index == TypeIndex::kTVMFFISmallStr) {
    PrintEscapeString(output_, value.cast<String>());
  } else {
    TVM_FFI_THROW(TypeError) << "TypeError: Unsupported literal value type: " << value.type_index();
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const IdAST& doc) { output_ << doc->name; }

inline void PythonDocPrinter::PrintTypedDoc(const AttrAST& doc) {
  PrintChildExpr(doc->obj, ExprAST(  // NOLINT(clang-analyzer-core.NonNullParamChecker)
                               GetObjectPtr<ExprASTObj>(const_cast<AttrASTObj*>(doc.get()))));
  output_ << "." << doc->name;
}

inline void PythonDocPrinter::PrintTypedDoc(const IndexAST& doc) {
  PrintChildExpr(doc->obj, ExprAST(  // NOLINT(clang-analyzer-core.NonNullParamChecker)
                               GetObjectPtr<ExprASTObj>(const_cast<IndexASTObj*>(doc.get()))));
  if (doc->idx.size() == 0) {
    output_ << "[()]";
  } else {
    output_ << "[";
    PrintJoinedDocs(doc->idx, ", ");
    output_ << "]";
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const OperationAST& doc) {
  using OpKind = OperationASTObj::Kind;
  ExprAST doc_as_expr(GetObjectPtr<ExprASTObj>(const_cast<OperationASTObj*>(doc.get())));
  if (doc->op < OpKind::kUnaryEnd) {
    if (doc->operands.size() != 1) {
      TVM_FFI_THROW(ValueError) << "ValueError: Unary operator requires 1 operand, but got "
                                << doc->operands.size();
    }
    output_ << OpKindToString(doc->op);
    PrintChildExpr(doc->operands[0], doc_as_expr);
  } else if (doc->op == OpKind::kPow) {
    if (doc->operands.size() != 2) {
      TVM_FFI_THROW(ValueError) << "Operator '**' requires 2 operands, but got "
                                << doc->operands.size();
    }
    PrintChildExprConservatively(doc->operands[0], doc_as_expr);
    output_ << " ** ";
    PrintChildExpr(doc->operands[1], ExprPrecedence::kUnary);
  } else if (doc->op < OpKind::kBinaryEnd) {
    if (doc->operands.size() != 2) {
      TVM_FFI_THROW(ValueError) << "Binary operator requires 2 operands, but got "
                                << doc->operands.size();
    }
    PrintChildExpr(doc->operands[0], doc_as_expr);
    output_ << " " << OpKindToString(doc->op) << " ";
    PrintChildExprConservatively(doc->operands[1], doc_as_expr);
  } else if (doc->op == OpKind::kIfThenElse) {
    if (doc->operands.size() != 3) {
      TVM_FFI_THROW(ValueError) << "IfThenElse requires 3 operands, but got "
                                << doc->operands.size();
    }
    PrintChildExpr(doc->operands[1], doc_as_expr);
    output_ << " if ";
    PrintChildExprConservatively(doc->operands[0], doc_as_expr);
    output_ << " else ";
    PrintChildExprConservatively(doc->operands[2], doc_as_expr);
  } else {
    TVM_FFI_THROW(ValueError) << "Unknown OperationASTObj::Kind " << static_cast<int>(doc->op);
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const CallAST& doc) {
  PrintChildExpr(doc->callee, ExprAST(  // NOLINT(clang-analyzer-core.NonNullParamChecker)
                                  GetObjectPtr<ExprASTObj>(const_cast<CallASTObj*>(doc.get()))));
  output_ << "(";
  bool is_first = true;
  for (ExprAST arg : doc->args) {
    if (is_first) {
      is_first = false;
    } else {
      output_ << ", ";
    }
    PrintDoc(arg);
  }
  if (doc->kwargs_keys.size() != doc->kwargs_values.size()) {
    TVM_FFI_THROW(ValueError)
        << "CallDoc should have equal number of elements in kwargs_keys and kwargs_values.";
  }
  for (int64_t i = 0; i < static_cast<int64_t>(doc->kwargs_keys.size()); i++) {
    if (is_first) {
      is_first = false;
    } else {
      output_ << ", ";
    }
    const String& keyword = doc->kwargs_keys[i];
    output_ << keyword;
    output_ << "=";
    PrintDoc(doc->kwargs_values[i]);
  }
  output_ << ")";
}

inline void PythonDocPrinter::PrintTypedDoc(const LambdaAST& doc) {
  output_ << "lambda ";
  PrintJoinedDocs(doc->args, ", ");
  output_ << ": ";
  PrintChildExpr(doc->body,
                 ExprAST(GetObjectPtr<ExprASTObj>(const_cast<LambdaASTObj*>(doc.get()))));
}

inline void PythonDocPrinter::PrintTypedDoc(const ListAST& doc) {
  output_ << "[";
  PrintJoinedDocs(doc->values, ", ");
  output_ << "]";
}

inline void PythonDocPrinter::PrintTypedDoc(const TupleAST& doc) {
  output_ << "(";
  if (doc->values.size() == 1) {
    PrintDoc(doc->values[0]);
    output_ << ",";
  } else {
    PrintJoinedDocs(doc->values, ", ");
  }
  output_ << ")";
}

inline void PythonDocPrinter::PrintTypedDoc(const DictAST& doc) {
  if (doc->keys.size() != doc->values.size()) {
    TVM_FFI_THROW(ValueError) << "DictDoc should have equal number of elements in keys and values.";
  }
  output_ << "{";
  int64_t idx = 0;
  for (ExprAST key : doc->keys) {
    if (idx > 0) {
      output_ << ", ";
    }
    PrintDoc(key);
    output_ << ": ";
    PrintDoc(doc->values[idx]);
    idx++;
  }
  output_ << "}";
}

inline void PythonDocPrinter::PrintTypedDoc(const SliceAST& doc) {
  if (doc->start.has_value()) {
    PrintDoc(doc->start.value());
  }
  output_ << ":";
  if (doc->stop.has_value()) {
    PrintDoc(doc->stop.value());
  }
  if (doc->step.has_value()) {
    output_ << ":";
    PrintDoc(doc->step.value());
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const StmtBlockAST& doc) {
  bool is_first = true;
  for (StmtAST stmt : doc->stmts) {
    if (is_first) {
      is_first = false;
    } else {
      NewLine();
    }
    PrintDoc(stmt);
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const AssignAST& doc) {
  bool lhs_empty = false;
  if (const auto* tuple_doc = doc->lhs.get()->IsInstance<TupleASTObj>()
                                  ? static_cast<const TupleASTObj*>(doc->lhs.get())
                                  : nullptr) {
    if (tuple_doc->values.size() == 0) {
      lhs_empty = true;
      if (doc->annotation.has_value()) {
        TVM_FFI_THROW(ValueError)
            << "ValueError: `Assign.annotation` should be None when `Assign.lhs` is empty, "
               "but got: "
            << doc->annotation.value().get()->GetTypeKey();
      }
    } else {
      PrintJoinedDocs(tuple_doc->values, ", ");
    }
  } else {
    PrintDoc(doc->lhs);
  }

  if (doc->annotation.has_value()) {
    output_ << ": ";
    PrintDoc(doc->annotation.value());
  }
  if (doc->rhs.has_value()) {
    if (!lhs_empty) {
      output_ << " = ";
    }
    if (const auto* tuple_doc = doc->rhs.value().get()->IsInstance<TupleASTObj>()
                                    ? static_cast<const TupleASTObj*>(doc->rhs.value().get())
                                    : nullptr) {
      if (tuple_doc->values.size() > 1) {
        PrintJoinedDocs(tuple_doc->values, ", ");
      } else {
        PrintDoc(doc->rhs.value());
      }
    } else {
      PrintDoc(doc->rhs.value());
    }
  }
  MaybePrintCommentInline(doc);
}

inline void PythonDocPrinter::PrintTypedDoc(const IfAST& doc) {
  MaybePrintCommentMultiLines(doc, true);
  output_ << "if ";
  PrintDoc(doc->cond);
  output_ << ":";
  PrintIndentedBlock(doc->then_branch);
  if (!doc->else_branch.empty()) {
    NewLine();
    output_ << "else:";
    PrintIndentedBlock(doc->else_branch);
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const WhileAST& doc) {
  MaybePrintCommentMultiLines(doc, true);
  output_ << "while ";
  PrintDoc(doc->cond);
  output_ << ":";
  PrintIndentedBlock(doc->body);
}

inline void PythonDocPrinter::PrintTypedDoc(const ForAST& doc) {
  MaybePrintCommentMultiLines(doc, true);
  output_ << "for ";
  if (const auto* tuple = doc->lhs.get()->IsInstance<TupleASTObj>()
                              ? static_cast<const TupleASTObj*>(doc->lhs.get())
                              : nullptr) {
    if (tuple->values.size() == 1) {
      PrintDoc(tuple->values[0]);
      output_ << ",";
    } else {
      PrintJoinedDocs(tuple->values, ", ");
    }
  } else {
    PrintDoc(doc->lhs);
  }
  output_ << " in ";
  PrintDoc(doc->rhs);
  output_ << ":";
  PrintIndentedBlock(doc->body);
}

inline void PythonDocPrinter::PrintTypedDoc(const WithAST& doc) {
  MaybePrintCommentMultiLines(doc, true);
  output_ << "with ";
  PrintDoc(doc->rhs);
  if (doc->lhs.has_value()) {
    output_ << " as ";
    PrintDoc(doc->lhs.value());
  }
  output_ << ":";
  PrintIndentedBlock(doc->body);
}

inline void PythonDocPrinter::PrintTypedDoc(const ExprStmtAST& doc) {
  PrintDoc(doc->expr);
  MaybePrintCommentInline(doc);
}

inline void PythonDocPrinter::PrintTypedDoc(const AssertAST& doc) {
  output_ << "assert ";
  PrintDoc(doc->cond);
  if (doc->msg.has_value()) {
    output_ << ", ";
    PrintDoc(doc->msg.value());
  }
  MaybePrintCommentInline(doc);
}

inline void PythonDocPrinter::PrintTypedDoc(const ReturnAST& doc) {
  output_ << "return";
  if (doc->value.has_value()) {
    output_ << " ";
    PrintDoc(doc->value.value());
  }
  MaybePrintCommentInline(doc);
}

inline void PythonDocPrinter::PrintTypedDoc(const FunctionAST& doc) {
  PrintDecorators(doc->decorators);
  output_ << "def ";
  PrintDoc(doc->name);
  output_ << "(";
  PrintJoinedDocs(doc->args, ", ");
  output_ << ")";
  if (doc->return_type.has_value()) {
    output_ << " -> ";
    PrintDoc(doc->return_type.value());
  }
  output_ << ":";
  if (doc->comment.has_value()) {
    PrintBlockComment(doc->comment.value());
  }
  PrintIndentedBlock(doc->body);
  NewLineWithoutIndent();
}

inline void PythonDocPrinter::PrintTypedDoc(const ClassAST& doc) {
  PrintDecorators(doc->decorators);
  output_ << "class ";
  PrintDoc(doc->name);
  output_ << ":";
  if (doc->comment.has_value()) {
    PrintBlockComment(doc->comment.value());
  }
  PrintIndentedBlock(doc->body);
}

inline void PythonDocPrinter::PrintTypedDoc(const CommentAST& doc) {
  if (doc->comment.has_value()) {
    MaybePrintCommentMultiLines(doc, false);
  }
}

inline void PythonDocPrinter::PrintTypedDoc(const DocStringAST& doc) {
  if (doc->comment.has_value()) {
    String comment(doc->comment.value());
    if (!comment.empty()) {
      PrintDocString(comment);
    }
  }
}

}  // namespace
}  // namespace text
}  // namespace ffi
}  // namespace tvm

// ============================================================================
// Non-anonymous-namespace implementations (exported functions and methods)
// ============================================================================

namespace tvm {
namespace ffi {
namespace text {

// ============================================================================
// DocToPythonScript
// ============================================================================

String DocToPythonScript(NodeAST node, PrinterConfig cfg) {  // NOLINT(*-value-param)
  if (cfg->num_context_lines < 0) {
    constexpr int32_t kMaxInt32 = 2147483647;
    cfg->num_context_lines = kMaxInt32;
  }
  PythonDocPrinter printer(cfg);
  printer.Append(node, cfg);
  String result = printer.GetString();
  // Trim trailing whitespace
  std::string result_str(result.data(), result.size());
  while (!result_str.empty() && std::isspace(static_cast<unsigned char>(result_str.back()))) {
    result_str.pop_back();
  }
  return String(result_str);
}

// ============================================================================
// NodeASTObj::ToPython
// ============================================================================

String NodeASTObj::ToPython(const PrinterConfig& cfg) const {
  return DocToPythonScript(GetRef<NodeAST>(this), cfg);
}

// ============================================================================
// IRPrintDispatch — look up __ir_print__ type attribute and call it
// ============================================================================

NodeAST IRPrintDispatch(AnyView obj, AnyView printer, AnyView path) {
  static reflection::TypeAttrColumn ir_print_column("__ir_print__");
  int32_t type_index = obj.type_index();
  AnyView func_view = ir_print_column[type_index];
  if (func_view.type_index() == TypeIndex::kTVMFFINone) {
    TVM_FFI_THROW(ValueError) << "No __ir_print__ registered for type index " << type_index;
  }
  Function func = func_view.cast<Function>();
  Any ret;
  AnyView args[3] = {obj, printer, path};
  func.CallPacked(args, 3, &ret);
  return ret.cast<NodeAST>();
}

// ============================================================================
// ToPython — convert any object to Python source code string
// ============================================================================

String ToPython(ObjectRef obj, PrinterConfig cfg) {  // NOLINT(*-value-param)
  IRPrinter printer(cfg);
  DefaultFrame frame;
  printer->FramePush(frame);
  NodeAST ret = IRPrintDispatch(obj, printer, reflection::AccessPath::Root());
  printer->FramePop();
  if (frame->stmts.empty()) {
    return ret->ToPython(cfg);
  }
  if (ret.get()->IsInstance<StmtBlockASTObj>()) {
    const auto* block = static_cast<const StmtBlockASTObj*>(ret.get());
    frame->stmts.insert(frame->stmts.end(), block->stmts.begin(), block->stmts.end());
  } else if (ret.get()->IsInstance<ExprASTObj>()) {
    frame->stmts.push_back(ExprStmtAST(List<AccessPath>{}, Optional<String>{},
                                       GetRef<ExprAST>(static_cast<const ExprASTObj*>(ret.get()))));
  } else if (ret.get()->IsInstance<StmtASTObj>()) {
    frame->stmts.push_back(GetRef<StmtAST>(static_cast<const StmtASTObj*>(ret.get())));
  } else {
    TVM_FFI_THROW(ValueError) << "Unsupported type: " << ret.get()->GetTypeKey();
  }
  NodeAST block_node = StmtBlockAST(List<AccessPath>{}, Optional<String>{}, frame->stmts);
  return block_node->ToPython(cfg);
}

}  // namespace text
}  // namespace ffi
}  // namespace tvm

// ============================================================================
// Registration block
// ============================================================================

namespace {

TVM_FFI_STATIC_INIT_BLOCK() {
  namespace refl = ::tvm::ffi::reflection;
  namespace text = ::tvm::ffi::text;
  // Ensure __ir_print__ type attribute column exists
  refl::EnsureTypeAttrColumn("__ir_print__");
  // Register global functions
  refl::GlobalDef()
      .def("ffi.text.DocToPythonScript", text::DocToPythonScript)
      .def("ffi.text.ToPython", text::ToPython)
      .def("ffi.text.IRPrintDispatch", text::IRPrintDispatch);
  // PrinterConfig
  refl::ObjectDef<text::PrinterConfigObj>()
      .def_rw("def_free_var", &text::PrinterConfigObj::def_free_var)
      .def_rw("indent_spaces", &text::PrinterConfigObj::indent_spaces)
      .def_rw("print_line_numbers", &text::PrinterConfigObj::print_line_numbers)
      .def_rw("num_context_lines", &text::PrinterConfigObj::num_context_lines)
      .def_rw("print_addr_on_dup_var", &text::PrinterConfigObj::print_addr_on_dup_var)
      .def_rw("path_to_underline", &text::PrinterConfigObj::path_to_underline)
      .def(refl::init<bool, int32_t, int8_t, int32_t, bool, ::tvm::ffi::List<text::AccessPath>>());
  // NodeAST
  refl::ObjectDef<text::NodeASTObj>(refl::init(false))
      .def_ro("source_paths", &text::NodeASTObj::source_paths)
      .def("to_python", &text::NodeASTObj::ToPython);
  // ExprAST
  refl::ObjectDef<text::ExprASTObj>(refl::init(false))
      .def_ro("source_paths", &text::ExprASTObj::source_paths);
  // StmtAST
  refl::ObjectDef<text::StmtASTObj>(refl::init(false))
      .def_ro("source_paths", &text::StmtASTObj::source_paths)
      .def_rw("comment", &text::StmtASTObj::comment);
  // StmtBlockText
  refl::ObjectDef<text::StmtBlockASTObj>()
      .def_ro("stmts", &text::StmtBlockASTObj::stmts)
      .def(refl::init<::tvm::ffi::List<text::StmtAST>>());
  // LiteralAST
  refl::ObjectDef<text::LiteralASTObj>()
      .def_ro("value", &text::LiteralASTObj::value)
      .def(refl::init<::tvm::ffi::Any>());
  // IdAST
  refl::ObjectDef<text::IdASTObj>()
      .def_ro("name", &text::IdASTObj::name)
      .def(refl::init<::tvm::ffi::String>());
  // AttrAST
  refl::ObjectDef<text::AttrASTObj>()
      .def_ro("obj", &text::AttrASTObj::obj)
      .def_ro("name", &text::AttrASTObj::name)
      .def(refl::init<text::ExprAST, ::tvm::ffi::String>());
  // IndexAST
  refl::ObjectDef<text::IndexASTObj>()
      .def_ro("obj", &text::IndexASTObj::obj)
      .def_ro("idx", &text::IndexASTObj::idx)
      .def(refl::init<text::ExprAST, ::tvm::ffi::List<text::ExprAST>>());
  // CallAST
  refl::ObjectDef<text::CallASTObj>()
      .def_ro("callee", &text::CallASTObj::callee)
      .def_ro("args", &text::CallASTObj::args)
      .def_ro("kwargs_keys", &text::CallASTObj::kwargs_keys)
      .def_ro("kwargs_values", &text::CallASTObj::kwargs_values)
      .def(refl::init<text::ExprAST, ::tvm::ffi::List<text::ExprAST>,
                      ::tvm::ffi::List<::tvm::ffi::String>, ::tvm::ffi::List<text::ExprAST>>());
  // OperationText
  refl::ObjectDef<text::OperationASTObj>()
      .def_ro("op", &text::OperationASTObj::op)
      .def_ro("operands", &text::OperationASTObj::operands)
      .def(refl::init<int64_t, ::tvm::ffi::List<text::ExprAST>>());
  // LambdaText
  refl::ObjectDef<text::LambdaASTObj>()
      .def_ro("args", &text::LambdaASTObj::args)
      .def_ro("body", &text::LambdaASTObj::body)
      .def(refl::init<::tvm::ffi::List<text::IdAST>, text::ExprAST>());
  // TupleText
  refl::ObjectDef<text::TupleASTObj>()
      .def_ro("values", &text::TupleASTObj::values)
      .def(refl::init<::tvm::ffi::List<text::ExprAST>>());
  // ListText
  refl::ObjectDef<text::ListASTObj>()
      .def_ro("values", &text::ListASTObj::values)
      .def(refl::init<::tvm::ffi::List<text::ExprAST>>());
  // DictText
  refl::ObjectDef<text::DictASTObj>()
      .def_ro("keys", &text::DictASTObj::keys)
      .def_ro("values", &text::DictASTObj::values)
      .def(refl::init<::tvm::ffi::List<text::ExprAST>, ::tvm::ffi::List<text::ExprAST>>());
  // SliceText
  refl::ObjectDef<text::SliceASTObj>()
      .def_ro("start", &text::SliceASTObj::start)
      .def_ro("stop", &text::SliceASTObj::stop)
      .def_ro("step", &text::SliceASTObj::step)
      .def(refl::init<::tvm::ffi::Optional<text::ExprAST>, ::tvm::ffi::Optional<text::ExprAST>,
                      ::tvm::ffi::Optional<text::ExprAST>>());
  // AssignText
  refl::ObjectDef<text::AssignASTObj>()
      .def_ro("lhs", &text::AssignASTObj::lhs)
      .def_ro("rhs", &text::AssignASTObj::rhs)
      .def_ro("annotation", &text::AssignASTObj::annotation)
      .def(refl::init<text::ExprAST, ::tvm::ffi::Optional<text::ExprAST>,
                      ::tvm::ffi::Optional<text::ExprAST>>());
  // IfText
  refl::ObjectDef<text::IfASTObj>()
      .def_ro("cond", &text::IfASTObj::cond)
      .def_ro("then_branch", &text::IfASTObj::then_branch)
      .def_ro("else_branch", &text::IfASTObj::else_branch)
      .def(refl::init<text::ExprAST, ::tvm::ffi::List<text::StmtAST>,
                      ::tvm::ffi::List<text::StmtAST>>());
  // WhileText
  refl::ObjectDef<text::WhileASTObj>()
      .def_ro("cond", &text::WhileASTObj::cond)
      .def_ro("body", &text::WhileASTObj::body)
      .def(refl::init<text::ExprAST, ::tvm::ffi::List<text::StmtAST>>());
  // ForText
  refl::ObjectDef<text::ForASTObj>()
      .def_ro("lhs", &text::ForASTObj::lhs)
      .def_ro("rhs", &text::ForASTObj::rhs)
      .def_ro("body", &text::ForASTObj::body)
      .def(refl::init<text::ExprAST, text::ExprAST, ::tvm::ffi::List<text::StmtAST>>());
  // WithText
  refl::ObjectDef<text::WithASTObj>()
      .def_ro("lhs", &text::WithASTObj::lhs)
      .def_ro("rhs", &text::WithASTObj::rhs)
      .def_ro("body", &text::WithASTObj::body)
      .def(refl::init<::tvm::ffi::Optional<text::ExprAST>, text::ExprAST,
                      ::tvm::ffi::List<text::StmtAST>>());
  // ExprStmtAST
  refl::ObjectDef<text::ExprStmtASTObj>()
      .def_ro("expr", &text::ExprStmtASTObj::expr)
      .def(refl::init<text::ExprAST>());
  // AssertText
  refl::ObjectDef<text::AssertASTObj>()
      .def_ro("cond", &text::AssertASTObj::cond)
      .def_ro("msg", &text::AssertASTObj::msg)
      .def(refl::init<text::ExprAST, ::tvm::ffi::Optional<text::ExprAST>>());
  // ReturnText
  refl::ObjectDef<text::ReturnASTObj>()
      .def_ro("value", &text::ReturnASTObj::value)
      .def(refl::init<::tvm::ffi::Optional<text::ExprAST>>());
  // FunctionText
  refl::ObjectDef<text::FunctionASTObj>()
      .def_ro("name", &text::FunctionASTObj::name)
      .def_ro("args", &text::FunctionASTObj::args)
      .def_ro("decorators", &text::FunctionASTObj::decorators)
      .def_ro("return_type", &text::FunctionASTObj::return_type)
      .def_ro("body", &text::FunctionASTObj::body)
      .def(refl::init<text::IdAST, ::tvm::ffi::List<text::AssignAST>,
                      ::tvm::ffi::List<text::ExprAST>, ::tvm::ffi::Optional<text::ExprAST>,
                      ::tvm::ffi::List<text::StmtAST>>());
  // ClassText
  refl::ObjectDef<text::ClassASTObj>()
      .def_ro("name", &text::ClassASTObj::name)
      .def_ro("decorators", &text::ClassASTObj::decorators)
      .def_ro("body", &text::ClassASTObj::body)
      .def(refl::init<text::IdAST, ::tvm::ffi::List<text::ExprAST>,
                      ::tvm::ffi::List<text::StmtAST>>());
  // CommentText
  refl::ObjectDef<text::CommentASTObj>().def(
      refl::init<::tvm::ffi::Optional<::tvm::ffi::String>>());
  // DocStringText
  refl::ObjectDef<text::DocStringASTObj>().def(
      refl::init<::tvm::ffi::Optional<::tvm::ffi::String>>());
  // DefaultFrame
  refl::ObjectDef<text::DefaultFrameObj>()
      .def_rw("stmts", &text::DefaultFrameObj::stmts)
      .def(refl::init<::tvm::ffi::List<text::StmtAST>>());
  // VarInfo
  refl::ObjectDef<text::VarInfoObj>()
      .def_ro("name", &text::VarInfoObj::name)
      .def_ro("creator", &text::VarInfoObj::creator)
      .def(refl::init<::tvm::ffi::Optional<::tvm::ffi::String>, ::tvm::ffi::Function>());
  // IRPrinter
  refl::ObjectDef<text::IRPrinterObj>()
      .def_rw("cfg", &text::IRPrinterObj::cfg)
      .def_rw("obj2info", &text::IRPrinterObj::obj2info)
      .def_rw("defined_names", &text::IRPrinterObj::defined_names)
      .def_rw("frames", &text::IRPrinterObj::frames)
      .def_rw("frame_vars", &text::IRPrinterObj::frame_vars)
      .def(refl::init<text::PrinterConfig, ::tvm::ffi::Dict<::tvm::ffi::Any, text::VarInfo>,
                      ::tvm::ffi::Dict<::tvm::ffi::String, int64_t>,
                      ::tvm::ffi::List<::tvm::ffi::Any>,
                      ::tvm::ffi::Dict<::tvm::ffi::Any, ::tvm::ffi::Any>>())
      .def("var_is_defined", &text::IRPrinterObj::VarIsDefined)
      .def("var_def", &text::IRPrinterObj::VarDef)
      .def("var_def_no_name", &text::IRPrinterObj::VarDefNoName)
      .def("var_remove", &text::IRPrinterObj::VarRemove)
      .def("var_get", &text::IRPrinterObj::VarGet)
      .def("frame_push", &text::IRPrinterObj::FramePush)
      .def("frame_pop", &text::IRPrinterObj::FramePop)
      .def("__call__", &text::IRPrinterObj::operator());
}

}  // namespace
