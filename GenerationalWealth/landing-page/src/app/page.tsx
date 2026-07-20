import { Navbar } from "@/components/Navbar";
import { HeroSection } from "@/components/hero/HeroSection";
import { Features } from "@/components/content/Features";
import LiveTerminalPreview from "@/components/data/LiveTerminalPreview";
import { Pricing } from "@/components/content/Pricing";
import { FAQ } from "@/components/content/FAQ";
import { Footer } from "@/components/content/Footer";
import { SectionTransition } from "@/components/ui/SectionTransition";

export default function Home() {
  return (
    <main className="min-h-screen bg-black selection:bg-white/30 selection:text-white">
      <Navbar />
      <HeroSection />
      
      <div className="relative z-10 bg-black pt-24 pb-32 flex flex-col gap-32">
        <SectionTransition>
          <section className="container mx-auto px-4 flex flex-col items-center">
            <div className="text-center mb-12 max-w-2xl mx-auto">
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-4">Live Market Intelligence</h2>
              <p className="text-zinc-400 text-lg">Stream real-time events, insider trades, and technical signals directly to your browser.</p>
            </div>
            <LiveTerminalPreview />
          </section>
        </SectionTransition>
        
        <SectionTransition>
          <Features />
        </SectionTransition>
        
        <SectionTransition>
          <Pricing />
        </SectionTransition>
        
        <SectionTransition>
          <FAQ />
        </SectionTransition>
      </div>
      <Footer />
    </main>
  );
}
