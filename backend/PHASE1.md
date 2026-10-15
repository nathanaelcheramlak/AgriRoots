# Extension-office workflow

Phase 1 adds manual, sourced advice. Autonomous drafting and MCP are Phase 2.

## Start and provision

Use the existing backend environment and `.env`. From `backend/`:

```bash
python -m src.db.schema_migrations
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Migrations also run at startup. Before running multiple production workers, run the migration command once as a deployment step. Back up the database before upgrading. Revision 1 adopts existing tables and adds missing chat storage columns; revision 2 creates the workspace tables. Existing user, profile, OTP and chat data is preserved. Applied revisions are recorded in `schema_revisions`; add a new revision for later schema changes. SQLite and PostgreSQL use the same SQLAlchemy migration operations; the automated migration checks currently execute on SQLite.

1. Register the first administrator through the existing phone OTP/password flow.
2. Obtain that account's UUID from authenticated `GET /api/auth/me` or `/api/workspace/me`.
3. A trusted operator with database access runs:

   ```bash
   python -m src.cli.provision_admin --user-id ACCOUNT_UUID
   ```

   This local-only command refuses a second bootstrap and records the administrator identity. There is no public bootstrap API or profile-based role assignment.
4. Open `/workspace`, create an office, and enroll registered account UUIDs as officers or farmers. An office administrator can enroll accounts in their office. The provisioned administrator can create offices and delegate their administration. Each account belongs to one office; cross-office reassignment and role changes require a future audited migration workflow.
5. Create a cluster, household linked to an enrolled farmer, plot, season records, local guidance/calendar and evidence. Sources are immutable; corrections use new source records.
6. Draft an advisory with target households/plots and specific evidence for each recommendation. Save, submit, inspect the full version, approve, then separately release. Approval alone does not publish. Rejection/cancellation require a reason. Editing any advisory creates a fresh draft version; old content and events remain intact. The same authorized officer may draft and review in Phase 1; a separate reviewer is not required by this phase.
7. Log in as the linked farmer and open `/advisories`. Only explicitly released versions addressed to that account are available. Audio uses the stored released text or an included, reviewed translation. Configure the existing Google/Hasab credentials for actual speech playback.

Farmer ownership and plot ownership are immutable. Profile `user_type` remains onboarding information and never grants privileges. Accounts with workspace history cannot use self-service deletion, and the debug reset refuses to erase workspace audit history.

## Synthetic demonstration

Point `DATABASE_URL` to a new, local database, then run:

```bash
python -m src.cli.seed_synthetic
```

The command refuses any database containing users. It creates labelled synthetic records and local demonstration accounts:

| Account | Phone | Password |
| --- | --- | --- |
| Administrator | +251900000001 | SyntheticDemo123! |
| Officer | +251900000002 | SyntheticDemo123! |
| Farmer | +251900000003 | SyntheticDemo123! |

Log in through the normal password login. The seed contains a cluster, household, plot, crop season and synthetic weather evidence. Manually draft and release an example through `/workspace`. These are public demo credentials for an empty local database only. All seed household names and evidence are explicitly synthetic; no personal records or database files are committed. Synthetic evidence cannot target an unlabelled household.

## Delivery route inventory and boundary

| Existing path / service | Phase 1 behavior |
| --- | --- |
| `/api/chat/sessions/.../messages`, `ChatService` | Deterministic general education for the exact prompts `What is crop rotation?`, `What is compost?`, `What is agroclimate?` and their displayed Amharic equivalents. Other prompts and image/audio requests receive a review referral. Enrolled farmers' requests are saved to their office queue, without advice generation. Images are validated but not retained; officers contact the farmer to inspect them. Voice transcripts can be queued. |
| Existing chat history | Previously unreviewed assistant responses are redacted when read; original database content is retained. |
| `/api/recommendations/{crops,fertilizer,weather}`, `RecommendationService` | Authenticated HTTP 409 directing the user to the review workflow, before generating advice. |
| `/api/crop-health/diagnose`, `DiagnosisService` | Authenticated HTTP 409. Manual evidence and review are required. |
| `/api/alerts`, `/api/alerts/weather/generate`, read/delete routes, `AlertAppService` | Authenticated HTTP 409, including historic unreviewed alert content. |
| `/api/voice/synthesize`, `VoiceService` | Arbitrary text synthesis returns authenticated HTTP 409. |
| `/api/voice/transcribe`, chat audio input | Transcription remains available; it does not generate advice. |
| `/api/workspace/released/{version_id}/audio` | Recipient authorization plus released-version check. Text and language come only from reviewed content; no translation call occurs. |
| OTP / password reset / phone change SMS | Existing authentication-only delivery remains intact. No agricultural SMS/USSD publication tools are added. |

The old recommendation/diagnosis implementations remain in the codebase for future officer drafting integration, but their HTTP delivery routes are gated. Chat no longer invokes the advisory agent. General education is deliberately a small catalogue so a prompt classifier or model cannot bypass approval. The Phase 2 agent must only create drafts; it must not call approval/release routes with officer credentials.

## Storage and concurrency

Office-scoped records use a typed schema registry and JSON payloads, with immutable evidence snapshots in each advisory version. Membership, linked farmer account uniqueness, version uniqueness and audit actor references are enforced in the database. Editable records use revision checks. Advisory changes acquire a database compare-and-swap claim before mutation. Lifecycle status and its event commit together; competing release requests re-read the committed version and return the same publication. Released versions remain available when a newer draft is created. Replacements link to a prior released advisory while retaining both histories.

Audit events include actor, entity, exact version, timestamp, reason and record before/after values where applicable. The UI shows review queues, source snapshots and audit histories. Farmers receive a reduced released-version projection without office membership or recipient account lists.

## Checks

```bash
cd backend
python -m pytest -q
cd ../frontend
npm run lint
npm run build
```

Tests cover OTP/onboarding regressions, office and household isolation, profile-based privilege escalation attempts, record validation and ownership, evidence requirements, review transitions, immutable history, exact released audio (provider mocked), replacements, concurrent publication and fresh/legacy schema migrations. External speech providers and real extension-office feedback have not been validated by these local checks.

Validation on 15 October 2026: all 28 backend tests passed with the repository-pinned FastAPI 0.136.0, SQLAlchemy 2.0.49, Pydantic 2.13.3 and pytest 9.0.3. Frontend lint and production build passed. The build reports a main-bundle size warning; speech providers were mocked, migrations were exercised on SQLite, and browser end-to-end testing was not performed.
