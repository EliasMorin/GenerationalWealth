"use client";

import { motion } from "framer-motion";
import React from "react";

export function SectionTransition({ 
  children,
  delay = 0 
}: { 
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }} // Custom easing for that premium SaaS feel
      className="w-full"
    >
      {children}
    </motion.div>
  );
}

export function SectionDivider() {
  return (
    <div className="relative w-full h-px my-16 md:my-32 flex items-center justify-center">
      {/* The line */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />
      {/* The glow in the center */}
      <div className="absolute w-1/4 h-[1px] bg-gradient-to-r from-transparent via-blue-500/50 to-transparent blur-[2px]" />
      <div className="absolute w-12 h-[1px] bg-white/40" />
    </div>
  );
}
