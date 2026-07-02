# AI Caregiver for Neurodegenerative Patients

### TL;DR

The AI Caregiver product empowers patients with neurodegenerative diseases (initially Parkinson's) and their caregivers by providing proactive symptom tracking, medication adherence tools, structured caregiver alerts, and AI-driven education—all designed to improve quality of life and extend high-function years. The platform is extensible to Alzheimer's and MS in future phases, with strict regulatory compliance and accessibility by design.

---

## Document Metadata

| Field | Value |
| --- | --- |
| Status | Draft v0.3 (merged) |
| Owner | TBD |
| Last Updated | 2026-07-02 |
| Intended Audience | Product, Engineering, Clinical/Regulatory Review |
| History | v0.1 original draft → v0.2 external revision → v0.3 merge (this doc) |

---

## Goals

### Business Goals

* Achieve >60% daily user engagement rate within the first 6 months of launch.
* Reduce average caregiver response time to adverse events by 30%.
* Establish HIPAA and GDPR compliance at MVP launch.
* Serve as a data and engagement platform for future integration with treatment research — as disease-modifying therapies and diagnostics mature (e.g., cell therapy, microbiome-targeted treatment), the product should be positioned to surface new options to patients, not just manage decline.

### User Goals

* Enable reliable medication reminders and adherence tracking.
* Provide caregivers with instant, actionable patient status and alerts.
* Simplify symptom tracking with voice-first and accessible UX.
* Offer up-to-date, cited medical information and research opportunities in plain language.

### Non-Goals

* The product does NOT diagnose or replace a neurologist as part of MVP.
* No closed-loop clinical decision-making or dose alteration suggestions in v1.
* No AR/video therapy or genomic data ingestion at launch.

---

## Scope & Sequencing

**MVP = Parkinson's disease only.** The data model, UX flows, and module architecture are designed to extend to Alzheimer's and MS by swapping the disease-specific rating scale, education corpus, and trial-matching criteria — not by rebuilding the app (see Software Architecture doc, disease-pluggable design).

| Phase | Disease | Trigger to start |
| --- | --- | --- |
| 1 (MVP) | Parkinson's | Now |
| 2 | Alzheimer's | Post-MVP validation w/ real PD users |
| 3 | MS | Post-Alzheimer's stabilization |

---

## User Stories

### Personas

| Persona | Description | Primary Needs |
| --- | --- | --- |
| Patient – Early/Mild | Newly diagnosed PD/AD/MS, independent | Education, symptom logging, reminders |
| Patient – Moderate, Low Motor Skill | Cognitive/motor impairment | Voice-first interaction, easy UI |
| Caregiver – Family | Unpaid, time-constrained | Alerts, quick patient overview, plain answers |

**Patient – Early/Mild:**

* As a patient, I want to receive reminders for my medications, so that I reduce the risk of missing doses.
* As a patient, I want to track my symptoms daily, so that I can spot trends or worsening conditions.
* As a patient, I want to ask the AI simple questions about my disease and receive credible answers, so that I can stay informed without reading primary research.

**Patient – Moderate, Low Motor Skill:**

* As a patient, I want to use voice to log symptoms, so that tremor or dexterity issues do not prevent accurate tracking.
* As a patient, I want large, easy-to-tap buttons, so that I can use the app despite motor difficulties.

**Caregiver – Family:**

* As a caregiver, I want to see my relative's medication adherence at a glance, so I can intervene early if doses are missed.
* As a caregiver, I want alerts when symptoms worsen, so that I can check in immediately.
* As a caregiver, I want answers in plain English about care best practices, so I can make better decisions quickly.

---

## Functional Requirements

* **Patient Experience** (Priority: Must-have/MVP)

  * Onboarding (diagnosis entry, medication list, communication preference, consent capture)
  * Daily symptom check-in (UPDRS for Parkinson's; text & voice)
  * Medication reminder engine (push, voice, adherence logging)
  * Analytics dashboard (trends for patient and caregiver)

* **Caregiver Experience** (Priority: Must-have/MVP)

  * Separate login, HIPAA-compliant, status dashboard
  * Immediate alerts for non-adherence or flagged symptoms
  * Simple 30-second status check workflow

* **AI Care Agent** (Priority: Must-have/MVP)

  * A single Claude Sonnet 5-based conversational agent (not a narrow AI Care Agent) that helps patients and caregivers with a range of tasks and questions: symptom/medication questions, literature and trial lookups, care best-practice guidance, and light task assistance (e.g., "when is my next dose," "summarize my week"). Always cites source for factual/research claims.
  * Tool-use pattern (see Software Architecture doc §4): the agent calls internal tools — patient record lookup (read-only, scoped to the requesting user), RAG retrieval over the curated corpus, trial-matching lookup, adherence/check-in history — rather than freeform generation for anything patient-data-adjacent.
  * Literature & trial digest (personalized plain-language summaries, direct links) — surfaced via the same agent's tool calls, not a separate bot.
  * GI health tracking (constipation, symptoms, gut-brain education, "track & learn" orientation — grounded in emerging Desulfovibrio/H2S/α-synuclein gut-brain axis evidence, see Reference Material)

* **Compliance & Security** (Priority: Must-have/MVP)

  * Audit-ready access logs
  * Granular consent, deletion requests
  * No diagnostic or dosing suggestion functionality

* **Future/Fast-Follow** (Should-have)

  * Sensor/wearable integration (fall detection)
  * Multi-caregiver support per patient
  * Video/AR therapy modules (Phase 2)

* **Out of Scope** (Explicit for MVP)

  * Dose recommendations or prescribing
  * Diagnostic risk scoring as clinical conclusion
  * Genomic/advanced biomarker data ingestion

---

## AI Behavior Contract

Every AI-generated response that touches symptom interpretation, medication, or medical fact is bound by this contract — enforced at the API layer (see Software Architecture doc, AI Inference & Guardrails), not just prompted for. This is the system prompt for the Claude Sonnet 5-based AI Care Agent:

```
Role: medical assistant agent for patients with Parkinson's disease.
Responsibilities:
  1. Ask daily UPDRS-based check-in questions.
  2. Remind about medication per patient's own schedule.
  3. Offer short guided routines (e.g., 5-minute walking) when appropriate.
  4. Answer patient/caregiver questions using tool calls (record lookup, RAG
     retrieval, trial search) — never answer patient-data or medical-fact
     questions from unaided generation.
Constraints:
  - Never provide a diagnosis.
  - Never suggest medication dose changes.
  - Always cite sources for any factual/research claim (RAG-retrieved, not
    from training data).
  - Escalate to caregiver/clinician when check-in answers indicate a concerning change.
Tone: empathetic, concise, plain language.
```

This contract is disease-specific config (per Scope & Sequencing) — AD/MS versions swap role framing and check-in scale reference (CDR / EDSS) but keep the same constraint set.

---

## User Experience

**Entry Point & First-Time User Experience**

* User downloads via referral or app store, or is onboarded by clinician; clear "not for diagnosis" disclaimer.
* Onboarding: guided walk-through prompts for diagnosis, symptoms, medication schedule, communication preference, consent.
* System adapts UI to user preference (text/voice first, large-font mode).

**Core Experience**

* **Step 1**: Morning symptom check-in notification arrives. User chooses voice or tap-based entry. Validation ensures key items are addressed (e.g., "Was medication taken on time? Any falls?").
* **Step 2**: Medication reminder fires based on user's schedule. User confirms with simple tap or voice. If missed, caregiver alerted (with appropriate rate-limiting).
* **Step 3**: Caregiver logs in to view patient's dashboard—sees adherence, recent symptoms, alerts.
* **Step 4**: User (patient or caregiver) can access the AI Care Agent to ask plain-language questions, or request small tasks,—AI returns concise, sourced answers. For out-of-scope queries, bot redirects to human clinician.
* **Step 5**: Patient receives plain-English digest of new literature/research trials, personalized to their stage.
* **Step X**: Power-users (caregivers) can view trends, export symptom logs for clinics.

**Advanced Features & Edge Cases**

* Voice fallback if motor impairment detected.
* Offline logging with sync-on-connect for users with unreliable connectivity.
* Adversarial testing of AI's scope boundaries to prevent disallowed advice.

**UI/UX Highlights**

* Large, high-contrast text as default, system-wide compliance with WCAG 2.2 AA.
* Touch targets ≥44×44pt; full screen reader and dynamic text scaling support.
* No more than 1 decision per check-in screen to reduce cognitive load.
* All AI answers and alerts clearly labeled and traceable for audit.

---

## Narrative

Sarah, recently diagnosed with Parkinson's, is determined to stay on top of her health. She downloads the AI Caregiver app, which guides her through setup in minutes—logging her medication regimen and preferred notification times. Each morning, Sarah receives a simple, voice-enabled symptom check-in—no confusing jargon, just straightforward questions. Her partner, David, checks Sarah's adherence dashboard on his lunch break and receives real-time alerts when a dose is missed, allowing him to intervene before symptoms worsen. Both Sarah and David rely on the in-app AI bot for plain-language answers to their questions about Parkinson's and emerging treatments, saving hours of reading primary literature. Later, when new clinical trial opportunities arise, Sarah is the first to know—her app delivers tailored, up-to-date information. Over time, Sarah's symptom logs help her care team adjust support, maximizing years of independence while keeping everyone informed and engaged.

---

## Success Metrics

### User-Centric Metrics

* Medication adherence rate (% reminders confirmed taken)
* Daily symptom check-in completion (% active users)
* Caregiver alert acknowledgment median time
* User satisfaction (in-app NPS or survey)

### Business Metrics

* 90-day retention of active users
* HIPAA compliance audit pass rate
* Expandable market: number of new users (by diagnosis phase)

### Technical Metrics

* API uptime (>99.9%)
* Error rates (AI bot, alerts)
* Security incidents (number, response time)
* Zero incidents of the AI Care Agent giving disallowed medical advice (tracked via adversarial testing + production monitoring)

### Tracking Plan

* Medication reminder confirm/cancel events
* Daily check-in completion
* Caregiver dashboard logins/views
* AI Care Agent usage and escalation to clinician events
* All alert triggers and follow-up actions

---

## Technical Considerations

### Technical Needs

* Secure, HIPAA-compliant cloud hosting
* Modular data model for symptom data, medication logs, and caregiver interactions
* Seamless integration for future sensor/wearable APIs
* Audit trail for all access/actions

### Integration Points

* Potential phase 1.5/2 sensor/wearable partners (Apple HealthKit, etc.)
* External clinical trial/literature APIs (ClinicalTrials.gov)
* (Future) EHR export if integrated into clinical workflow

### Data Storage & Privacy

* All data encrypted at rest (AES-256), transit (TLS 1.3)
* Explicit, granular consent; support for deletion requests & audit logs

### Scalability & Performance

* Architecture designed for rapid patient/caregiver onboarding at scale
* Fast, resilient endpoints for time-sensitive events (alerts, reminders)

### Potential Challenges

* FDA regulatory review for any diagnostic-leaning feature
* Ensuring AI scope control, preventing clinical advice beyond decision support
* Making voice/text interfaces robust to neuro-cognitive and motor symptoms

---

## Milestones & Sequencing

> Revised from earlier draft: a HIPAA-compliant app with an AI/RAG guardrail pipeline, caregiver portal, audit logging, and accessibility compliance does not ship as MVP in 1–2 weeks with a 2-person team. Estimate and team composition below reflect the actual scope in Functional Requirements + AI Behavior Contract + Technical Considerations.

### Team Composition (MVP)

* 1 Product Owner
* 2 Backend/Platform engineers (API, data model, compliance/audit infra)
* 1 ML/AI engineer (RAG pipeline, guardrail/output validation, adversarial test harness)
* 1–2 Frontend/mobile engineers (React Native — patient app, caregiver portal)
* 1 shared UX/Design resource
* Part-time: compliance/legal counsel (HIPAA/GDPR, FDA classification review), security reviewer

### Project Estimate

* **MVP core**: ~8–12 weeks (onboarding, check-in, reminder engine, caregiver portal, AI Care Agent w/ guardrails, audit logging) — gated on legal/compliance sign-off before launch, not just before code-complete.
* **Sensor/fast-follow**: ~4–6 weeks after MVP, contingent on wearable partner selection.
* Estimate assumes compliance and RAG-guardrail work start in parallel with core feature build, not after.

### Suggested Phases

**MVP Launch**

* Deliver core patient/caregiver onboarding, medication/adherence, dashboard, and AI FAQ.
* Team: Product, Engineering, ML
* Dependencies: Clinical review for education corpus, legal/compliance review, FDA classification determination (blocking — see Open Risks #1)

**Sensor/Fast-Follow**

* Add wearable integration, enhanced analytics.
* Team: Product, Engineering
* Dependencies: Partner/sensor selection

**Expansion (future)**

* Add support for Alzheimer's, MS (per Scope & Sequencing trigger conditions); video/AR modules; EHR sync as needed.
* Dependencies: Market feedback, compliance assessment

---

## Reference Material Used

* Neuroinflammation across AD/PD/MS — biomarker dataset (De la Serna Tuya, 2026, Harvard Dataverse, DOI 10.7910/DVN/X2TQQA)
* Gut-brain axis / Desulfovibrio-hydrogen sulfide-α-synuclein pathogenesis model (PMC8126658) — basis for GI health tracking feature
* Stem-cell dopamine neuron therapy (bemdaneprocel) Phase 1→3 trial coverage (Nature 2025, MSK/BlueRock) — informs long-term platform goal of surfacing emerging treatments

---

## Open Risks / Decisions Needed

1. **FDA classification** — legal review required for clinical/diagnostic feature boundaries before launch. This includes trend/dashboard displays — frame as "your logged history," not a clinical assessment.
2. **LLM/data hosting** — **decided:** Claude Sonnet 5 (Anthropic API) — chosen for cost/quality balance at the AI Care Agent's tool-use and citation-enforcement needs (see Software Architecture doc §4). **Still open, blocking launch:** confirmation of a signed BAA (Business Associate Agreement) with Anthropic covering this workload — this is a plan-tier/contractual matter, not something resolvable from API docs alone. Legal/compliance must confirm directly with Anthropic before any PHI touches the API. If unavailable at the needed tier, fall back to self-hosted open-weight model — re-opens this decision.
3. **Sensor/wearable partner** — choose integration platform for fall detection (Apple HealthKit vs. dedicated medical wearable).
4. **AI accuracy monitoring** — rigorous adversarial testing and scope-guardrails required before launch, and on every corpus/model update thereafter, not just at launch.

---

*Next: Software Architecture doc (02-Software-Architecture) — translate Functional Requirements, AI Behavior Contract, and Technical Considerations into system design.*
