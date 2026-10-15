# Dependency and asset provenance

No repository-wide licence was present when Phase 3 began. On 15 October 2026 the project owner confirmed ownership or redistribution rights for the existing code, photographs and crop-model files and authorized Apache-2.0 for original code. That code is now covered by the root `LICENSE` and `NOTICE`. This is an owner confirmation, not an independent training-data or asset-chain audit. Third-party dependencies and materials retain their upstream terms; the code licence does not relicense third-party assets or their underlying datasets.

| Component | Provenance / terms | Treatment |
| --- | --- | --- |
| Qwen3-0.6B GGUF | [Official immutable model revision](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a), Apache-2.0 | Downloaded locally, checksum pinned; weights excluded from source artifacts. Preserve upstream licence/attribution if redistributing. |
| llama.cpp b11429 | [Official release](https://github.com/ggml-org/llama.cpp/releases/tag/b11429), MIT | Downloaded locally, checksum pinned; binary bundle includes its LICENSE; runtime excluded from source artifacts. |
| MCP Fetch 2026.10.10 | [MCP maintainers' source](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch), MIT | Exact package pin; installed dependency, not vendored source. |
| MCP Python SDK | [Official source](https://github.com/modelcontextprotocol/python-sdk), MIT | Exact package pin; installed dependency. |
| LangGraph | [Official source](https://github.com/langchain-ai/langgraph), MIT | Exact package pin; installed dependency. |
| Playwright | [Official source](https://github.com/microsoft/playwright), Apache-2.0 | Pinned browser development dependency. Chrome is operator-provided; not redistributed. |
| Local speech | [espeakng-loader 0.2.4](https://github.com/thewh1teagle/espeakng-loader), MIT loader; [eSpeak NG](https://github.com/espeak-ng/espeak-ng), GPL-3.0-or-later runtime/data | Installed pinned dependency used in an isolated synthesis subprocess. Binary/data are not vendored here. Retain upstream licences/source obligations if redistributing that runtime; the project's Apache licence does not relicense it. |
| PostgreSQL driver | [Psycopg 3](https://www.psycopg.org/), LGPL-3.0 driver with separately licensed bundled libraries | Exact driver/binary package versions in the lock; installed dependency, not vendored source. |
| NRCS soil-health extract | Source and extraction terms recorded in `backend/src/mcp/public_sources.py` | Short attributed source snapshot; general background, not a local Ethiopian agronomic endorsement. |
| Open-Meteo forecast | Attribution and retrieval metadata in each evidence record | Network service, not bundled weather data; operator must check service terms for deployment. |
| `backend/model/*.pt` | Existing checkpoints; owner confirms redistribution rights; detailed training-data provenance not supplied | Not loaded by the advisory demo. Preserve any upstream weight/data terms; the original-code licence does not extend to third-party inputs. |
| `frontend/public/img-4.jpg`, Android PNG artwork | Existing assets; owner confirms rights for the repository's included assets | Retain applicable upstream terms; the original-code grant does not relicense third-party artwork. |

Python direct and transitive versions are recorded in `backend/requirements-demo.lock`; JavaScript dependency integrity is recorded in the two npm lockfiles. Their upstream licences remain applicable. A lockfile pins versions, and is not a legal clearance or security audit. Secrets, databases, model caches, user uploads and private logs must remain excluded from published source packages.
