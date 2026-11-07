export function Hero() {
  return (
    <section className="relative mx-auto max-w-6xl px-4 pb-10 pt-10 text-center sm:px-6 sm:pb-14 sm:pt-16">
      <div aria-hidden className="hero-glow pointer-events-none absolute left-1/2 top-0 -z-10 h-[30rem] w-[min(56rem,140vw)] -translate-x-1/2 -translate-y-1/4" />
      <p className="inline-flex items-center gap-2 rounded-full border border-sand/15 bg-forest-950/50 px-3.5 py-1.5 text-xs font-medium tracking-wide text-sand/80 backdrop-blur">
        <span aria-hidden className="size-1.5 rounded-full bg-accent" />
        GBM · 10,000 simulations
      </p>
      <h1 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
        Monte Carlo Stock Simulator
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-pretty text-base leading-relaxed text-sand/70 sm:text-lg">
        Pick a stock and a horizon. We learn its drift and volatility from history, then simulate
        thousands of possible futures to show the range of outcomes and the downside risk.
      </p>
    </section>
  );
}
