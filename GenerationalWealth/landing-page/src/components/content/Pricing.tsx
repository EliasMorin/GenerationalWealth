"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Standard",
    price: "$2,400",
    interval: "per user/month",
    description: "For individual traders and small boutique firms.",
    features: [
      "Real-time US equities & options",
      "Standard charting package",
      "Up to 2 connected brokerages",
      "Email support",
    ],
    highlight: false,
  },
  {
    name: "Enterprise",
    price: "$4,800",
    interval: "per user/month",
    description: "For institutions requiring global access and prime services.",
    features: [
      "Global real-time market data",
      "Advanced institutional charting",
      "Unlimited brokerage connections",
      "Multi-user workspaces",
      "API access (10k req/min)",
      "24/7 dedicated phone support",
    ],
    highlight: true,
  },
];

export function Pricing() {
  return (
    <section className="py-24 bg-black relative overflow-hidden">
      <div className="max-w-5xl mx-auto px-6 relative z-10">
        <div className="text-center mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-3xl md:text-4xl font-medium tracking-tight text-white mb-4"
          >
            Transparent pricing. Institutional grade.
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="text-neutral-400 text-lg"
          >
            Select the tier that aligns with your firm's requirements.
          </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 + 0.1 }}
              whileHover={{ y: -8, transition: { duration: 0.2 } }}
              className={`relative p-8 rounded-3xl border glass flex flex-col ${
                plan.highlight 
                  ? "bg-neutral-900/40 border-neutral-600 shadow-[0_0_40px_-10px_rgba(255,255,255,0.05)]" 
                  : "bg-neutral-900/10 border-neutral-800"
              }`}
            >
              {plan.highlight && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-4/5 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />
              )}
              
              <div className="mb-8">
                <h3 className="text-xl font-medium text-white mb-2">{plan.name}</h3>
                <p className="text-neutral-400 h-10">{plan.description}</p>
              </div>

              <div className="mb-8 flex items-baseline">
                <span className="text-5xl font-medium text-white tracking-tight">{plan.price}</span>
                <span className="text-neutral-500 ml-2 text-sm">{plan.interval}</span>
              </div>

              <ul className="space-y-4 mb-8 flex-1">
                {plan.features.map((feature, j) => (
                  <li key={j} className="flex items-center text-neutral-300">
                    <Check className="w-5 h-5 text-neutral-400 mr-3 shrink-0" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <button className={`w-full py-4 rounded-xl font-medium transition-all text-sm ${
                plan.highlight
                  ? "bg-white text-black hover:bg-neutral-200"
                  : "bg-neutral-800 text-white hover:bg-neutral-700"
              }`}>
                Get Started
              </button>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
