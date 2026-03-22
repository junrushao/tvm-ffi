# Skill /commit-ledger - Self-Evolution
- **Procedure friction**: Step 3.4 (cross-layer consistency) guidance is appropriate here; the commit is inherently cross-layer. No friction.
- **Template gap**: The `FuncFunctorImpl::TypeSchema()` JSON format encodes the return type as `args[0]` (before the parameter types), which is unintuitive. The template has no guidance on documenting unusual wire-format orderings for schema types — a brief "Wire format note" annotation slot in Key Exports would help capture this.
- **Wasted effort**: None — shape was correctly classified as `standard` given the multi-layer scope.
- **Suggested skill change**: None — skill fit well.
