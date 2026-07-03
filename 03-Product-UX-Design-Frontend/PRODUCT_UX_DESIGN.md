# Product / UX Design — AI Caregiver for Neurodegenerative Patients

**Status:** Draft v0.3 (auth/onboarding/invite UX split out, §10)
**Depends on:** [01-PRD/PRD.md](../01-PRD/PRD.md), [02-Software-Architecture/ARCHITECTURE.md](../02-Software-Architecture/ARCHITECTURE.md)
**Last updated:** 2026-07-03
**Reference note:** Mobbin MCP connected mid-session — pulled 25 screens from the Lovi app (iOS, AI skincare companion). Full IA visible: onboarding, Today/home, AI chat ("Ask Lóvi"), progress tracking, skin diary, settings. §9 documents what's adopted, adapted, or explicitly rejected from it — rejected mainly on compliance grounds (PRD Open Risk #1), not taste.

---

## 1. Design System

Generated via `ui-ux-pro-max --design-system` for a healthcare companion app, elderly/accessible-first framing.

### Colors — calm cyan + health green (WCAG AAA target)

| Role | Hex |
| --- | --- |
| Primary | `#0891B2` |
| On Primary | `#FFFFFF` |
| Secondary | `#22D3EE` |
| Accent/CTA | `#059669` |
| Background | `#ECFEFF` |
| Foreground | `#164E63` |
| Muted | `#E8F1F6` |
| Border | `#A5F3FC` |
| Destructive | `#DC2626` |
| Ring | `#0891B2` |

Rationale: cyan/teal reads clinical-but-warm (not sterile white/blue like generic med-tech; not clinical-cold gray). Green accent reserved for positive/confirm actions (adherence logged, check-in complete) — never used for anything the PRD's AI Behavior Contract would flag as medical-fact confirmation (that always needs the citation pattern, §4).

### Typography

- **Heading:** Figtree
- **Body:** Noto Sans
- Both are high-legibility, wide-language-support faces — matters for §2 accessibility reqs (Dynamic Type scaling) and future AD/MS localization needs.
- Base body size 16px minimum (PRD UI/UX Highlights — no auto-zoom triggers, readable at arm's length for tremor-affected users who hold devices less steadily).

### Anti-patterns (explicit avoid list)

- Bright neon colors, motion-heavy animations, AI purple/pink gradients — all read as "generic AI product," undermines trust for a medical-adjacent audience.
- No emoji as icons — SVG only (Heroicons/Lucide), consistent stroke width.

---

## 2. Accessibility Baseline (non-negotiable — PRD §UI/UX Highlights)

Directly enforced, not aspirational:

- Contrast ≥4.5:1 body text, ≥3:1 large text/UI glyphs (`color-accessible-pairs`)
- Touch targets ≥44×44pt, 8px+ spacing between (`touch-target-size`, `touch-spacing`)
- Full screen-reader labeling, logical focus order (`voiceover-sr`, `focus-management`)
- `prefers-reduced-motion` respected everywhere (`reduced-motion`)
- Dynamic Type support without truncation (`dynamic-type`, `truncation-strategy`)
- **One decision per check-in screen** (PRD explicit requirement — cognitive load management for AD-adjacent symptoms)
- Voice input as a first-class alternative on every data-entry screen, not a fallback bolted on

---

## 3. Information Architecture

### 3.1 Patient App (mobile, React Native per Architecture doc)

**Revised against Lovi's proven 5-tab-with-center-action structure** (Lovi: Today / Products / [center: New Scan] / Insights / Sunshine-profile). We adopt the shape, not the content — center tab as a persistent quick-action beats burying it, and 5 tabs with a visually distinct center item still reads as one decision (`bottom-nav-limit` allows up to 5; the center slot doesn't count against label-scanning load the way a 5th equal-weight tab would):

```
[ Today ]   [ Check-in ]   ( Voice Log )   [ Care Agent ]   [ Trends ]
                              center, raised
```

- **Today** — home/status screen. Next medication, today's check-in status (done/pending), one glanceable card per pending action. **Adopted from Lovi's Today screen:** a lightweight daily mood row (see §3.1a below) lives here too, separate from the deeper structured check-in.
- **Check-in** — the daily UPDRS-based flow (§5). Also reachable from a Today-screen card/notification deep link.
- **( Voice Log )** — center, raised action button, adapted from Lovi's "New Scan" center tab. One tap → voice capture starts immediately (symptom note, quick question to Care Agent, or ad-hoc check-in item) — no menu, no screen transition first. This is the single most-used action for a tremor-affected user, so it gets the least-motion path in the whole app.
- **Care Agent** — the Claude Sonnet 5 conversational surface (§4). Persistent entry point, not buried in a menu — PRD frames this as core, not support-ticket-adjacent.
- **Trends** — patient's own logged history (PRD, Open Risks #1: framed explicitly as "your logged history," never as clinical assessment — banner copy enforces this, see §6).

Settings still live behind the profile icon in the top-right header (`overflow-menu` pattern, also how Lovi handles it — settings, legal, log out are not tab-worthy).

#### 3.1a Today-screen daily mood row (adopted from Lovi)

Lovi's Today screen has an inline emoji row — "How does your skin feel today? [Bad] [Not great] [Okay] [Good] [Awesome]" — answered in place, zero navigation. We adopt this exact pattern for a lightweight daily wellbeing ping, distinct from the structured UPDRS check-in (§5):

```
"How are you feeling today?"   [😞] [😐] [🙂] [😊] [😄]   ← single tap, no screen change
```

This is not a replacement for the structured check-in — it's a second, near-zero-friction touchpoint for days the patient doesn't want to do the full flow. Feeds the same check-in-history data model (Architecture doc §4 `get_checkin_history` tool) as a distinct entry type. Icon-based, not emoji glyphs (`no-emoji-icons` — Lovi uses actual emoji here, which we don't copy; ours renders as SVG faces for cross-platform/theming consistency).

### 3.2 Caregiver Portal (web, per Architecture doc — separate app shell from patient mobile)

```
Dashboard → Patient Detail → Alerts → Settings
```

- **Dashboard** — the "30-second status check" (PRD explicit requirement). One row per linked patient: adherence %, last check-in status, active alerts. No drill-down needed to answer "is everything OK."
- **Patient Detail** — trend charts, check-in history, exportable log (PRD, power-user caregiver need).
- **Alerts** — chronological feed, filterable by patient, each alert links back to the triggering event.
- Desktop-first layout (`adaptive-navigation` — sidebar ≥1024px), but must degrade to mobile web without a rebuild (caregivers checking from a phone at work).

---

## 4. Care Agent — Conversation UI Pattern

PRD's AI Care Agent, tool-use pattern, Architecture doc §4. Revised against Lovi's "Ask Lóvi AI Cosmetologist" surface — same core shape (chat thread + suggested prompts), one deliberate divergence on citations (§4, below).

**Layout:** standard chat thread (user right-aligned, agent left-aligned) — deliberately conventional, not novel, because the audience already has one new interaction pattern to learn (voice-first health tracking) and doesn't need a second one (unfamiliar chat UI). Matches Lovi's own choice here — even a consumer-facing, lower-stakes app doesn't reinvent chat UI.

**Adopted from Lovi:** suggested-question chips above the input, shown on first entry to the agent screen (Lovi: "Skincare layering mistakes...", "Best way to fade post-acne spots..."). Ours are seeded from the patient's own disease stage/recent check-in data, not generic — e.g. "What does today's UPDRS score mean?", "Any new Parkinson's trials near me?". Reduces blank-input anxiety, which matters more here than in a skincare app given the audience.

**Every agent message that carries a factual/medical claim renders as a card, not a bare bubble** — this is where we deliberately diverge from Lovi. Lovi's AI answers cite sources inline as prose ("as noted in a PubMed study") with no tap-through; ours cannot do that, because Architecture doc §4's output validator requires every factual claim traceable to a tool call this turn, and an audit trail needs a structured, tappable citation, not a prose mention:

```
┌─────────────────────────────────────────┐
│ [Agent response text]                     │
│                                           │
│ Sources: [chip: AAN Guideline 2024 ✓]    │
│          [chip: PubMed PMC8126658 ✓]      │
│          (✓ = clinician-reviewed corpus   │
│           entry — adapted from Lovi's     │
│           "MD Verified" product badge)    │
│                                           │
│ ⓘ This is general information, not a     │
│   diagnosis. Talk to your care team for   │
│   guidance specific to you.               │
└─────────────────────────────────────────┘
```

- Citation chips are tappable → open source detail (title, snippet, link) — never silently trust-me text (maps to Architecture doc §4 output-validator requirement: no factual claim without a traceable citation).
- The "clinician-reviewed" checkmark is adapted from Lovi's "Lóvi MD Verified" trust badge on product cards — same trust-signal idea, applied to corpus provenance instead of product recommendations.
- Disclaimer line is fixed boilerplate, injected by the same validator — not model-generated, so it can't be prompted away.
- Escalation path: if the agent's out-of-scope classifier fires (Architecture doc §4 intent classifier), the card instead shows a "Talk to your care team" CTA with one tap to caregiver notify — never a dead-end "I can't help with that."
- **Adopted, reframed:** Lovi's "Lóvi Assistant says:" narrator framing for AI-generated reports (skin analysis summaries) — we use the same device for the literature/trial digest (PRD, AI Care Agent), framed as "Your Care Agent found:" — same trust-building narrator pattern, scoped to a feature where source-citation still applies in full.

**Input row:** text field + persistent mic button (not a secondary/hidden toggle — voice is equal-weight to typing per PRD accessibility requirement, not a fallback). Lovi's input is text-only ("Ask Lóvi anything...") — this is the one place we add rather than borrow, since voice-first is a hard PRD requirement Lovi's audience doesn't need.

---

## 5. Daily Check-in Flow (one decision per screen)

Sequential, linear, no branching visible to the user (branching logic — e.g. UPDRS scoring — happens server-side):

```
Screen 1: "Did you take your medication on time today?"  [Yes] [No] [Not yet]
Screen 2: "Any falls or near-falls since your last check-in?"  [No] [Yes →]
Screen 3: "How are your movements today?"  [1-5 scale, single tap]
Screen 4: (repeat pattern for remaining UPDRS-mapped questions, one per screen)
Screen N: Confirmation — "Check-in complete" + link to Trends (no auto-navigate away,
          user controls when they're done)
```

- Progress indicator at top (`multi-step-progress`) so the linear flow doesn't feel endless.
- Back navigation always available, preserves prior answers (`back-behavior`, `state-preservation`).
- A "Yes" on the falls question (Screen 2) branches to an immediate detail capture + triggers the emergency-signal path in Architecture doc §6 — this is the one place the check-in isn't purely linear, and it's intentional (safety over consistency).
- Every screen offers voice input as an equal alternative to tapping the scale/buttons.

---

## 6. Trends / Dashboard Framing (compliance-critical copy pattern)

Per PRD Open Risk #1 — any trend display risks reading as a clinical assessment. UI pattern to enforce the "logged history, not diagnosis" framing:

- Header always reads **"Your Logged History"**, never "Your Progress" or "Your Status" (implies clinical judgment).
- Chart labels use raw scale values (e.g. "UPDRS: 34") with a tooltip explaining what the number means, never a color-coded "good/bad" traffic light on the chart itself — a red/green trend line reads as a diagnostic signal, which is exactly what Open Risk #1 says to avoid.
- Caregiver Patient Detail view follows the same rule — this is a compliance requirement, not a stylistic preference, so it applies identically on both surfaces.

**Explicitly rejected from Lovi:** the Progress Tracking screen's green "✓ You are on track!" status badge. This is exactly the pattern Open Risk #1 exists to prevent — a system-generated verdict on the user's condition, dressed as encouragement. Fine for a skincare app; not fine here, where "on track" reads as a clinical judgment call the product isn't licensed to make. Our equivalent (check-in streak / consistency indicator, if any) states a neutral fact ("6 of 7 days logged this week"), never a status verdict.

---

## 7. Component Inventory (for Frontend build)

| Component | Used in | Accessibility notes |
| --- | --- | --- |
| Status card (Today screen) | Patient app home | Single tap target, full-card hit area |
| Single-question check-in screen | Check-in flow | One decision, voice-alternative, ≥44pt targets |
| Agent message card w/ citation chips | Care Agent | Tappable chips, disclaimer always rendered, never model-controlled |
| Escalation CTA card | Care Agent (out-of-scope path) | High-contrast, single primary action |
| Adherence summary row | Caregiver dashboard | Scannable in <5s per row, no drill-down required for status |
| Trend chart (raw-value, no color-coded judgment) | Trends / Patient Detail | Compliance-driven — see §6 |
| Voice input toggle | Global (check-in, Care Agent) | Equal-weight to text input, not secondary |
| Alert feed item | Caregiver alerts | Links to triggering event, timestamp, patient name |

---

## 8. Open Items

1. **Voice UI detailed spec** (wake phrase, confirmation pattern, error recovery when voice input misheard) — not detailed here, needs its own pass once a voice input framework/vendor is chosen (Architecture doc doesn't yet name one for the patient app, only Twilio for outbound reminders).
2. **Caregiver Portal responsive breakpoints** — needs concrete pixel values once frontend framework/component library is chosen.

---

## 9. Lovi Reference — Pattern Audit

Full disposition of every notable pattern pulled from the 25 Lovi screens (Mobbin, iOS). "Adopted" = used as-is or near-as-is; "Adapted" = same underlying idea, different execution; "Rejected" = considered and explicitly not used, with reason.

| Lovi pattern | Disposition | Where | Why |
| --- | --- | --- | --- |
| 5-tab nav w/ raised center action tab | **Adopted** | §3.1 | Proven shape for a persistent quick-action; center slot becomes Voice Log instead of camera scan |
| Inline daily emoji-row check-in on home screen | **Adopted** | §3.1a | Zero-friction second touchpoint alongside (not replacing) the structured check-in |
| Suggested-question chips on AI chat entry | **Adopted** | §4 | Reduces blank-input anxiety; ours seeded from patient data, not generic |
| Narrator framing ("Lóvi Assistant says:") for AI-generated reports | **Adapted** | §4 | Reframed as "Your Care Agent found:" for the literature/trial digest |
| "MD Verified" trust badge on product cards | **Adapted** | §4 | Reused as "clinician-reviewed" badge on citation chips, not products |
| Settings behind profile icon, not a tab | **Adopted** | §3.1 | Same reasoning — not tab-worthy, keeps primary nav short |
| Inline prose citation, no tap-through | **Rejected** | §4 | Our output validator requires a traceable, tappable citation per claim — audit requirement, not style choice |
| Green "✓ You are on track!" status verdict | **Rejected** | §6 | Reads as a clinical judgment call — exactly what PRD Open Risk #1 prohibits |
| Confetti/celebration animation on completing daily items | **Rejected** | §2 | Motion-heavy, conflicts with `prefers-reduced-motion` baseline (§2) for a tremor/motor-sensitive audience |
| Calendar view for scan/diary history | **Considered, deferred** | — | Reasonable alternate view for check-in history; not in MVP scope, revisit post-launch |
| Text-only AI chat input | **Extended, not adopted as-is** | §4 | We add persistent voice input — hard PRD requirement Lovi's audience doesn't share |

---

## 10. Auth, Onboarding & Caregiver Invite UX

Registration, login, password reset, the guided onboarding walk-through (disease confirmation, medication entry, communication preference, consent), and the patient-initiated caregiver invite/accept flow (both the no-account and existing-account paths) are specced in a sibling doc, not here: **[AUTH_ONBOARDING_UX.md](./AUTH_ONBOARDING_UX.md)**.

This work exists because 02-Software-Architecture/AUTH_LAYER.md introduced real auth (local email+password, JWT/refresh tokens, patient-initiated caregiver invites) where the original 5 screens in this doc assumed a hardcoded dev patient ID and never needed a login screen. Split into its own file for the same reason AUTH_LAYER.md itself was split out of ARCHITECTURE.md rather than appended to it — this project's established pattern for a pillar doc that's outgrown its parent (see also the 01/02/03/04/05 top-level split itself).

---

*Next: Database design (04-Database) — translate check-in flow (§5), Care Agent tool calls (§4, ties to Architecture doc §4 tool set), and caregiver dashboard queries (§3.2) into schema.*
