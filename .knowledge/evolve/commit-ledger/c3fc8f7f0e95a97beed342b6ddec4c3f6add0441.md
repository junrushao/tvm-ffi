# Skill /commit-ledger - Self-Evolution
- **Procedure friction**: Step 0.3 (`git checkout`) consistently fails in sandbox due to index.lock permission. The workaround (reading via `git -C $REPO_MAIN show`) works, but the procedure should document it as the preferred fallback when lock creation fails.
- **Template gap**: None.
- **Wasted effort**: None.
- **Suggested skill change**: Add a note in Step 0.3: "If `git checkout` fails due to a lock permission error (sandbox), fall back to reading diff data with `git -C $REPO_MAIN show $COMMIT` — this avoids the lock entirely and provides all needed diff information."
