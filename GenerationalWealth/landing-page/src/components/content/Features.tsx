"use client";

import { motion } from "framer-motion";
import { Activity, Users, BarChart3, Zap, Shield, Globe } from "lucide-react";

const features = [
  {
    icon: <Activity className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Real-time Data",
    description: "Millisecond precision market data streaming directly to your terminal. Never miss a tick.",
  },
  {
    icon: <Users className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Multi-user Workspaces",
    description: "Collaborate with your team in real-time. Share layouts, analysis, and portfolios instantly.",
  },
  {
    icon: <BarChart3 className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Advanced Charts",
    description: "Institutional-grade charting with over 100+ technical indicators and drawing tools.",
  },
  {
    icon: <Zap className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Lightning Execution",
    description: "Direct market access routing ensures your trades are executed at the absolute best prices.",
  },
  {
    icon: <Shield className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Bank-grade Security",
    description: "End-to-end encryption, multi-factor authentication, and cold storage for all assets.",
  },
  {
    icon: <Globe className="w-6 h-6 text-neutral-400 group-hover:text-white transition-colors" />,
    title: "Global Markets",
    description: "Access 50+ global exchanges across equities, options, futures, and digital assets.",
  },
];

export function Features() {
  return (
    <section className="py-24 bg-black relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-neutral-800/20 rounded-full blur-[120px] pointer-events-none" />
      
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-3xl md:text-4xl font-medium tracking-tight text-white mb-4"
          >
            The ultimate terminal for the modern firm.
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="text-neutral-400 text-lg"
          >
            Built for speed, reliability, and unparalleled insight. Experience the future of financial software.
          </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="group p-8 rounded-2xl bg-neutral-900/40 border border-neutral-800 hover:border-neutral-700 transition-colors glass relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-b from-neutral-800/0 to-neutral-800/20 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative z-10">
                <div className="w-12 h-12 rounded-xl bg-neutral-800/50 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-neutral-800 transition-all duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-medium text-white mb-3 group-hover:text-white transition-colors">{feature.title}</h3>
                <p className="text-neutral-400 leading-relaxed group-hover:text-neutral-300 transition-colors">
                  {feature.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
