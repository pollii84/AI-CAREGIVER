import Header from "@/components/Header";
import Footer from "@/components/Footer";

const FEATURES = [
  {
    title: "Daily check-ins",
    body: "A short, structured check-in each morning — voice or text. Built for tremor and low-motor-skill days, not just good ones.",
  },
  {
    title: "Medication reminders",
    body: "Reminders tied to your actual schedule, with adherence tracked automatically so nothing gets lost in the shuffle.",
  },
  {
    title: "AI Care Agent",
    body: "Ask a question, get a sourced answer — every claim is cited, every answer is logged. Never a diagnosis, never a dosing suggestion.",
  },
  {
    title: "Caregiver alerts",
    body: "A 30-second status check for the people who care about you: adherence, recent check-ins, anything that needs attention now.",
  },
];

export default function Home() {
  return (
    <>
      <Header />
      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 pt-20 pb-16 text-center">
          <h1 className="font-[family-name:var(--font-heading)] text-4xl sm:text-5xl font-bold tracking-tight text-[var(--color-foreground)] max-w-3xl mx-auto">
            Quality of life, tracked every day — not just at the next appointment.
          </h1>
          <p className="mt-6 text-lg text-[var(--color-foreground)]/80 max-w-2xl mx-auto">
            AI Caregiver helps people living with Parkinson&rsquo;s — and the
            family who supports them — track symptoms, stay on top of
            medication, and get clear, sourced answers, every day.
          </p>

          {/* NOTE: form is intentionally disabled, not fake-functional — no
              waitlist-capture endpoint exists yet. Wire this to a real
              backend route before removing `disabled`; don't ship a form
              that silently swallows submissions. */}
          <form
            id="notify"
            className="mt-10 mx-auto flex max-w-md flex-col sm:flex-row gap-3 scroll-mt-24"
            aria-describedby="notify-status"
          >
            <label htmlFor="notify-email" className="sr-only">
              Email address
            </label>
            <input
              id="notify-email"
              type="email"
              disabled
              placeholder="you@example.com"
              className="flex-1 rounded-full border border-[var(--color-border)] bg-white px-5 py-3 text-sm disabled:opacity-60"
            />
            <button
              type="submit"
              disabled
              className="rounded-full bg-[var(--color-primary)] px-6 py-3 text-sm font-medium text-[var(--color-on-primary)] disabled:opacity-60"
            >
              Notify me at launch
            </button>
          </form>
          <p id="notify-status" className="mt-3 text-sm text-[var(--color-foreground)]/60">
            Coming soon to the App Store — waitlist opens shortly.
          </p>
        </section>

        {/* Compliance strip — keep this honest and above the fold; PRD Non-Goals
            and Open Risk #1 both hinge on never reading as diagnostic. */}
        <section className="border-y border-[var(--color-border)] bg-[var(--color-muted)]">
          <p className="mx-auto max-w-3xl px-6 py-4 text-center text-sm text-[var(--color-foreground)]/80">
            AI Caregiver does not diagnose and does not replace your
            neurologist. It&rsquo;s a tool for tracking your own logged
            history and staying informed — always talk to your care team
            about anything specific to you.
          </p>
        </section>

        {/* Features */}
        <section id="features" className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="font-[family-name:var(--font-heading)] text-3xl font-bold text-center text-[var(--color-foreground)]">
            Built around a hard day, not a good one
          </h2>
          <div className="mt-12 grid gap-8 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-[var(--color-border)] bg-white p-6"
              >
                <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold text-[var(--color-foreground)]">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm text-[var(--color-foreground)]/75">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* For families */}
        <section id="families" className="bg-[var(--color-primary)] text-[var(--color-on-primary)]">
          <div className="mx-auto max-w-4xl px-6 py-20 text-center">
            <h2 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
              For the person diagnosed — and the people who show up for them
            </h2>
            <p className="mt-6 text-lg text-[var(--color-on-primary)]/90">
              Sarah gets a simple, voice-enabled check-in every morning. Her
              partner David sees her adherence and gets an alert the moment
              a dose is missed — before it becomes a bigger problem. Same
              app, two very different jobs to do.
            </p>
          </div>
        </section>

        {/* Roadmap — sets correct expectations, matches PRD Scope & Sequencing */}
        <section className="mx-auto max-w-4xl px-6 py-20 text-center">
          <h2 className="font-[family-name:var(--font-heading)] text-2xl font-bold text-[var(--color-foreground)]">
            Starting with Parkinson&rsquo;s. Built to grow.
          </h2>
          <p className="mt-4 text-[var(--color-foreground)]/75">
            We&rsquo;re launching focused on Parkinson&rsquo;s disease first,
            validating with real patients before expanding to
            Alzheimer&rsquo;s and MS on the same foundation.
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
