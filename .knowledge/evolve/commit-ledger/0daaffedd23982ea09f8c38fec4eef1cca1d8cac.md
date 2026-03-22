# Skill /commit-ledger - Self-Evolution
- **Procedure friction**: Step 0.3 checkout is blocked by sandbox restrictions on `.git/worktrees/*/index.lock` creation. The workaround (using `git show` from REPO_MAIN) works, but the procedure could acknowledge this as a fallback path.
- **Template gap**: None — the template covered this standard feature commit well.
- **Wasted effort**: None for this commit shape.
- **Suggested skill change**: In Step 0.3, add a note: "If `git checkout` fails due to index.lock permissions (sandbox mode), fall back to `git show <COMMIT>:<path>` and `git show --format="" <COMMIT>` for all diff access — the analysis is not impaired."
