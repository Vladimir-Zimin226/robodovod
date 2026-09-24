# Live C11–C26 remediation after the first economics run

Status: **investigated; implementation pending; C30 HOLD**. Evidence: the owner's
2026-09-24 deployment log and commercial-result transcript, plus the ignored
`backup/` diagnostic snapshot generated at 08:11 UTC. The archive is confidential
and must remain outside Git. Server `main` reached `6a92e3e` (`v0.5.9`), Compose
services were healthy, and both `/ready` URLs answered. This is service health,
not acceptance of calculations, visualization, or exports.

## Confirmed observations and causes

1. **Financial result is not trustworthy (P0).** The successful immutable
   `FULL_ANALYSIS` run contains six `COMPLETE` purchase/RaaS calculations; the
   base purchase shows NPV 4,857,446,580.85 RUB and 0.07-year simple payback,
   but procurement is `UNVERIFIED` and every recommendation is `ALTERNATIVE`.
   More importantly, C14 `RoleLabourResultV1.annual_deficit_cost` is already
   `deficit × annual_cost_per_person` (`backend/calculation/labour.py`), while C16
   multiplies it by `role.deficit` again in both baseline and scenario cashflows
   (`backend/calculation/economics/cashflow.py`). Deficit cost thus scales with
   **deficit squared**. This inflates C16 baseline/benefit and can inflate the
   displayed C16 NPV/payback. C18 ranking and sensitivity use an independently
   composed allocation cashflow, so their numbers require reconciliation rather
   than an assumption that the same defect propagated. Do not cite the current
   run as a validated
   business case. For the base scenario, 28 missing staff × 1,874,880 RUB
   direct cost/person/year is already 52,496,640 RUB in C14; C16 multiplies
   that by 28 again. Together with 25 staff direct+overhead, this exactly
   reproduces the displayed year-1 baseline of 1,525,705,920 RUB. A single
   deficit count would make that particular baseline component sum
   108,296,640 RUB before recalculating the other ledgers. Confirm the full
   downstream impact with an isolated replay and a simple
   hand-worked unit case before changing versioned calculation code. Do not
   mutate historical runs or silently overwrite old golden files.
2. **Evidence ZIP fails in the browser (P0).** The transcript says `Failed to
   execute 'fetch' on 'Window': Illegal invocation`. `EvidenceExportSession`
   stores bare `fetch` as `this.fetchImpl` and calls it with the session as the
   receiver. Browser `Window.fetch` rejects that receiver. Existing tests inject
   arrow-function mocks, so they miss the browser-specific failure. The
   diagnostic request log has no export GET during its capture window; do not
   mistake that for a server 404. Backend manifest/ZIP routes exist, but live
   download and digest verification remain unproven.
3. **RobCraft iframe is blocked by production headers (P0).** The frontend
   embeds `/robcraft/?embedded=1`; `infra/caddy/Caddyfile` applies
   `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` to every response.
   Those policies forbid this same-origin iframe. The saved ScenarioSpec parses
   and generates a RobCraft world locally, so the snapshot is not the observed
   cause. The archive does not contain Caddy/browser console logs; verify the
   response headers and browser console during the fix. Allow only the embedded
   `/robcraft/` document to be framed by the same origin while preserving
   anti-clickjacking protection for the rest of the app and the other CSP rules.
4. **2D is a synthetic animation, not a process map (P1).**
   `simulation2dModel.js` creates a triangle from a hash, draws one synthetic
   rectangle for the single active warehouse process, and moves all 15 robots
   around that triangle on a fixed 20-second visual loop. Coordinates and stages
   are not derived from C23 events, warehouse zones, measured geometry, or the
   120 m analytical route. The UI labels `SYNTHETIC`, but its present visual
   form does not explain the flow. Add an intelligible schematic with named
   origin/destination, operations, flow direction, fleet/queue/throughput, a
   legend, and explicit synthetic-versus-provided geometry provenance. Never
   imply the drawn path is the real facility or silently invent site geometry.
5. **C23 capacity verdict compares unlike quantities (P0/P1).** The live C23
   result reports demand 90.91 unit/h, expected *maximum effective fleet
   capacity* 137.65 unit/h, observed demand-limited throughput 90.5 unit/h,
   then flags 34.25% `DEVIATION`. `scheduling.py::_capacity_verdict` compares
   observed throughput directly with maximum capacity even when arrivals are
   below that capacity. This yields a misleading warning for an intentionally
   underloaded fleet. The 0.41 unit/h shortfall versus demand still needs a
   separate end-of-window/queue explanation. Specify and version separate
   demand-served and capacity-ceiling checks; test underload, saturation,
   overload, zero-demand and operating-window edges. Do not suppress genuine
   failures or claim SLA PASS: this run supplied no SLA or loading resources.
6. **A usable calculation report is not exposed (P1).** There is only an
   `evidence.zip` download button; `Report.pdf` lives inside that ZIP. The
   existing PDF is a raw snapshot/CSV dump using Courier/WinAnsi and ASCII
   `\u` escapes for Cyrillic, not a readable Russian management report. Build
   an explicit report download/view path from the immutable run, with key
   inputs, six scenarios, cashflow explanation, assumptions, C05/procurement
   status and source/digest links. Keep the evidence ZIP separately available.
7. **C23 report is not part of the immutable economics export (P1).** C23 jobs
   and reports are process-memory state, and the economics run snapshot contains
   no `simulation_report`. The current evidence builder therefore marks its
   `Simulation` section `NOT_AVAILABLE`; a server restart reruns C23. Define a
   separately versioned, owner-scoped, immutable simulation artifact bound to
   project/run/ScenarioSpec digest before promising downloadable C23 evidence.
   Preserve deterministic replay and historical snapshots.

The archive contains one successful C11, one earlier failed C11, and one
successful economics run. The successful C11 retained `NEEDS_VALIDATION` for
passport and availability. The economics POST returned 201 and C23 POST/GET
returned 202/200. The archive excludes frontend/Caddy logs, raw request bodies,
uploaded bytes and passwords; it cannot prove the browser render or export
response. User-entered purchase/RaaS terms, salaries, maintenance and battery
inclusions are **scenario assumptions**, not vendor facts. The current price
basis confirmation is not a verified offer, VAT determination or C05 PASS.

## Implementation order and gates for the next session

1. Re-check `main`, HEAD, status, applicable `AGENTS.md`, ignored `backup/`, and
   the latest attachments. Reproduce the financial defect from the stored run
   in a disposable environment; add unit/golden cases that expose single versus
   double deficit multiplication. Agree on a versioned correction path and
   migration/activation compatibility. Correct C16 and every downstream
   purchase/RaaS projection, re-run exact replay and six-scenario reconciliation.
   Label old runs with their original engine; do not rewrite them. If the
   corrected inputs still yield implausible economics, investigate further.
2. Fix `fetch` binding and add a browser-realistic test (native/browser fetch or
   a receiver-checking stub), plus API/persistence tests for manifest/ZIP,
   digest, tenant isolation and error paths. Verify an actual ZIP download,
   extraction and hash binding from a reopened economics run.
3. Scope the Caddy iframe policy to `/robcraft/` and test production response
   headers, browser console, static assets, CSP, READY→PREPARED→APPLIED
   handshake, report digest binding, reload and WebGL-unavailable fallback.
   Keep the rest of the site non-frameable.
4. Correct C23 comparison semantics with a versioned report/trace contract,
   explain observed-versus-required and headroom, and add deterministic
   underload/edge goldens. Persist a run-bound C23 artifact if it is to appear
   in evidence; test restart/reopen/replay and cross-tenant denial.
5. Design an honest 2D warehouse process schematic from known process/route
   inputs. Keep synthetic geometry unmistakable. Test event-to-visual bindings,
   multiple supported zones where data exist, keyboard/accessibility, responsive
   dark styling and no client-side KPI recalculation.
6. Add a readable, standalone Russian calculation report and retain the
   machine-auditable ZIP. Test PDF text extraction, numeric/source consistency,
   `NOT_AVAILABLE` sections, old-run compatibility and no unconfirmed claims.
7. Re-run backend unit/API/PostgreSQL/golden/security, frontend/browser build,
   C01→C05/C11→C13–C21→C23→2D/3D→reopen/copy/delete→both exports, including
   live HTTPS. Repeat C29/release acceptance after all changes. Inspect diff,
   commit separately, move only the tested commit to `main`, deploy only from
   `main`; no public readiness declaration while any P0 or live gate fails.

Existing [partial-input backlog](partial-economics-inputs-backlog.md) remains
separate: unknown commercial values must not become hidden zeroes or facts.
