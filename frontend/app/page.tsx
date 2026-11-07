import { BackgroundGlow } from "@/components/BackgroundGlow";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Simulator } from "@/components/Simulator";
import { SiteHeader } from "@/components/SiteHeader";

export default function Home() {
  return (
    <div className="relative isolate flex min-h-full flex-col overflow-x-clip">
      <BackgroundGlow />
      <div aria-hidden className="bg-dots pointer-events-none absolute inset-x-0 top-0 -z-10 h-[56rem] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <a
        href="#simulator"
        className="sr-only z-50 rounded-lg bg-forest-950 px-4 py-2 focus:not-sr-only focus:absolute focus:left-4 focus:top-4"
      >
        Skip to simulator
      </a>
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <Simulator />
        <HowItWorks />
      </main>
      <Footer />
    </div>
  );
}
