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
      initial={{ opacity: 0, y: 60 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }} // Smooth spring-like ease
      className="w-full"
    >
      {children}
    </motion.div>
  );
}
