# Workspace structure after frontend retirement

Current canonical application code is now in one AgriRoots repository following the user-requested [consolidation](REPOSITORY_CONSOLIDATION.md). The workspace parent still holds the standalone provider evaluation and a backup of the old separate frontend checkout.

| Directory | Responsibility |
| --- | --- |
| `agrilo-fieldops-frontend/` | The only active frontend: application/map in `src`, contracts in `docs`, unit tests in `tests`, browser tests in `e2e` |
| `backend/` | API, database migrations, approved tool registry/executor, LangGraph workers, provider adapters and tests |
| `docs/` | Backend architecture, policies, integration audit and setup |
| `scripts/` | Backend evaluations and artifact checks |
| `scripts/legacy/` | Disabled historical scripts for the removed UI |
| `../f-test/` | Standalone provider experiments; not runtime authority or application storage |

On 2026-11-17, the 107 tracked files in the clean `frontend/` subtree were removed with Git-aware deletion after checking for modified, untracked, ignored and linked files. No local frontend material needed preservation outside Git. The old Android wrapper is included in this retirement; native/mobile packaging, farmer released-advice screens and administration screens are not all implemented in the newer UI. Their backend endpoints remain.

No backend source directories, environments, databases, private-data directories or repository `.git` folders were moved or deleted. Phase 1 changes in both repositories were retained. New layout files in the workspace parent (`README.md`, `AgriLo.code-workspace`) are local conveniences outside application Git history.

Backend CI now checks backend evaluations and artifacts without the removed frontend/cold-start browser workflow. The root CI workflow checks the current frontend from its repository folder. The disposable Home/Plugins/Skills runner is an explicit local check described in [testing](testing.md), now requiring only this application checkout.

Recover historical source without affecting current work using a separate checkout/worktree at a revision that still contains `frontend/` (for example the pre-retirement `main` commit). Restore old scripts and frontend from the same revision. No history was rewritten and no new commit/push is made by this cleanup.

## Cleanup verification (2026-11-17)

- Old frontend directory absent; all 107 removed files were tracked and unchanged before deletion. Git-aware removal staged those deletions; no commit was created.
- Frontend `npm run check`: typecheck, lint, 97 unit tests and production build passed after removal.
- `backend/scripts/check_home_browser.py`: all four actual backend-connected fixture browser tests passed after removal. No cloud model/provider call was made.
- Archived Python and browser entry points exit with an explicit retirement message before setup/seeding/browser activity, including without the old browser dependency installation.
- Both workflow files parse as YAML; GitHub-hosted workflow execution has not been performed locally.
- All three editor workspace folders and the local links in nine active setup/layout documents resolve. Changed text files validate as UTF-8.

The cleanup preserves Phase 1's live-model/account blockers. It does not implement replacement administration, farmer-release or Android screens, nor advance Plugins/Monitoring/Outreach integration.
