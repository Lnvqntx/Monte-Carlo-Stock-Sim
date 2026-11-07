import { Card } from "./ui";

function Formula({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <figure className="my-4 overflow-x-auto rounded-xl border border-sand/10 bg-forest-950/60 px-4 py-3.5">
      <figcaption className="mb-1.5 text-[0.6875rem] font-medium uppercase tracking-[0.14em] text-sand/50">{label}</figcaption>
      <p className="whitespace-nowrap font-serif text-[1.0625rem] italic tracking-wide text-sand">{children}</p>
    </figure>
  );
}

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="mx-auto mt-20 max-w-6xl scroll-mt-6 px-4 pb-20 sm:mt-28 sm:px-6">
      <div className="max-w-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-sand/55">Under the hood</p>
        <h2 id="how-title" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
          How it works
        </h2>
        <p className="mt-4 text-pretty leading-relaxed text-sand/70">
          Nobody knows where a stock will go. Instead of one forecast, this tool plays out thousands of
          plausible futures and shows you how they spread out.
        </p>
      </div>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        <Card className="p-6 sm:p-7">
          <p className="text-sm font-semibold text-sand/55">01</p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight">A model of random prices</h3>
          <p className="mt-3 text-sm leading-relaxed text-sand/70">
            Geometric Brownian motion (GBM) treats a price as a steady trend (the drift, μ) plus random
            shocks whose size is set by volatility, σ. Shocks compound in percentage terms, so prices stay
            positive and big moves get bigger as the price grows.
          </p>
          <Formula label="GBM">
            dS = μ S dt + σ S dW
          </Formula>
          <p className="text-sm leading-relaxed text-sand/70">
            Each simulated trading day (Δt = 1/252 year) applies the exact solution with a fresh random draw
            Z from a standard normal distribution:
          </p>
          <Formula label="One step">
            S<sub>t+Δt</sub> = S<sub>t</sub> · exp( (μ − σ²⁄2) Δt + σ √Δt · Z )
          </Formula>
        </Card>

        <Card className="p-6 sm:p-7">
          <p className="text-sm font-semibold text-sand/55">02</p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight">Learning μ and σ from history</h3>
          <p className="mt-3 text-sm leading-relaxed text-sand/70">
            We download daily closing prices over the lookback window (2 years by default) and turn them into
            daily log returns, r = ln(P<sub>t</sub> / P<sub>t−1</sub>). Then we annualize:
          </p>
          <Formula label="Volatility">σ = stdev(r) × √252</Formula>
          <Formula label="Drift">μ = mean(r) × 252 + σ²⁄2</Formula>
          <p className="text-sm leading-relaxed text-sand/70">
            The starting price is the latest close. The same seed and settings always reproduce the same paths.
          </p>
        </Card>

        <Card className="p-6 sm:p-7">
          <p className="text-sm font-semibold text-sand/55">03</p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight">Monte Carlo: many futures at once</h3>
          <p className="mt-3 text-sm leading-relaxed text-sand/70">
            We repeat the daily step for every trading day in your horizon, across 10,000 independent paths
            by default. Instead of one guess you get a distribution, and from it:
          </p>
          <ul className="mt-4 space-y-2.5 text-sm leading-relaxed text-sand/70">
            <li><span className="font-semibold text-sand">Expected price</span>: the average final price across all paths.</li>
            <li><span className="font-semibold text-sand">Probability of loss</span>: the share of paths ending below today&apos;s price.</li>
            <li><span className="font-semibold text-sand">95% VaR</span>: the loss at the 5th-percentile outcome. 1 path in 20 does worse.</li>
            <li><span className="font-semibold text-sand">Bands</span>: at each day, the range holding the middle 50% and 90% of paths.</li>
          </ul>
        </Card>

        <Card className="p-6 sm:p-7">
          <p className="text-sm font-semibold text-sand/55">04</p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight">Honest limitations</h3>
          <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-sand/70">
            <li><span className="font-semibold text-sand">Constant volatility.</span> Real markets have calm spells and storms; GBM uses one σ throughout.</li>
            <li><span className="font-semibold text-sand">Normal returns.</span> Real returns have fat tails: crashes and spikes happen more often than the model expects, so the true downside is likely worse.</li>
            <li><span className="font-semibold text-sand">Historical drift is noisy.</span> A strong past run produces a large μ that may not repeat. Drift is the least reliable input, so read the spread, not the mean.</li>
            <li><span className="font-semibold text-sand">No news, dividends or events.</span> Earnings, splits and macro shocks aren&apos;t modelled.</li>
          </ul>
          <p className="mt-5 rounded-xl border border-sand/12 bg-forest-950/50 px-4 py-3 text-sm font-medium text-sand/85">
            This is an educational model, not financial advice. Don&apos;t make investment decisions based on it.
          </p>
        </Card>
      </div>
    </section>
  );
}
