import { GitHubIcon } from "./icons";
import { REPO_URL } from "./SiteHeader";

export function Footer() {
  return (
    <footer className="border-t border-sand/10 bg-forest-950/40">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-sand/60 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>Model output for education only. Not financial advice.</p>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 self-start rounded-lg text-sand/80 transition-colors hover:text-sand sm:self-auto"
        >
          <GitHubIcon className="size-4" />
          Lnvqntx/Monte-Carlo-Stock-Sim
        </a>
      </div>
    </footer>
  );
}
