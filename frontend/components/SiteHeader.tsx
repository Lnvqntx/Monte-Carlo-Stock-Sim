import { GitHubIcon, LogoMark } from "./icons";

export const REPO_URL = "https://github.com/Lnvqntx/Monte-Carlo-Stock-Sim";

export function SiteHeader() {
  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
      <a href="#" className="flex items-center gap-2.5 rounded-lg text-sm font-semibold tracking-tight">
        <LogoMark className="size-8" />
        <span>Monte Carlo</span>
      </a>
      <nav aria-label="Site" className="flex items-center gap-1 text-sm text-sand/75">
        <a href="#how-it-works" className="rounded-lg px-3 py-2 transition-colors hover:text-sand">
          How it works
        </a>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-lg px-3 py-2 transition-colors hover:text-sand"
        >
          <GitHubIcon className="size-4" />
          <span className="hidden sm:inline">GitHub</span>
          <span className="sr-only sm:hidden">GitHub repository</span>
        </a>
      </nav>
    </header>
  );
}
