"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface LiquidGlassButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  className?: string;
  glowColor?: string;
}

export function LiquidGlassButton({
  children,
  className,
  glowColor = "rgba(59, 130, 246, 0.5)",
  ...props
}: LiquidGlassButtonProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className={cn(
        "relative group px-8 py-4 rounded-full font-semibold text-lg overflow-hidden transition-all duration-300",
        "bg-white/40 backdrop-blur-md border border-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.05)]",
        "hover:bg-white/60 hover:shadow-[0_8px_32px_rgba(0,0,0,0.1)]",
        className
      )}
      {...(props as any)}
    >
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background: `radial-gradient(circle at center, ${glowColor} 0%, transparent 70%)`,
          mixBlendMode: "overlay",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-tr from-white/10 to-white/50 opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
      <span className="relative z-10 text-slate-800 group-hover:text-blue-900 transition-colors">
        {children}
      </span>
    </motion.button>
  );
}
