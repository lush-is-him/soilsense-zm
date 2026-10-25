# Prompt: audit the existing SoilSense ZM code against the new spec

How to use:
1. Copy `SOILSENSE_SPEC.md` into the repo as `docs/SOILSENSE_SPEC.md` and commit it.
2. Open the repo in Antigravity (the same prompt works in Claude Code).
3. Paste everything below the line.
4. Read the `docs/MIGRATION_PLAN.md` it produces before telling it to change any code.

---

You are working in the SoilSense ZM repository. The target design is in `docs/SOILSENSE_SPEC.md`. Read all of it first, especially section 0 (rules for agents), section 2 (architecture), section 3 (data model), section 6 (rule data) and section 8 (build plan).

Context: this project already has code, written before the design changed. The design changed twice: machine learning was removed, and a "map agreement" design was introduced (probe pH is checked against the iSDAsoil map, which sets a trust level). I need you to find out what in the existing code still works with the new design, what needs adapting, and what should go.

## Phase 1: read-only audit

**Do not modify, move or delete any file in this phase.** The only file you may create is `docs/MIGRATION_PLAN.md`.

If this is a git repository and the working tree is clean, note the current commit hash in the plan. If the working tree is not clean, say so in the plan and stop after writing it.

### 1. Inventory

Report: languages, frameworks and versions, database and how it is created, how to run the backend, dashboard and tests, dependency files, folder structure (two levels), and where the Arduino firmware and serial bridge live (if anywhere).

Secret check: list any file that appears to contain an API key, token, password or phone number (Africa's Talking, database, etc.). **List file paths only. Never print the values.**

### 2. Component verdicts

For every component in the table below, find the existing implementation (or say there is none) and give one verdict:

- **KEEP**: matches the spec, no change needed
- **ADAPT**: right idea, needs specific changes (say which)
- **REPLACE**: rewrite, reuse nothing
- **DELETE**: obsolete (for example ML)
- **MISSING**: nothing exists yet

| Component | Spec section |
|---|---|
| ML code, models, training scripts, sensor-only soil classifier | 0 (rule 6), 2 |
| Database schema and migrations | 3 |
| Users, roles, login, password hashing | 3, 5 (FR1, NFR6) |
| Farmer and field registration, GPS handling (30 m rule, manual pin) | 2.2, 3 |
| Arduino firmware | 2.3, 8.3 track B |
| Serial bridge | 2, 4 |
| Probe calibration (pH 4.00 and 7.00 buffers, slope 95 to 105%) | 2.3 |
| Reading quality check | 2.3 |
| Map service (iSDAsoil local layers) | 2.4 |
| Trust checker | 2.4, 2.5 |
| Rule engine, and where agronomy values live | 6 |
| Translation and i18n (en, ny, toi, unreviewed flag) | 3, 2.1 |
| Household measures | 6.8 |
| SMS delivery (Africa's Talking) | 2.1, NFR5 |
| Web dashboard: pages, mobile layout, low-bandwidth behaviour | 4, 8.3 track C |
| Automated tests | 10 |
| Configuration and environment handling | 0 (rule 7) |
| Analysis scripts (for example `extract_kafue.py`, SoilGrids extraction, chart scripts) | Not part of the product |

Give the verdicts in one table with these columns:
`Component | Path(s) | Verdict | What matches the spec | What does not | Effort (S/M/L) | Track and sprint`

### 3. Specific checks (report each one, even if the answer is "none found")

1. Any remaining ML or model code, files, saved models or dependencies, and what depends on them.
2. Any **agronomy values hard-coded in code** (pH thresholds, lime rates, crop lists, fertiliser amounts, plan text). Quote file and line numbers, not the values' meaning. These violate rule 3 of the spec and must move to `rules/*.yaml`.
3. Whether the database schema can hold the spec's tables, and which columns or tables are missing or differ. Say whether there is existing data worth migrating (readings, fields, farmers) and how much.
4. Whether pH values carry a method (water or CaCl2) anywhere.
5. How readings reach the backend today (serial, HTTP, manual entry) and the exact payload shape.
6. How SMS is sent: sandbox or production, where the key is read from, whether phone numbers are stored, and whether they can be deleted (NFR5).
7. Whether the dashboard already works on a phone (layout, size of JS bundle, any heavy dependencies) and which pages exist.
8. Whether any user-facing text exists in Nyanja or Tonga, and whether it is marked unreviewed.
9. Test coverage: what is tested, what is not, whether tests currently pass.
10. Anything in the code that gives advice from a reading that has not passed a quality check (spec NFR2 forbids this).

### 4. Reuse opportunities

List what is good enough to keep as-is or with small changes (for example the SMS integration, the dashboard layout, auth). Be specific about files.

### 5. Conflicts and questions

- **Conflicts**: places where the code and the spec disagree and it is not obvious which is right.
- **Spec problems**: anything in the spec that is ambiguous, contradictory or impossible given the code. Section 7 of the spec already lists known conflicts (C-1 to C-6); do not re-solve those, but say which ones block which code.
- **Questions for me**: at most 10, most important first, each answerable in one line.

### 6. Output

Write `docs/MIGRATION_PLAN.md` with these sections, in this order:

1. Summary (10 lines maximum: what can be kept, what must change, biggest risks)
2. Repo state (commit hash, clean or not)
3. Stack inventory
4. Component verdict table
5. Findings from the 10 specific checks
6. Reuse opportunities
7. Data migration notes
8. **Proposed Sprint 0 and Sprint 1 task list** (see below)
9. Risks
10. Conflicts and questions

For section 8, use the spec's tracks (A to H) and Sprint 1 tasks (S1-1 to S1-7). For each task give: the files it will touch, size (S/M/L), dependencies, and a status column (`todo`). Mark which tasks can run in parallel **because they touch different files**, and which must go in order. Propose which agent should take each task using the directory ownership in spec section 8.4, and flag any task where the existing code makes that split impractical.

Then **stop and wait for me**. Do not start Phase 2 until I reply.

## Phase 2: only after I approve the plan

Execute the Sprint 1 **Must** tasks only (S1-1 to S1-5), unless I say otherwise.

Rules while doing this:

- One branch per track. Small commits with clear messages.
- Write tests before the code for the quality checker, trust checker and rule engine.
- Never invent an agronomy value. Anything marked `OPEN` or `CONFLICT` in the spec stays a stub that returns "lab test recommended", with an `xfail` test that names the open item.
- Do not delete files outside the ones the approved plan lists. Move analysis scripts to `analysis/` rather than deleting them.
- After each task, update its status in `docs/MIGRATION_PLAN.md` and tell me what changed, what you tested, and what you were unsure about.
- If you need to change a shared contract (schema, API, YAML shape, i18n keys), edit `docs/SOILSENSE_SPEC.md` first and tell me, then change the code.
- Never print or commit secrets.
