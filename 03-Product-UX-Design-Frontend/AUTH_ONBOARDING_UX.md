# Auth, Onboarding & Caregiver Invite UX — AI Caregiver for Neurodegenerative Patients

**Status:** Draft v0.1 — spec, not yet implemented
**Depends on:** [03-Product-UX-Design-Frontend/PRODUCT_UX_DESIGN.md](./PRODUCT_UX_DESIGN.md) §1 (design system), §2 (accessibility baseline), §5 (check-in pattern precedent), §9 (Lovi audit method) — [01-PRD/PRD.md](../01-PRD/PRD.md) Personas, User Stories, User Experience — [02-Software-Architecture/AUTH_LAYER.md](../02-Software-Architecture/AUTH_LAYER.md) — [04-Database/DATABASE_DESIGN.md](../04-Database/DATABASE_DESIGN.md) §2.1, §2.4
**Last updated:** 2026-07-03

---

## 0. Why this doc exists, and two things checked before writing it

AUTH_LAYER.md §6 names the gap directly: "Neither 01-PRD nor 03-Product-UX-Design-Frontend specifies who initiates a caregiver invite or the account-creation UX in implementation detail." PRD §User Experience mentions onboarding ("guided walk-through prompts for diagnosis, symptoms, medication schedule, communication preference, consent") but never breaks it into screens. This doc closes both gaps, plus specs registration/login, which no doc has touched at all — the original 5 screens (Today, Check-in, Voice Log, Care Agent, Trends) all assumed a hardcoded dev patient ID (`patient-app/src/lib/api.ts`, `DEV_PATIENT_ID`, visible in `index.tsx`/`checkin.tsx`) and never needed a login screen to reach them.

This is a **new sibling doc**, not an addition to PRODUCT_UX_DESIGN.md's body — same reasoning that doc's own header note applies to itself, and the same move 02-Software-Architecture made when auth got detailed out of ARCHITECTURE.md into its own file. PRODUCT_UX_DESIGN.md §10 is a two-line stub pointing here.

Two things checked before writing, rather than assumed, because the task framing asserted them and both turned out to need correction:

1. **"ARCHITECTURE.md now references AUTH_LAYER.md as a sibling doc"** — checked directly (`grep -n -i "AUTH_LAYER" ARCHITECTURE.md`): no match. ARCHITECTURE.md predates AUTH_LAYER.md by a day and has not been updated to reference it. This doc follows the repo's actual established cross-reference pattern instead (a `Depends on` header line + a `Next:` footer pointer) rather than mimicking a citation that doesn't exist yet.
2. **Whether the architect assumed a specific surface for caregiver invite-accept** — checked AUTH_LAYER.md §6.2: it doesn't say. But two other docs disagree with each other about whether a caregiver *native mobile app* exists at all: ARCHITECTURE.md §3's front-end row lists "React Native (patient + caregiver mobile), React web for caregiver portal desktop view," while PRODUCT_UX_DESIGN.md §3.2 headers the whole Caregiver Portal section "(web, per Architecture doc — separate app shell from patient mobile)" and specs only Dashboard → Patient Detail → Alerts → Settings as web screens, with a "must degrade to mobile web" requirement rather than a native-app requirement. The repo itself has no `caregiver-app/` directory — only `patient-app/`. Given the actual IA this doc must build against (§3.2's web-only scope) and the absence of any caregiver mobile codebase, §3 below specs the caregiver side of the invite flow as **web only** (responsive, opened from any device's browser via the invite link). This is a real scope decision, not a detail — see Open Items #2.

---

## 1. Registration & Login

### 1.1 Design call: one field per screen, or a single form?

§5's one-decision-per-screen pattern exists for a stated reason (§2: "cognitive load management for AD-adjacent symptoms," repeated daily). Registration and login are not a repeated, symptom-adjacent task — they're a one-time (registration) or low-frequency (login) transaction with a familiar shape from outside this app entirely (every email client, every retail app). Splitting "enter your email" and "enter your password" into two separate full-screen transitions adds navigation overhead (more taps, more screen transitions, more places to lose a low-vision or tremor-affected user mid-flow) without reducing cognitive load — the two fields are one coherent decision ("who are you"), not two independent ones the way "did you fall?" and "how are your movements today?" are independent clinical questions in §5.

**Call: single-screen forms for Register and Login**, each with all fields visible at once, generous spacing (§2 touch-target/spacing rules apply to fields and buttons identically), and inline (not deferred) validation. One-decision-per-screen is preserved for onboarding (§2 below), where each screen genuinely is a separate decision with its own weight (disease confirmation, medication entry, five distinct consent choices) — that's where the pattern's stated rationale actually applies.

### 1.2 Screen: Landing / Welcome

First screen on cold launch, unauthenticated.

```
┌─────────────────────────────────────┐
│         AI Caregiver                 │
│                                       │
│  Symptom tracking, medication        │
│  reminders, and answers about        │
│  Parkinson's — for you and the       │
│  people caring for you.              │
│                                       │
│  This app does not diagnose or       │
│  replace your neurologist.           │
│                                       │
│   [ Create account ]  (primary)      │
│   [ Log in ]          (secondary)    │
└─────────────────────────────────────┘
```

- "Does not diagnose" disclaimer is present on the very first screen, unauthenticated — matches PRD §Entry Point & First-Time User Experience ("clear 'not for diagnosis' disclaimer") and the same fixed-boilerplate discipline PRODUCT_UX_DESIGN.md §4 applies to the Care Agent's disclaimer line: it's product copy, not something a later screen can omit once the user is past onboarding.
- Two clearly weighted actions (`color-accessible-pairs`, §1 design system: primary `#0891B2` fill, secondary outline) — no ambiguity about which is the "start here" path for a first-time user, per PRD Narrative's framing of Sarah's first minutes with the app.

### 1.3 Screen: Create account (patient)

```
┌─────────────────────────────────────┐
│  ← Back           Create account     │
│                                       │
│  Email                               │
│  ┌─────────────────────────────┐ 🎤 │
│  └─────────────────────────────┘     │
│                                       │
│  Password                            │
│  ┌─────────────────────────────┐     │
│  └─────────────────────────────┘     │
│  Use 8+ characters                   │
│                                       │
│  Confirm password                    │
│  ┌─────────────────────────────┐     │
│  └─────────────────────────────┘     │
│                                       │
│  [ Create account ]  (primary)       │
│                                       │
│  Already have an account? Log in     │
└─────────────────────────────────────┘
```

Maps to `POST /api/v1/auth/register/patient { email, password, disease_code, preferred_comm_mode }` (AUTH_LAYER §6.1) — **`email`, `password`, and `disease_code` all ride in this single call; `preferred_comm_mode` is the one field not sent here.** `disease_code` is not a field this screen (or any screen) asks the user about: since §2.2 below is a confirmation, not a real choice, for the entire MVP, the client hardcodes `disease_code: "parkinsons"` into this same registration call — there's no decision here to defer, so there's no reason to split the transaction over it. `preferred_comm_mode` is a genuine per-user choice (§2.3), not something to guess a default for at registration time before the user has seen why they're being asked — this field is deferred, sent later as a small, targeted `PATCH` to the patient record once the user reaches the comm-preference screen in onboarding, rather than folded into a second full "onboarding-completion" endpoint. That's a narrower, cheaper seam against AUTH_LAYER §6.1's spec than an alternate transaction shape would be — flagged precisely in Open Items #9, scoped to just this one field, not the whole registration payload.

- **Voice input:** email field only (mic icon, equal-weight per §2's "voice input as first-class alternative on every data-entry screen"). **Password and Confirm password fields deliberately exclude voice input** — this is the one place this doc overrides the accessibility baseline's default, and it's called out explicitly rather than silently: speaking a password aloud is a security leak (overheard in a shared living space, a clinic waiting room, a caregiver's earshot — exactly the settings this audience is often in), not an accessibility win. The accommodation for password entry instead: full platform autofill/password-manager support (`autoComplete="new-password"` / equivalent) and, once one login has succeeded, biometric unlock (Face ID/Touch ID/fingerprint via device secure storage, §1.5) so typing a password is a rare event, not a daily one.
- **Password field:** show/hide toggle (eye icon, ≥44×44pt per §2 `touch-target-size`) — typing a password blind, twice, for a tremor-affected user is its own accessibility failure; letting them see what they typed is more important here than the generic "mask passwords" convention.
- **Validation:** inline, on blur, not only on submit — "Use 8+ characters" hint shown by default (not only after an error), turns from muted to caution-colored only after a failed attempt. Password policy specifics (minimum length beyond 8, complexity rules) are AUTH_LAYER §2.2's "implementation detail for the Backend Dev, not re-specified there" — this screen's copy will need the real policy once set; `8+ characters` here is a placeholder minimum, not this doc asserting the actual policy (Open Items #4).
- **Error states, honest per the `index.tsx` precedent** (that screen's "Could not reach the backend" card shows the real error text, not a generic failure message):
  - Email already registered → `This email already has an account. [Log in instead]` — specific and actionable, not "Something went wrong."
  - Passwords don't match → inline under Confirm password, before submit is even attempted if both fields have been touched.
  - Network/server unreachable → same card pattern as `index.tsx`: "Could not create your account — [real error detail]" with a retry action. Never a bare spinner that silently times out.

### 1.4 Screen: Log in

```
┌─────────────────────────────────────┐
│  ← Back                Log in        │
│                                       │
│  Email                               │
│  ┌─────────────────────────────┐ 🎤 │
│  └─────────────────────────────┘     │
│                                       │
│  Password                            │
│  ┌─────────────────────────────┐     │
│  └─────────────────────────────┘     │
│                                       │
│  Forgot password?                    │
│                                       │
│  [ Log in ]  (primary)               │
│                                       │
│  New here? Create account            │
└─────────────────────────────────────┘
```

Maps to `POST /api/v1/auth/login {email, password}` (AUTH_LAYER §6.1). This is the patient-facing login screen; PRD §Caregiver Experience calls for "Separate login" — the caregiver web portal has its own login page, same field shape, reached only from a browser (never from the patient app), per §0's surface decision.

**Error states — honest, but with one deliberate exception:**

- **Wrong email or password:** `Email or password is incorrect.` — generic, does **not** say which field is wrong. This looks like it conflicts with the "don't fake success, show real errors" precedent, so the reasoning is spelled out here rather than left implicit: honest doesn't mean maximally diagnostic when the extra diagnostic detail creates a security hole. Confirming "that email doesn't exist" vs. "that password is wrong" as two different messages lets an attacker enumerate registered accounts — a real HIPAA-adjacent risk for a patient roster of Parkinson's diagnoses. The message never claims success and never hides that login failed; it just doesn't over-disclose *why*. That's the same honesty standard as `index.tsx`'s error card, applied to a case where full disclosure itself is the harm.
- **Account locked / rate-limited:** `Too many attempts. Try again in a few minutes.` — AUTH_LAYER §2.2 defers the exact threshold/timing to the Backend Dev as an implementation detail; this doc specs the UI shape (a distinct, honest state — not folded into the generic wrong-password message, since the user needs to know *waiting* is the fix, not retrying immediately) without asserting the real numbers (Open Items #4).
- **Network/server unreachable:** same `index.tsx`-pattern card as registration — real error text, not "Something went wrong."
- Every error state is announced to screen readers on appearance (`voiceover-sr`, §2), not just rendered visually — a failed login that only shows as a color change is invisible to a screen-reader user.

### 1.5 Password reset

**No endpoint for this exists in AUTH_LAYER.md** — checked directly, §6 and §8 enumerate `register/patient`, `register/caregiver`, `login`, `refresh`, `logout`, and the caregiver-invite routes; nothing named `forgot-password` or `reset-password`. This section specs the UI and states its assumptions plainly so the gap is visible, not papered over (Open Items #1) — it is a proposal for the Backend Dev/architect to confirm or override, not a restatement of an existing contract.

**Design call: in-app one-time code, not an email reset link.** A reset-link flow assumes the recipient can open a browser and land back in a state the app recognizes (deep link / universal link) — reliable for the Caregiver Portal (already a web surface, §3.2) but not a safe assumption for the patient app: `patient-app` is mobile-only with no companion web surface (§0), this audience skews elderly/low-motor-skill, and a broken universal link (app not installed under that exact bundle ID, wrong default browser, a corporate device restriction) leaves a distressed, locked-out user with no recovery path and no one to ask. A short numeric code the user reads off their email or SMS and types back into the app they already have open avoids all of that — no deep-link reliability dependency, works identically whether the email arrives on the same device or a different one (e.g., a caregiver checks Sarah's email for her).

```
Screen 1: "Forgot your password?"
  Email
  ┌─────────────────────────────┐ 🎤
  └─────────────────────────────┘
  [ Send code ]

Screen 2: "Check your email"
  "If an account exists for [email], we've sent a 6-digit code.
   It expires in 15 minutes."
  [ Enter code ] (advances regardless of whether the email
                  existed — see note below)

Screen 3: Enter code
  ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐   (6 individual digit boxes, large touch targets)
  [ Verify ]
  "Didn't get it? Send again" (rate-limited, disabled 30s after send)

Screen 4: New password
  New password        ┌─────────────────────────────┐
  Confirm password     ┌─────────────────────────────┐
  [ Reset password ]
  → success → routes to Log in with a confirmation banner,
    never auto-logs-in on a device that isn't verified as the
    account owner's
```

- Screen 2's copy ("If an account exists for...") is deliberately non-committal for the same account-enumeration reason as §1.4's login error — this is the one screen in this flow where under-disclosure is correct, not a violation of the honest-errors precedent.
- Code entry, not voice — same reasoning as password fields (§1.3): a 6-digit code read aloud is no more sensitive than typing it, so voice input **is** offered here as an equal alternative (mic button reads back the digits for confirmation before submitting, since a misheard "6" vs "5" needs a correction step before it silently fails).
- This flow needs `POST /auth/forgot-password {email}` and `POST /auth/reset-password {email, code, new_password}` (or equivalent) added to AUTH_LAYER.md — not inferable from anything currently specified there.

---

## 2. Onboarding

Runs immediately after `register/patient` succeeds (AUTH_LAYER §6.1 step 4: "Client proceeds into the existing onboarding UX... now authenticated"). Follows the same sequential, one-decision-per-screen shape as `checkin.tsx` (§5's precedent) — unlike registration/login (§1.1), every screen here genuinely is one separate decision, so the pattern's rationale actually holds. Progress indicator at top throughout (`multi-step-progress`, same as §5), back navigation preserves prior answers (`back-behavior`, `state-preservation`).

```
Screen 1: Welcome / what to expect
Screen 2: Disease confirmation
Screen 3: Communication preference
Screen 4: Medications (repeating add-one-at-a-time sub-flow)
Screen 5: Consent (one screen, five distinct toggles — see §2.4)
Screen 6: Done → lands on Today
```

### 2.1 Screen: Welcome

```
┌─────────────────────────────────────┐
│  Let's set up your account           │
│                                       │
│  This takes about 3 minutes. We'll   │
│  ask about your diagnosis,           │
│  medications, how you'd like to      │
│  hear from us, and what you're       │
│  comfortable sharing.                │
│                                       │
│  You can change any of this later    │
│  in Settings.                        │
│                                       │
│  [ Get started ]                     │
└─────────────────────────────────────┘
```

Setting the time expectation ("about 3 minutes") and the "change it later" reassurance up front matters more here than in most onboarding flows — PRD Persona "Patient – Moderate, Low Motor Skill" is exactly the user for whom an open-ended, unbounded-feeling form is likeliest to cause drop-off.

### 2.2 Screen: Disease confirmation

**MVP is Parkinson's-only** (PRD Scope & Sequencing: "MVP = Parkinson's disease only"; Database doc §2.2 `disease_profiles.active`: "MVP: only 'parkinsons' active"). This is stated explicitly rather than left implicit in the UI design: **this screen is a confirmation, not a real choice.** Building a disease-picker component for one enabled option would be dead UI weight and would misrepresent the product's actual current scope to a newly-diagnosed patient who may not know AD/MS support doesn't exist yet.

```
┌─────────────────────────────────────┐
│  Your care plan                      │
│                                       │
│  AI Caregiver is currently built     │
│  for Parkinson's disease care.       │
│                                       │
│  ✓ Parkinson's disease               │
│                                       │
│  We'll use this to tailor your       │
│  daily check-in questions and the    │
│  information your Care Agent shares. │
│                                       │
│  [ Continue ]                        │
└─────────────────────────────────────┘
```

- No selectable options, no dropdown — a single, pre-affirmed statement with a `Continue` action. **This screen has no payload of its own** — `disease_code: "parkinsons"` was already sent unconditionally as part of the single `register/patient` call in §1.3, since there was never a decision here to defer (Database doc §2.2's `disease_code` enum has `alzheimers`/`ms` rows present but `active: false` — the client doesn't need to know that distinction exists at all, since it never renders a choice for it). This screen exists purely to tell the user what was already recorded, not to collect anything new.
- When AD/MS go active (PRD Scope & Sequencing Phase 2/3), this screen becomes a real picker — that's a future revision of this same screen, not a new screen, and it's the only onboarding screen whose shape changes at that milestone. Flagged so a future editor of this doc knows exactly where that change lands (Open Items #7).

### 2.3 Screen: Communication preference

```
┌─────────────────────────────────────┐
│  How would you like to check in?     │
│                                       │
│  [ Text ]     — tap to answer        │
│  [ Voice ]    — speak your answers   │
│  [ Both ]     — choose each time     │
│                                       │
│  You can change this anytime in      │
│  Settings.                           │
└─────────────────────────────────────┘
```

Single tap, single decision, maps directly to `patients.preferred_comm_mode` (Database doc §2.1, `CHECK (preferred_comm_mode IN ('text', 'voice', 'both'))`). No `Continue` button needed — selecting an option advances immediately, consistent with the low-friction, single-tap pattern §3.1a's mood row already established in the shipped app (`index.tsx`'s `submitMood`, single tap, no confirmation screen). "Both" is worded as "choose each time," not "text and voice at once" — it's a per-interaction choice, not a mode where every screen shows two input methods stacked (voice is already offered as an equal alternative everywhere per §2 of the main doc, independent of this setting; this setting instead governs which channel proactive prompts/reminders default to, e.g., a Twilio voice call vs. an SMS/push).

### 2.4 Screen(s): Medications

Initial medication list entry — PRD §Patient Experience: "Onboarding (diagnosis entry, medication list...)". Maps to `medications (name, dosage, schedule_rrule)` (Database doc §2.3).

```
Screen 4a: "Do you take any medications for Parkinson's?"
  [ Yes, add a medication ]   [ Not yet / skip for now ]
                                → skip goes straight to Screen 5 (Consent)

Screen 4b (repeats per medication): "Add a medication"
  Medication name
  ┌─────────────────────────────┐ 🎤
  └─────────────────────────────┘

  Dosage (e.g. "100mg")
  ┌─────────────────────────────┐ 🎤
  └─────────────────────────────┘

  How often?
  [ Once daily ] [ Twice daily ] [ Three times daily ] [ Custom ]
    → selecting a preset shows time pickers for that many doses/day
    → "Custom" opens a plain-language day/time builder, never raw
      RRULE syntax

  [ Save medication ]

Screen 4c: "Add another medication?"
  [ + Add another ]     [ I'm done — Continue ]
  (list of medications added so far, each with an edit/remove
   affordance, shown above these buttons)
```

- **Voice input on the medication-name field carries a specific risk this doc flags rather than treats as solved:** drug names are exactly the kind of input voice transcription gets wrong (brand vs. generic names, similar-sounding drugs — "Sinemet" vs. some transcription near-miss). A misheard drug name silently entered into a medical record is worse than no entry at all. This screen requires a **read-back confirmation** step after voice input specifically for this field ("We heard: *Sinemet* — is that right? [Yes] [Try again / type instead]") before the value is accepted — not required on other voice-input fields in this doc, called out here because the consequence of a silent transcription error is materially higher for a medication name than for, say, an email address (which gets validated by the confirmation-email/login-failure loop anyway). Full voice-input error-recovery design is still PRODUCT_UX_DESIGN.md §8 Open Item #1 (not resolved by this doc) — this is a narrower, in-line mitigation for the one field where getting it wrong is highest-stakes, not a substitute for that broader pass.
- `schedule_rrule` is never shown to the user as text — the preset buttons and time pickers are translated to an RRULE string by the client (or sent as structured data and translated server-side; an implementation choice, not specified here) before hitting the API. Matches the general house rule (Architecture doc §5) of not leaking an internal technical representation into a UI surface that doesn't need it.
- Skippable (`Not yet / skip for now`) — PRD Persona "Patient – Early/Mild" may be newly diagnosed and not yet prescribed anything; forcing a medication entry blocks onboarding completion for a real, common case. Medications can be added later from Today or Settings (existing `POST` medication route, unchanged by this doc).

### 2.5 Screen: Consent

Database doc §2.4 defines five consent categories: `symptom_data`, `fall_location_data`, `research_personalization`, `caregiver_sharing`, `literature_digest`. The task requirement is that these read as "genuinely separate, revocable choices, not one buried checkbox" — that requirement is about **how distinctly each choice is presented**, not about screen count. This doc deliberately does **not** split consent into five sequential full screens the way §5's UPDRS questions are split:

- §5's one-decision-per-screen rigor is scoped, by its own stated rationale (§2: "cognitive load management for AD-adjacent symptoms"), to a **repeated daily task** where each question is a separate clinical data point being freshly assessed. Consent is a **one-time, deliberative, legal-effect decision** — the user benefits from seeing all five choices in relation to each other (so "do I want research use of my data" can be weighed against "do I want my caregiver to see my data" as related-but-distinct questions), not from having each one isolated from the others by a full-screen transition that erases that context.
- Five consecutive full screens for a one-time setup step also carries real abandonment risk for this specific task shape: each screen transition is another point where a user closes the app "to finish later" and doesn't — worse for a *consent* step than for daily check-in, since an incomplete consent screen blocks account setup entirely rather than just delaying one day's data point.

**Call: one screen, five visually and interactively separate sections**, each independently toggled, each defaulting to **off** (unchecked) — no pre-selected consent, which would be the "buried checkbox" dark pattern this requirement exists to prevent, just spread across a single screen instead of hidden in one line.

```
┌─────────────────────────────────────┐
│  Your data, your choice              │
│                                       │
│  Each of these is optional and       │
│  separate. You can turn any of       │
│  them on or off later in Settings.   │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ Daily symptom tracking       │     │
│  │ Lets us record your check-in │     │
│  │ answers so you and your care │     │
│  │ team can see your history.   │     │
│  │ Without this, daily check-in │     │
│  │ won't work.        [●  On]  │     │
│  └─────────────────────────────┘     │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ Fall/location data           │     │
│  │ Used only if you connect a   │     │
│  │ wearable that detects falls. │     │
│  │                     [  ○ Off]│     │
│  └─────────────────────────────┘     │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ Share with my caregiver      │     │
│  │ Lets a caregiver you invite  │     │
│  │ see your adherence, alerts,  │     │
│  │ and trends. Never your       │     │
│  │ private chats with your      │     │
│  │ Care Agent.        [  ○ Off]│     │
│  └─────────────────────────────┘     │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ Research & personalization   │     │
│  │ Helps improve the app and    │     │
│  │ (optionally) contribute to   │     │
│  │ Parkinson's research.        │     │
│  │                     [  ○ Off]│     │
│  └─────────────────────────────┘     │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ Research & trial digest      │     │
│  │ Personalized updates on new  │     │
│  │ studies and clinical trials. │     │
│  │                     [  ○ Off]│     │
│  └─────────────────────────────┘     │
│                                       │
│  [ Continue ]                        │
└─────────────────────────────────────┘
```

- Each toggle writes its own `consent_records` row on submit (`category`, `granted`, `version` = the copy version shown — Database doc §2.4's audit requirement), even the ones left off (`granted: false`) — an explicit "no" is itself a recorded decision, not an absence of a row, so a later audit can show the user was asked and declined, not just never asked.
- **`symptom_data` is the one exception to "everything optional and off by default"** — it defaults **on**, with inline copy stating plainly what happens if it's turned off ("Without this, daily check-in won't work"), rather than being silently required. This is a deliberate, disclosed tradeoff, not a forced consent: the user can still switch it off and see the honest consequence stated in place, same as the wrong-password error in §1.4 states a real consequence instead of a vague failure. Making a checkbox mandatory-and-hidden would be the dark pattern; making it opt-out-with-a-stated-cost, defaulted to match what the product's core feature actually requires, is not the same thing — it is still genuinely revocable (Settings, any time), it just isn't free of consequence, and the copy says so.
- **`caregiver_sharing`'s copy explicitly states the boundary from PRODUCT_UX_DESIGN.md's own compliance model** — "Never your private chats with your Care Agent" — which is not just reassuring copy, it's a direct restatement of Database doc §8 ("Cannot read `agent_conversations` content... no such sharing feature in MVP") and AUTH_LAYER §5.1 (`require_patient_self` blocks caregiver access to agent routes categorically). Getting this line right matters: a patient who doesn't know that boundary exists may decline `caregiver_sharing` out of a fear this doc's own architecture already forecloses, or may wrongly assume the opposite. Stating it here, at the point of decision, is more useful than leaving it to a Settings help-text nobody reads before consenting.
- Declining `caregiver_sharing` here doesn't block the caregiver-invite feature at the UI level — see §3.1's note on how these two interact.
- Revocation copy note, matching Database doc §2.4's own distinction: nothing on this screen claims declining or later revoking deletes past data — "Consent revocation ≠ deletion... different action, different button" (§2.4) is a Settings-screen concern (a separate "Delete my data" affordance), out of scope for this onboarding screen, which only ever writes forward-looking grants.

### 2.6 Screen: Done

```
┌─────────────────────────────────────┐
│  You're all set                      │
│                                       │
│  ✓ Parkinson's care plan             │
│  ✓ 2 medications added               │
│  ✓ Text check-ins                    │
│  ✓ Your data choices saved           │
│                                       │
│  [ Go to Today ]                     │
└─────────────────────────────────────┘
```

A neutral factual summary, not a verdict — same discipline as PRODUCT_UX_DESIGN.md §6's "state a neutral fact, never a status verdict" rule for the Trends screen, applied here: this is a checklist of what was recorded, not an "You're ready! 🎉" tone that overclaims. No confetti/celebration animation (§9's Lovi audit already rejected that pattern on `reduced-motion` grounds; the same reasoning applies to this screen).

---

## 3. Caregiver Invite Flow

### 3.1 Patient side: where it lives, and what it does

Lives behind the profile icon (top-right header, `overflow-menu` pattern) per PRODUCT_UX_DESIGN.md §3.1's existing placement of Settings — "Settings still live behind the profile icon... settings, legal, log out are not tab-worthy." Caregiver management is a settings-shaped, low-frequency action, not a primary-nav-worthy one, so it's a row inside that same menu: **Settings → Caregivers**.

```
Settings → Caregivers
┌─────────────────────────────────────┐
│  ← Back              Caregivers      │
│                                       │
│  People who can see your adherence,  │
│  alerts, and trends. Never your      │
│  private chats with your Care Agent. │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ David M.            Active   │     │
│  │ Family caregiver             │     │
│  │                    [ Remove ]│     │
│  └─────────────────────────────┘     │
│                                       │
│  ┌─────────────────────────────┐     │
│  │ jane@example.com    Pending  │     │
│  │ Invited 2 days ago            │     │
│  │                    [ Cancel ]│     │
│  └─────────────────────────────┘     │
│                                       │
│  [ + Invite a caregiver ]            │
└─────────────────────────────────────┘
```

- Same "never your private chats" boundary line as the consent screen (§2.5) — repeated deliberately, not redundantly: this is the second point in the product where a patient might reasonably wonder what a caregiver can see, and both should say the same thing (consistency of a compliance-critical claim across screens matters more than avoiding repetition).
- **Interaction with `caregiver_sharing` consent (§2.5):** if the patient declined `caregiver_sharing` during onboarding (or later revoked it in Settings), the `[ + Invite a caregiver ]` action is still visible but leads to an interstitial rather than silently failing or silently re-granting consent on the invite screen: `"You've turned off caregiver sharing. Turn it back on to invite someone. [ Go to data choices ]"` — routes to the same toggle in Settings. This keeps the two features consistent without conflating an invite action with a consent grant (a caregiver invite screen that also flips a compliance-relevant toggle as a side effect would bury that toggle exactly the way §2.5 is designed not to).

```
Invite a caregiver
┌─────────────────────────────────────┐
│  ← Back      Invite a caregiver      │
│                                       │
│  Their email                         │
│  ┌─────────────────────────────┐ 🎤 │
│  └─────────────────────────────┘     │
│                                       │
│  We'll send them a link to connect   │
│  to your account. They'll be able    │
│  to see your adherence, alerts, and  │
│  trends — never your private chats.  │
│                                       │
│  [ Send invite ]                     │
└─────────────────────────────────────┘

→ success:
┌─────────────────────────────────────┐
│  ✓ Invite sent                       │
│  We sent a link to jane@example.com. │
│  It's good for 7 days.               │
│  [ Done ]                            │
└─────────────────────────────────────┘
```

- Maps to `POST /api/v1/patients/{patient_id}/caregiver-invites {email, role: "family"}` (AUTH_LAYER §6.2 step 1). **No role picker on this screen** — `"clinician"` isn't exposed in MVP UI (AUTH_LAYER §6.2's own note, citing Database doc §2.1's phase-2 comment), so the client always sends `role: "family"` and this screen never asks; adding a role picker later, when clinician accounts exist, is a change to this one screen, not a new one.
- Success card's green checkmark uses the Accent/CTA color (`#059669`, §1 design system) — reserved for "positive/confirm actions (adherence logged, check-in complete)," per §1's own scoping rule, and an invite being sent is exactly that category (a confirmed action, not a medical-fact claim the AI Behavior Contract would need to gate).
- Error states: invite to an email that's already an active caregiver on this account → `"[email] is already connected."`; network failure → same `index.tsx`-pattern honest error card.
- `[ Remove ]` on an active caregiver maps to `DELETE /api/v1/patients/{patient_id}/caregivers/{caregiver_id}` (AUTH_LAYER §6.2 Revocation) — confirmation dialog required before this fires (`"Remove David M.? They'll lose access immediately."`) since AUTH_LAYER's own note is that revocation takes effect on the caregiver's very next request, not gradually — the UI's confirmation copy should say so plainly rather than implying it's reversible or delayed.
- `[ Cancel ]` on a pending invite is a distinct, lower-stakes action (no confirmation dialog needed — nothing has been granted yet) than `[ Remove ]` on an active link; conflating the two copy/interaction patterns would understate what revoking active access actually does.

### 3.2 Caregiver side: accept flow (web, per §0's surface decision)

Both of AUTH_LAYER §6.2's converging paths (4a: no account yet, 4b: existing caregiver account) land on the same `GET /api/v1/caregiver-invites/{token}` lookup and the same "Accept invite" screen shell — the two paths only diverge in which form renders below the invite context.

```
GET /caregiver-invites/{token} → renders:

┌─────────────────────────────────────┐
│  AI Caregiver                        │
│                                       │
│  Sarah has invited you to be her     │
│  family caregiver on AI Caregiver.   │
│                                       │
│  As her caregiver, you'll be able    │
│  to see her medication adherence,    │
│  symptom trends, and get alerts if   │
│  something needs attention. You      │
│  won't see her private conversations │
│  with her Care Agent.                │
│                                       │
│  [ path 4a or 4b form renders here ] │
└─────────────────────────────────────┘
```

- **Patient context shown: first name only** — AUTH_LAYER §6.2 step 3 explicitly left this to this doc ("shows inviting patient context (first name only, or whatever minimal context the Product/UX flow wants — not specified here, flag for that doc)"). First-name-only is the call made here: enough for the invitee to recognize who's inviting them (they were very likely just contacted directly and told to expect this), without putting a full name or any clinical detail into a link that could be forwarded, land in a shared inbox, or be opened on a shared device before the invitee has authenticated. Full name and any other detail become visible only after the invite is accepted and the caregiver is looking at an authenticated Dashboard.
- The scope explanation ("you'll be able to see... you won't see...") repeats the same boundary claim as §2.5 and §3.1 a third time, on the one screen an invitee sees *before* they've had any other chance to learn it — this is the version of that sentence most likely to actually be read, since it's the only content on an otherwise-empty screen.

**Path 4a — no account yet:**

```
Create your caregiver account
Email (pre-filled from invite, editable... but see note)
┌─────────────────────────────────────┐
└─────────────────────────────────────┘
Password
┌─────────────────────────────────────┐
└─────────────────────────────────────┘
Confirm password
┌─────────────────────────────────────┐
└─────────────────────────────────────┘
[ Create account & connect ]
```

- Same field-level rules as patient registration (§1.3): no voice on password fields, show/hide toggle, inline validation.
- The email field is pre-filled from the invite but **editable is misleading to offer at all** — AUTH_LAYER §6.2 step 5a is explicit: "the registration payload's `email` must equal the invite's `email` (case-insensitive) — reject with 400 otherwise, before creating any row." Editing the field would just produce a guaranteed rejection after the user has already filled in a password. **Correction to the wireframe above: the email field is shown but disabled/read-only**, with a one-line note — `"This invite was sent to this address. To use a different email, ask [patient] to resend the invite."` — surfacing the constraint before submission, not as a 400 error after.
- Maps to `POST /api/v1/auth/register/caregiver {email, password, invite_token}` (AUTH_LAYER §6.2 step 4a / Implementation Handoff §9 step 5) — one call performs account creation and link acceptance together, per the architect's spec; the UI doesn't need a second step or a spinner-then-spinner sequence, just one submit and one destination.

**Path 4b — already has a caregiver account:**

```
Already have an account?
Email
┌─────────────────────────────────────┐
└─────────────────────────────────────┘
Password
┌─────────────────────────────────────┐
└─────────────────────────────────────┘
[ Log in & connect ]

(link below the 4a form: "Already have an account? Log in instead" —
 swaps the rendered form without leaving the page or losing the invite
 token from the URL)
```

- Login here uses standard `POST /api/v1/auth/login`, then, on success, `POST /api/v1/caregiver-invites/{token}/accept` (AUTH_LAYER §6.2 step 4b) — two calls, sequenced by the client, both before the caregiver ever sees the Dashboard.
- AUTH_LAYER §6.2 step 5a(4b): "the authenticated caregiver's `caregiver_credentials.email` must equal the invite's `email`." If it doesn't match (the invitee logs into a *different* existing caregiver account than the one the invite was addressed to), the accept call fails — honest error, not a silent no-op: `"This invite was sent to a different email than the account you just logged into. Log out and try again with [invite email], or ask [patient] to resend it to the right address."`

**Shared error/edge states (either path), all honest per the `index.tsx` precedent — no generic "Something went wrong" for any of these:**

| State | Copy |
| --- | --- |
| Token expired (`caregiver_invites.status='expired'` or `expires_at` past) | `"This invite has expired. Ask [patient] to send a new one."` |
| Token already accepted | `"This invite has already been used. [ Log in ]"` |
| Token revoked (patient cancelled it, §3.1's `[ Cancel ]`) | `"This invite is no longer available. Ask [patient] to send a new one."` |
| Malformed/unknown token | `"We couldn't find this invite. Double-check the link, or ask [patient] to resend it."` |
| Network/server unreachable | Same `index.tsx`-pattern card: real error detail + retry, not a spinner that dies silently. |

### 3.3 First login: what the caregiver sees

Immediately after either path's accept transaction completes, the caregiver lands on the Caregiver Portal Dashboard (PRODUCT_UX_DESIGN.md §3.2) — but a brand-new caregiver's Dashboard has exactly one linked patient and zero history to show yet, so the generic "30-second status check" row-per-patient layout needs a first-run variant, not a silently empty table:

```
┌─────────────────────────────────────────────┐
│  Dashboard                                    │
│                                                │
│  ✓ You're now connected to Sarah's account.   │
│                                                │
│  ┌─────────────────────────────────────┐      │
│  │ Sarah                                 │      │
│  │ No check-ins logged yet.              │      │
│  │ You'll see her adherence and alerts   │      │
│  │ here as she starts using the app.     │      │
│  └─────────────────────────────────────┘      │
└─────────────────────────────────────────────┘
```

- The "connected" confirmation banner is a one-time, dismissable strip on this first visit only (not a permanent Dashboard fixture) — same "state a fact, don't dress it as a verdict" discipline as §2.6's onboarding-complete screen and PRODUCT_UX_DESIGN.md §6's Trends framing rule, applied to a compliance-adjacent event (an access grant) rather than a clinical one, but the same principle: confirm what happened, don't editorialize about it.
- This state only occurs when the patient hasn't logged anything yet (a caregiver invited very early, e.g. during the patient's own onboarding). A caregiver joining later, once real data exists, skips straight to the normal per-patient row from PRODUCT_UX_DESIGN.md §3.2 — this variant is specifically the zero-data case, not a permanent alternate layout.

---

## 4. Component Inventory Additions

Extends PRODUCT_UX_DESIGN.md §7's table — new components introduced by this doc:

| Component | Used in | Accessibility notes |
| --- | --- | --- |
| Single-screen auth form (email + password, inline validation) | Register, Login | Voice on email only, never password fields (§1.3); show/hide password toggle ≥44×44pt |
| Honest auth error card | Register, Login, Password reset, Invite accept | Real error text per `index.tsx` precedent, except account-enumeration-sensitive states (§1.4) which stay intentionally generic — screen-reader announced on appearance |
| OTP code entry (6 digit boxes) | Password reset | Voice-alternative with read-back confirmation before submit |
| Confirmation-only selection screen (no real choice, single affirm action) | Onboarding disease confirmation (§2.2) | Explicitly not a picker component — reused if/when AD/MS go active and this screen becomes a real picker |
| Single-tap preference row (no Continue button, selection = advance) | Onboarding comm-preference (§2.3), Today mood row (existing, §3.1a) | Matches existing shipped pattern in `index.tsx`; no new interaction model introduced |
| Repeating add-item sub-flow (add one / add another loop) | Onboarding medications (§2.4) | Voice input on name field requires read-back confirmation (medication-name transcription risk, §2.4) |
| Multi-section toggle screen (independently labeled, independently switched) | Onboarding consent (§2.5) | Each section is its own labeled region for screen readers, not one long form — a screen reader user must be able to tell which toggle they're on without scrolling context |
| Caregiver list row (active / pending states, distinct actions) | Settings → Caregivers (§3.1) | `[ Remove ]` (active) requires confirmation dialog; `[ Cancel ]` (pending) does not — different stakes, different interaction weight |
| Invite-accept shell (shared context header, swappable form body) | Caregiver accept, both paths (§3.2) | Path switch (4a ↔ 4b) preserves the invite token in the URL/state, never re-fetches or loses invite context on toggle |
| First-run Dashboard state (zero-data variant) | Caregiver Portal Dashboard, first login only (§3.3) | One-time dismissable banner, not a permanent empty-state fixture |

---

## 5. Open Items

1. **Password reset backend contract doesn't exist yet.** AUTH_LAYER.md names no `forgot-password`/`reset-password` endpoints. §1.5 above specs a UI (in-app OTP code, not an email deep link) and states the reasoning, but this is a proposal for the architect/Backend Dev to confirm, adjust, or override — not a restatement of an agreed contract.
2. **Caregiver mobile-native app scope is inconsistent between two existing docs.** ARCHITECTURE.md §3's front-end row lists "React Native (patient + caregiver mobile)"; PRODUCT_UX_DESIGN.md §3.2 scopes the Caregiver Portal as web-only with a mobile-web degradation requirement; no `caregiver-app/` codebase exists in the repo. This doc specs caregiver invite-accept and first-login against the web-only model (§0, §3.2). If a caregiver native app is actually in scope, a follow-up native accept screen needs specifying — flagging for whoever owns ARCHITECTURE.md next, since resolving that ambiguity isn't this doc's call to make unilaterally.
3. **Medication-name voice transcription confirmation (§2.4)** is a narrow, in-line mitigation, not a resolution of PRODUCT_UX_DESIGN.md §8's existing Open Item #1 (full voice UI spec — wake phrase, confirmation pattern, error recovery). That broader pass still needs to happen once a voice framework/vendor is chosen.
4. **Password policy and account-lockout thresholds** are AUTH_LAYER §2.2's explicit implementation detail for the Backend Dev. This doc's copy ("8+ characters," "too many attempts... try again in a few minutes") is placeholder UI shape, not the asserted real policy — needs reconciling once those numbers exist.
5. **Clinician-role invites** are out of scope for this doc, matching AUTH_LAYER §6.2's own MVP scoping (`clinician` role exists in the schema, not exposed in UI). §3.1's invite screen only ever sends `role: "family"`.
6. **Caregiver's own ToS/privacy-policy acceptance at registration** is not addressed anywhere in this doc or any doc it depends on. Database doc §2.4's consent model is patient-scoped only (`consent_records.patient_id`, no caregiver equivalent) — whether caregivers need a distinct acceptance step at account creation is genuinely unaddressed, not just deferred.
7. **Multi-caregiver UI** — Database doc §2.1 notes the schema already supports more than one active `patient_caregiver_links` row per patient, but PRD scopes multi-caregiver support as Future/Fast-Follow. §3.1's list-row design (§3.1, §4 table) will read fine with two or three rows, but hasn't been stress-tested against "many caregivers" information density — revisit when that feature actually ships.
8. **Caregiver Portal responsive breakpoints** — still open per PRODUCT_UX_DESIGN.md §8 item 2; this doc's invite-accept web screens (§3.2) inherit the same unresolved pixel-value gap, since they render inside the same portal shell.
9. **`preferred_comm_mode` sequencing (§1.3) needs Backend Dev sign-off — narrower than it first looked.** `disease_code` is *not* deferred: it's a hardcoded constant for the entire MVP (§2.2), so it rides in the original single `register/patient` call exactly as AUTH_LAYER §6.1 specifies, no transaction change needed. `preferred_comm_mode` is the one field this doc genuinely defers — it's a real per-user choice the user hasn't made yet at the moment the account is created (§2.3), so it's sent later as a targeted `PATCH` to the already-created patient record once the user reaches that onboarding screen, not folded into a second full "onboarding-completion" endpoint. This is a small, single-field seam against AUTH_LAYER §6.1's transaction shape, not a restructuring of it — flagging for the Backend Dev currently implementing that spec, since it's the one place this doc's sequencing diverges from what's already being built.
10. **AD/MS disease-confirmation screen redesign trigger** — noted inline at §2.2: when Phase 2/3 activates a second `disease_profiles` row, that screen changes from a confirmation (and its silent hardcoded payload) to a real picker with its own registration-payload field again. No design work is proposed for that picker here since it's not needed until that milestone; flagged so it isn't forgotten as a silent scope gap later.
11. **`symptom_data` defaulting to on (§2.5) needs the same legal/compliance review this project already applies to comparable calls** (PRD Open Risks #1 FDA classification, #2 BAA confirmation). The design reasoning in §2.5 — disclosed consequence, genuinely revocable, not a hidden/pre-checked box — is a UX argument for why this isn't a dark pattern; it is not a substitute for legal sign-off on whether a pre-defaulted-on consent toggle, even a disclosed and revocable one, satisfies GDPR Art. 7(4)'s "freely given" standard given PRD's explicit GDPR-compliance business goal. This is exactly the kind of call the task itself flags as "a compliance requirement per PRD, not a nice-to-have" — surfacing it here rather than leaving the judgment implicit in §2.5's reasoning alone.

---

*Sibling doc: [PRODUCT_UX_DESIGN.md](./PRODUCT_UX_DESIGN.md) §10 points here. Depends on [AUTH_LAYER.md](../02-Software-Architecture/AUTH_LAYER.md) for the API contracts referenced throughout; §5 items 1 and 9 above are the two places this doc's UI design implies a change to that contract rather than just consuming it as given.*
