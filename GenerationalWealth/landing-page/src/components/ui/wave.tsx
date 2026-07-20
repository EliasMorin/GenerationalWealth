"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface WaveProps extends React.HTMLAttributes<HTMLDivElement> {
  fill?: string;
  flipped?: boolean;
}

export function Wave({ className, fill = "#ffffff", flipped = false, ...props }: WaveProps) {
  return (
    <div
      className={cn(
        "w-full overflow-hidden leading-[0] flex",
        flipped ? "rotate-180" : "",
        className
      )}
      {...props}
    >
      <svg
        className="relative block w-[200%] sm:w-[150%] h-[60px] sm:h-[100px]"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
      >
        <motion.path
          animate={{ x: ["0%", "-50%"] }}
          transition={{ repeat: Infinity, ease: "linear", duration: 15 }}
          d="M0,60 C150,120 350,0 600,60 C850,120 1050,0 1200,60 C1350,120 1550,0 1800,60 C2050,120 2250,0 2400,60 L2400,120 L0,120 Z"
          style={{ fill, opacity: 0.5 }}
        ></motion.path>
        <motion.path
          animate={{ x: ["-50%", "0%"] }}
          transition={{ repeat: Infinity, ease: "linear", duration: 20 }}
          d="M0,70 C150,10 350,130 600,70 C850,10 1050,130 1200,70 C1350,10 1550,130 1800,70 C2050,10 2250,130 2400,70 L2400,120 L0,120 Z"
          style={{ fill }}
        ></motion.path>
      </svg>
    </div>
  );
}
