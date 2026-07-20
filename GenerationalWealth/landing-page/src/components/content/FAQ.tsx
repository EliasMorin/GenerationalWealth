"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    question: "How does the real-time data compare to Bloomberg?",
    answer: "Our data feeds are sourced directly from the exact same primary exchanges and SIPs, ensuring identical latency and precision. We render this data using WebGL, allowing us to display millions of data points without the UI lag typical of legacy terminals.",
  },
  {
    question: "Can I share my workspace with colleagues?",
    answer: "Yes, multi-user workspaces are a core feature of the Enterprise plan. You can share exact screen layouts, specific charts, or entire portfolios in real-time with a single link.",
  },
  {
    question: "Is there an API available for automated trading?",
    answer: "Absolutely. The Enterprise plan includes REST and WebSocket API access with a baseline limit of 10,000 requests per minute. Dedicated cross-connects are available upon request for high-frequency strategies.",
  },
  {
    question: "How secure is GenerationalWealth?",
    answer: "We employ AES-256 encryption at rest and TLS 1.3 in transit. We require MFA for all accounts and support SSO/SAML integration for enterprise directory management.",
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section className="py-24 bg-black relative">
      <div className="max-w-3xl mx-auto px-6">
        <div className="text-center mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-3xl md:text-4xl font-medium tracking-tight text-white mb-4"
          >
            Frequently asked questions
          </motion.h2>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, i) => {
            const isOpen = openIndex === i;
            return (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={`border transition-colors duration-300 rounded-2xl overflow-hidden glass ${
                  isOpen ? "bg-neutral-900/40 border-neutral-700" : "bg-neutral-900/10 border-neutral-800/80 hover:border-neutral-700"
                }`}
              >
                <button
                  onClick={() => setOpenIndex(isOpen ? null : i)}
                  className="w-full px-6 py-5 flex items-center justify-between text-left focus:outline-none"
                >
                  <span className="font-medium text-white pr-8">{faq.question}</span>
                  <motion.div
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown className={`w-5 h-5 shrink-0 transition-colors ${isOpen ? "text-white" : "text-neutral-500"}`} />
                  </motion.div>
                </button>
                <AnimatePresence>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeInOut" }}
                    >
                      <div className="px-6 pb-6 text-neutral-400 leading-relaxed border-t border-neutral-800/50 pt-4 text-sm">
                        {faq.answer}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
