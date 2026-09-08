# DEFECT — the guided package never searched, and completed every game anyway

**Severity: submission blocker (§8.2.6/§8.2.8).** Caught by the check added in response to
`DEFECT_packaged_agent_searched_3_of_84_decisions.md`, on its first run against a different
package. Without that check this would have been uploaded.

## What happened

`submission_L_guided_search_v0` was built with a **hand-written list** of the `cg` modules the
guide needs. The list was missing `policy_data_v2`, which `cg/rl_policy.py` imports at module
scope. Inside the extracted package:

```
ImportError: cannot import name 'policy_data_v2' from 'cg'
```

`main.py` wraps the whole planning call in `except Exception: return base`. That fallback is
correct — a submitted agent must never crash — but it meant the guide's construction failure
was completely silent. The package imported, ran, and played 4/4 games to termination:

| | decisions | searched | search_step ok | changed action |
|---|---|---|---|---|
| before | 321 | **0** | 0 | 0 |
| after | 293 | 262 | 3,792 | 65 |

Every prior safety signal was green. It was the official baseline agent wearing a guided-search
label.

## Why the hand-list was the wrong shape

A hand-maintained dependency list is one forgotten import away from this outcome, and the
failure mode is invisible by construction. The packager now derives the transitive `cg.*` import
closure from the AST of the modules the guide actually needs.

One wrinkle worth recording: some repo files carry a UTF-8 BOM, and `ast.parse` on a plain
`utf-8` read raises `SyntaxError: invalid non-printable character U+FEFF`. The first version of
the closure walker swallowed that exception and returned a **silently truncated** closure — the
same class of bug one level up. Files are now opened with `utf-8-sig`.

## Generalisable lesson

A safe fallback and a working feature are indistinguishable from the outside unless something
counts the feature actually running. Two different packages hit this in one session, for two
unrelated reasons. The fallback was not the bug either time; the absence of a counter was.
