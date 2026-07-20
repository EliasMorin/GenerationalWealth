"use client";

import { motion } from "framer-motion";
import { SiRevolut, SiBinance, SiCoinbase, SiStripe, SiRobinhood } from "react-icons/si";

const brokers = [
  { name: "Trade Republic", icon: <div className="font-bold tracking-tighter text-xl flex items-center gap-1"><span className="w-4 h-4 rounded-full bg-white block" /> Trade Republic</div> },
  { name: "Revolut", icon: <SiRevolut className="w-8 h-8" /> },
  { name: "Interactive Brokers", icon: <div className="font-bold tracking-tighter text-xl flex items-center gap-1"><span className="w-4 h-4 rounded-full bg-red-600 block" /> Interactive Brokers</div> },
  { name: "Robinhood", icon: <SiRobinhood className="w-8 h-8" /> },
  { name: "Binance", icon: <SiBinance className="w-8 h-8" /> },
  { name: "Coinbase", icon: <SiCoinbase className="w-8 h-8" /> },
  { name: "Stripe", icon: <SiStripe className="w-10 h-10" /> },
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
              className="flex items-center gap-3 text-neutral-400 hover:text-white transition-colors duration-300 grayscale hover:grayscale-0 opacity-70 hover:opacity-100 cursor-pointer"
            >
              {broker.icon}
              {broker.name !== "Trade Republic" && (
                <span className="text-xl font-bold tracking-tight">{broker.name}</span>
              )}
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
