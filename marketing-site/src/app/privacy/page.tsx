import Header from "@/components/Header";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — AI Caregiver",
};

export default function PrivacyPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-6 py-16">
          <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold text-[var(--color-foreground)]">
            Privacy Policy
          </h1>
          <p className="mt-4 rounded-lg border border-[var(--color-destructive)] bg-red-50 p-4 text-sm text-[var(--color-destructive)]">
            Placeholder — not legal advice, not reviewed by counsel. A real
            policy is required before App Store submission and before any
            real patient data is collected (PRD, Open Risks #1: FDA/legal
            review is a blocking dependency, not a formality).
          </p>

          <div className="mt-8 space-y-6 text-[var(--color-foreground)]/85">
            <p>
              This placeholder outlines the data categories the product is
              designed to handle, per the consent model in{" "}
              <code className="text-sm">04-Database/DATABASE_DESIGN.md §2.4</code>.
              The real policy must cover each of these explicitly, plus
              HIPAA/GDPR obligations once a BAA is confirmed (PRD, Open
              Risks #2).
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Symptom and check-in data</li>
              <li>Fall/location data (sensor-derived, phase 1.5+)</li>
              <li>Research personalization data</li>
              <li>Caregiver-sharing permissions</li>
              <li>Literature/trial digest personalization</li>
            </ul>
            <p>
              Every category above is individually consentable and
              revocable within the product itself — see{" "}
              <code className="text-sm">04-Database/DATABASE_DESIGN.md §6</code>{" "}
              for the deletion-request flow.
            </p>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
