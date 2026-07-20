"use client";

import { motion } from "framer-motion";
import { SiRevolut, SiBinance, SiCoinbase, SiStripe, SiRobinhood } from "react-icons/si";

const brokers = [
  { name: "Trade Republic", icon: <img src="https://cdn.brandfetch.io/id5mURhE1s/theme/light/symbol.svg?c=1bxid64Mup7aczewSAYMX&t=1695070245727" alt="Trade Republic logo" className="w-8 h-8 object-contain drop-shadow-[0_0_10px_rgba(255,255,255,0.4)]" /> },
  { name: "Revolut", icon: <SiRevolut className="w-8 h-8 text-black bg-white rounded-md p-1 shadow-[0_0_10px_rgba(255,255,255,0.4)]" /> },
  { name: "Interactive Brokers", icon: <img src="https://cdn.brandfetch.io/idcABCQwX-/w/400/h/400/theme/dark/icon.jpeg?c=1bxid64Mup7aczewSAYMX&t=1667570681287" alt="Interactive Brokers logo" className="w-8 h-8 object-contain rounded-md shadow-[0_0_10px_rgba(220,38,38,0.4)]" /> },
  { name: "Robinhood", icon: <SiRobinhood className="w-8 h-8 text-[#00c805] drop-shadow-[0_0_10px_rgba(0,200,5,0.5)]" /> },
  { name: "Binance", icon: <SiBinance className="w-8 h-8 text-[#fcd535] drop-shadow-[0_0_10px_rgba(252,213,53,0.5)]" /> },
  { name: "Coinbase", icon: <SiCoinbase className="w-8 h-8 text-[#0052ff] drop-shadow-[0_0_10px_rgba(0,82,255,0.5)]" /> },
  { name: "Stripe", icon: <SiStripe className="w-10 h-10 text-[#635bff] drop-shadow-[0_0_10px_rgba(99,91,255,0.5)]" /> },
];

export function Integrations() {
  // Duplicate array to create a seamless infinite loop
  const duplicatedBrokers = [...brokers, ...brokers, ...brokers];

  return (
    <section className="py-12 border-y border-neutral-800/50 bg-neutral-950/30 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 mb-8 text-center">
        <p className="text-sm font-medium text-neutral-500 tracking-wider uppercase">
          Connect directly to over 50+ brokers and banks
        </p>
      </div>
      
      <div className="relative w-full flex overflow-hidden">
        {/* Fade masks */}
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-black to-transparent z-10" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-black to-transparent z-10" />
        
        {/* Infinite scrolling track */}
        <motion.div
          animate={{ x: [0, -1920] }} // Adjust depending on content width
          transition={{
            repeat: Infinity,
            ease: "linear",
            duration: 30, // Slow, steady scroll
          }}
          className="flex items-center gap-16 md:gap-24 w-max px-8"
        >
          {duplicatedBrokers.map((broker, i) => (
            <div 
              key={i} 
              className="flex items-center gap-3 text-neutral-300 hover:text-white transition-all duration-300 hover:scale-105 cursor-pointer"
            >
              {broker.icon}
              <span className="text-2xl font-bold tracking-tight">{broker.name}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
