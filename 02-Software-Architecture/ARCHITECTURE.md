# Software Architecture — AI Caregiver for Neurodegenerative Patients

**Status:** Draft v0.2 (refs updated for PRD v0.3 merge)
**Depends on:** [01-PRD/PRD.md](../01-PRD/PRD.md)
**Last updated:** 2026-07-02

---

## 1. Architecture Principles

1. **HIPAA-first, not HIPAA-retrofitted.** Every layer assumes PHI (protected health information) flows through it. Encryption, access control, and audit logging are load-bearing, not bolted on.
2. **Decision-support, not diagnostic.** Architecture must not let any component present model output as a clinical conclusion (PRD, Open Risks #1 — FDA classification). This is enforced at the API layer (response schema forces `source_citations` + `disclaimer` fields on any AI-generated clinical-adjacent content) not just at the prompt layer.
3. **Disease-pluggable.** PD is MVP; AD and MS follow the same shape. Rating scales (UPDRS/CDR/EDSS), education corpora, and trial-match criteria are config/data, not code branches.
4. **Voice and low-motor-skill are first-class**, not a v2 add-on — affects API design (need voice session state) not just frontend.

## 2. System Diagram

```
                        ┌─────────────────────────────┐
                        │   Front-End UI                │
                        │   (Patient app / Caregiver     │
                        │    portal / Voice interface)   │
                        └───────────────┬─────────────┘
                                        │  REST + WebSocket (voice streaming)
                                        ▼
                        ┌─────────────────────────────┐
                        │   API Gateway / Auth           │
                        │   (OAuth2 + JWT, RBAC)          │
                        └───────────────┬─────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                ▼                       ▼                       ▼
      ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐
      │ Service Layer     │◄──►│ Data & Feature    │   │ Notification Service │
      │ (patients, meds,   │   │ Store              │   │ (push, SMS, voice     │
      │  check-ins, alerts)│   │ (Postgres+Timescale│   │  prompts via Twilio)  │
      └────────┬──────────┘   │  + Mongo notes)    │   └─────────────────────┘
                │              └─────────────────┘
                ▼
      ┌─────────────────┐   ┌─────────────────────┐
      │ AI Inference       │◄──►│ Knowledge Base /      │
      │ Orchestrator       │   │ RAG Store              │
      │ (RAG + LLM calls,   │   │ (curated medical corpus,│
      │  guardrails)        │   │  vector DB)             │
      └────────┬──────────┘   └─────────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │ Logging / Analytics / Audit    │
      │ (Prometheus+Grafana, Sentry,   │
      │  immutable audit log store)    │
      └─────────────────────────────┘
```

## 3. Layer-by-Layer Decisions

| Layer | Choice | Why |
|---|---|---|
| **Front-end** | React Native (patient + caregiver mobile), React web for caregiver portal desktop view | Single codebase mobile, matches PRD accessibility reqs (Dynamic Type, voice) with mature a11y libraries |
| **Voice/video transport** | WebRTC (video, phase 2), Twilio Voice (prompts, reminders) | Twilio already used for SMS reminders — one vendor for telephony reduces integration surface |
| **API** | FastAPI (Python) | AI/ML-adjacent service, Python ecosystem parity with inference layer, async support for streaming |
| **Auth** | OAuth2 + JWT; RBAC with `patient`, `caregiver`, `clinician` (phase 2) roles | Caregiver portal needs distinct, auditable permission scope from patient app (PRD, Caregiver Experience) |
| **Primary data store** | PostgreSQL | Relational integrity for patients/meds/consent — this is the compliance-critical data |
| **Time-series store** | TimescaleDB (Postgres extension) | Symptom check-in scores, adherence events — trend queries are the core analytics use case (PRD, Patient Experience analytics dashboard) |
| **Unstructured store** | MongoDB | Free-text notes, chatbot conversation transcripts |
| **AI inference** | Claude Sonnet 5 (`claude-sonnet-5`, Anthropic API) via tool use, orchestrating RAG retrieval over curated corpus + internal data tools; BAA confirmation still open (PRD, Open Risks #2) | Every clinical-adjacent answer must cite source (PRD, AI-Powered Education & Support) — RAG is the mechanism, not optional. Tool use (not freeform generation) for anything patient-data-adjacent — see §4. |
| **Knowledge base** | Vector DB (e.g., Pinecone or self-hosted pgvector) + curated corpus (PubMed abstracts, clinical guidelines, patient-consented forum data) | See §4 for corpus governance |
| **Monitoring** | Prometheus + Grafana (infra metrics), Sentry (errors), separate immutable audit log store (compliance — not the same system as ops monitoring) | HIPAA audit logs must not be commingled with general app logs / subject to the same retention-and-delete policy |
| **Deployment** | Containerized (Docker), API on Cloud Run or ECS Fargate, DB managed (RDS Postgres + TimescaleDB) | Avoid managing DB ops in-house given small initial team; Fargate/Cloud Run for stateless API scaling |
| **Messaging** | Twilio (SMS/WhatsApp for reminders + voice prompts) | Matches PRD, Patient Experience medication reminder engine requirement for non-app-open delivery |

## 4. AI Care Agent — Inference & Guardrails (critical path — PRD AI Behavior Contract + Open Risks #1, #2)

**Model:** `claude-sonnet-5` (Anthropic API, Messages API + tool use). Chosen over a Managed Agents / autonomous-agent surface — this is a bounded, application-embedded assistant with a fixed tool surface, not an open-ended coding/ops agent, so a standard tool-use loop the service layer controls is the right tier (per Anthropic's own surface-selection guidance: single-call/workflow/tool-use for bounded custom-tool agents; Managed Agents only when you want Anthropic to host the agent loop *and* the execution sandbox, which doesn't apply here).

**Every** AI-generated response that touches symptom interpretation, medication, or medical fact must go through this pipeline — no direct LLM passthrough:

```
User input
   │
   ▼
Intent classifier  (check-in / agent-query / reminder-ack / emergency-signal / out-of-scope)
   │
   ├─ emergency-signal → bypass LLM, trigger alert service directly (PRD, Caregiver Experience alerts)
   │
   ▼
Claude Sonnet 5 call — system prompt = PRD's AI Behavior Contract, with a fixed tool set:
   - get_patient_record(scope=self)   — read-only, scoped to requesting user's own data
   - search_corpus(query)             — RAG retrieval over curated medical corpus (vector DB)
   - search_trials(disease, stage)    — ClinicalTrials.gov query, disease/stage scoped
   - get_checkin_history(range)       — patient's own adherence/symptom log
   No tool returns another patient's data — enforced at the tool-implementation layer,
   not just by prompting.
   │
   ▼
Structured output enforcement (output_config.format, json_schema):
   every response required to carry:
     - answer: string
     - citations: array (non-empty whenever a factual/research claim is made;
       sourced only from search_corpus/search_trials results, never bare model claims)
     - disclaimer: string (fixed boilerplate, injected if response touches medical fact)
   │
   ▼
Output validator (application-layer, not just the schema):
   - Rejects response if a factual claim lacks a citation traceable to a tool call this turn
   - Rejects response if it matches disallowed-content patterns (diagnosis, dose change advice)
   │
   ▼
Response to user + logged (audit store, full tool-call trace)
```

Structured outputs are incompatible with citations-on-document-blocks in the same call — since retrieval here is via `search_corpus`/`search_trials` tool results (not `document` content blocks with `citations: {enabled: true}`), this doesn't conflict; the `citations` field above is populated from tool-result content, not the API's native document-citation feature.

**Adversarial test suite** (owned by 05-Testing) must run against this pipeline before every corpus/model update — not just at launch.

## 5. Disease-Pluggable Design (PRD, Scope & Sequencing)

To avoid rebuilding for Alzheimer's/MS, these are **config, not code**:

- Rating scale definition (question set, scoring range, severity thresholds) — PD: UPDRS 0–199; AD: CDR 0–3; MS: EDSS 0–10.
- Corpus namespace in the vector DB (per-disease retrieval scoping).
- Trial-matching criteria (PRD, AI-Powered Education & Support — literature & trial digest) — disease + stage → ClinicalTrials.gov query template.
- Medication schedule templates (levodopa timing pattern ≠ MS immunotherapy infusion schedule).

Service layer takes a `disease_profile` object per patient at onboarding; this drives which config set loads. **Do not branch application logic on disease name anywhere in the codebase** — if this happens, it's a signal the plug-in boundary leaked.

## 6. Data Flow: Fall/Emergency Detection (phase 1.5, PRD Future/Fast-Follow)

```
Wearable sensor → HealthKit/vendor API → webhook to Service Layer
   → bypass AI inference entirely (deterministic threshold check)
   → Alert Service → caregiver push + SMS, simultaneously
   → logged to audit store with full sensor payload for later review
```
No LLM in the critical alert path — latency and reliability requirements exclude it.

## 7. CI/CD

```
GitHub Actions → Unit tests → Security scan (Trivy) → Deploy to staging
   → Smoke test → Adversarial AI-safety test gate (blocks promote on any
   disallowed-content regression) → Promote to prod
```

## 8. Open Architecture Decisions (needs resolution before build starts)

1. ~~**LLM hosting**~~ — **resolved:** Claude Sonnet 5 via Anthropic API (see §4). Still blocking: BAA confirmation with Anthropic (PRD, Open Risks #2) — legal/compliance must confirm directly, not inferable from API docs. If a BAA at the needed tier isn't available, this reopens and self-hosted becomes the fallback.
2. **Vector DB**: managed (Pinecone) vs. self-hosted (pgvector in existing Postgres) — cost vs. one-less-vendor-to-BAA tradeoff. Same BAA-scoping question applies here too: any vendor touching PHI-adjacent data needs its own BAA or must be excluded from the PHI path.
3. **Wearable integration partner** for phase 1.5 fall detection (Apple HealthKit vs. dedicated medical-grade wearable) — affects webhook contract in §6.

---

*Next: Product/UX Design + Frontend (03-Product-UX-Design-Frontend) — use `ui-ux-pro-max` skill to generate design system from PRD personas + accessibility requirements.*
