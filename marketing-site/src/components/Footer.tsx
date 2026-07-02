import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--color-border)] bg-white">
      <div className="mx-auto max-w-6xl px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-[var(--color-foreground)]/70">
        <p>&copy; {new Date().getFullYear()} AI Caregiver. Not a diagnostic tool.</p>
        <div className="flex gap-6">
          <Link href="/privacy" className="hover:text-[var(--color-primary)]">
            Privacy Policy
          </Link>
          <a href="mailto:hello@aicaregiver.example" className="hover:text-[var(--color-primary)]">
            Contact
          </a>
        </div>
      </div>
    </footer>
  );
}
