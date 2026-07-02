import Link from "next/link";

export default function Header() {
  return (
    <header className="border-b border-[var(--color-border)] bg-white/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
        <Link
          href="/"
          className="font-[family-name:var(--font-heading)] text-lg font-bold text-[var(--color-foreground)]"
        >
          AI Caregiver
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <a href="#features" className="hover:text-[var(--color-primary)]">
            Features
          </a>
          <a href="#families" className="hover:text-[var(--color-primary)]">
            For Families
          </a>
          <Link href="/privacy" className="hover:text-[var(--color-primary)]">
            Privacy
          </Link>
          <a
            href="#notify"
            className="rounded-full bg-[var(--color-primary)] px-4 py-2 font-medium text-[var(--color-on-primary)] hover:opacity-90"
          >
            Get notified
          </a>
        </nav>
      </div>
    </header>
  );
}
