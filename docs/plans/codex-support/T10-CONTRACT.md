# T10 — Usage and budget contract

2026-09-22. Source CLI and real plan delivery; generated bundles refresh in T12/T17.

## Durable accounting

Each actual executor invocation has an atomic attempt record under
`.cld/runs/<run-id>/usage/attempt-<id>.json`. A durable reservation precedes dispatch;
completion precedes judging. Validation, failed calls, retries and model escalation all count.
Records retain model/provider/effort, retry feedback/reason, rung/source, timestamps, process
artifact paths, policy and allowance, normalized usage and raw provider usage fields. CLI
version identity is a content fingerprint from T09, not a guessed semantic version; direct
injected library executors without CLI identity report it unavailable.

The build owns the OS writer lock; its shared mutation lock serializes concurrent reservations,
completion publication and ledger writes. The ledger holds aggregate totals by model, slice and
validation plus active reservations. All attempts contribute, regardless of acceptance. Slice
`attempts`, token totals and cost are cumulative and survive retry, escalation and resume.
Individual journal files are the recovery source: resume scans them once, changes unfinished
reservations to interrupted/unknown outcomes, and rebuilds the ledger summary. Atomic completion
before a failed ledger save is counted once on resume. Corrupt journals block instead of resetting.
No recovery record is deleted. Accounting persistence errors block further admission.

Old builds only retained final-attempt usage. Their previous values are archived in a legacy
usage record, and historical totals stay unknown; they are not represented as complete history.
An attempt budget cannot rely on that incomplete history: use a new build. Token/cost limits also
cannot charge an old unknown attempt without a recorded allowance.

## Normalized usage

Finite nonnegative numeric reports are accepted; bool/negative/NaN/infinity are unknown.
Reported total wins. Without it, both input and output are required to derive their sum;
`total_source` distinguishes this derivation from provider reporting. Cache read/write remain
separate and are never added to input/output or total, because categories can overlap. A derived
input/output subtotal does not claim unreported reasoning/cache coverage. OpenCode retains raw
per-step usage and only aggregates a category present in every step. Cursor retains its raw usage
object and labels its input/output sum as derived. No guessed prices or subscription-zero costs.
Provider-reported cost and its provenance are retained; absent cost stays unknown.

Antigravity currently supplies no verified token/cost fixture. It continues to return unavailable
usage, which renders as unknown; no parser or zero-cost claim is invented. Unknown aggregates show
both the known subtotal and count of unknown attempts. Validation has a separate subtotal and is
also included once in build totals. Provider account-wide statistics remain separate from build cost.

## Admission policy

| Flag | Meaning |
|---|---|
| `--budget-attempts N` | Cumulative dispatch count, including validation/retries/escalation |
| `--budget-tokens N` | Cumulative token admission allowance |
| `--budget-cost USD` | Cumulative reported-cost admission allowance |
| `--attempt-tokens N` | Token reservation per dispatch |
| `--attempt-cost USD` | Cost reservation per dispatch |
| `--unknown-usage deny` | Default: unknown completed usage blocks a corresponding configured limit |
| `--unknown-usage reserve` | Explicitly charge the attempt's recorded allowance for unknown usage |

Cumulative token/cost limits require a positive corresponding per-dispatch reservation. Policy
persists across invocations; omitted flags retain prior values. Explicit flags revise policy and
new attempt records retain the selected policy. With no limits, accounting is still active and
unknown totals are visible. Validation spend permission (`--validation-policy`) remains a separate
T09 requirement; cached validation evidence incurs no new charge.

Admission checks known usage plus outstanding reservations and explicitly charged unknowns under
the shared build mutation lock. Simultaneous workers cannot each spend the same remaining allowance.
Known actual usage replaces the reservation on completion. A completed overrun is shown, and the
next call is blocked; an observed per-attempt overrun requires explicitly revising the allowance.
Already-running calls may exceed their allowances. These are admission controls, not provider token
kill switches or billing guarantees. Unknown usage charged by reservation remains unknown in reports;
it never becomes a fabricated measurement. Budget blocks return gate 5 and retain candidates, without
retrying/escalating a policy failure or labelling it model incapability.

## Status and telemetry

For T10 builds, status reads the current ledger summary: bounded by slices/models/active workers,
not total historical attempts or event-log length. It does not scan JSONL or attempt files. A crashed
invocation's last summary may still show reservations; resume reconciles the journal before new
admission. Status distinguishes reservations from proof that a process remains alive. Legacy
pre-T10 event streams retain the old read path until the build is resumed/migrated.

JSONL remains the complete diagnostic stream. Sink replacement closes the prior sink; closing a
failing sibling does not leak other sinks. Owned OTEL providers shut down on close, flushing their
processor; unfinished spans are ended. Unknown token values are omitted from OTEL attributes.

## Offline gate and canary boundary

Tests cover two failures then escalation success, validation consuming the production budget,
concurrent reservations at a threshold, interrupted/resumed usage, journal/ledger crash recovery,
unknown costs, overruns, budget blocking without escalation, retained patches and ledger/status
agreement. Existing real-Git candidate/recovery contracts remain required.

No live providers are used in T10. A later Kimi K3/OpenCode canary must first verify the exact
installed model/account and observed usage/cost source, then choose explicit per-attempt allowances,
cumulative limits and unknown policy. No fixed price assumption or live canary allowance is authorized
by this offline slice. M3 closes only when T10 verification passes.
