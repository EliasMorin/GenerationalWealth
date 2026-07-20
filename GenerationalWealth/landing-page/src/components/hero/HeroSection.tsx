"use client";

import React from "react";
import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react";
import { motion } from "framer-motion";
import { Abstract3DObject } from "./Abstract3DObject";

export function HeroSection() {
  return (
    <div className="relative w-full h-screen min-h-[800px] flex items-center justify-center overflow-hidden bg-black text-white">
      {/* Background Shader Gradient (Layer 1) */}
      <div className="absolute inset-0 z-0 opacity-70 pointer-events-none">
        <ShaderGradientCanvas
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
          }}
        >
          <ShaderGradient
            control="query"
            urlString="https://www.shadergradient.co/customize?animate=on&axesHelper=off&bgColor1=%23000000&bgColor2=%23000000&brightness=0.5&cAzimuthAngle=180&cDistance=3.6&cPolarAngle=90&cameraZoom=1&color1=%23000000&color2=%23111111&color3=%232b2b2b&envPreset=city&format=gif&fov=45&frameRate=10&gizmoHelper=hide&lightType=3d&pixelDensity=1&positionX=-1.4&positionY=0&positionZ=0&range=enabled&rangeEnd=40&rangeStart=0&reflection=0.1&rotationX=0&rotationY=10&rotationZ=50&shader=defaults&type=plane&uAmplitude=0&uDensity=1.3&uFrequency=5.5&uSpeed=0.15&uStrength=1.5&uTime=0&wireframe=false"
          />
        </ShaderGradientCanvas>
        
        {/* Soft gradient overlay to blend into the rest of the page */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/50 to-black pointer-events-none" />
      </div>

      {/* Background 3D Object (Layer 2) */}
      <div className="absolute inset-0 z-10 opacity-60 pointer-events-none">
        <Abstract3DObject />
      </div>

      {/* Content (Layer 3) */}
      <div className="relative z-20 flex flex-col items-center justify-center px-6 text-center max-w-4xl mx-auto pointer-events-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="inline-flex items-center gap-2 px-3 py-1 mb-8 text-sm font-medium border rounded-full border-white/10 bg-white/5 backdrop-blur-md text-gray-300"
        >
          <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          GenerationalWealth 1.0 is now live
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
          className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8 drop-shadow-2xl"
        >
          Professional-grade financial <br className="hidden md:block" />
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-blue-200 to-white">
            terminal in your browser.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
          className="text-lg md:text-xl text-gray-400 mb-10 max-w-2xl leading-relaxed drop-shadow-lg"
        >
          Experience institutional-level analytics, real-time market data, and advanced portfolio management without installing a single application.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: "easeOut" }}
          className="flex flex-col sm:flex-row items-center gap-4"
        >
          <button className="px-8 py-4 text-sm font-semibold text-black transition-all bg-white rounded-lg hover:bg-gray-200 hover:scale-[1.02] active:scale-[0.98] shadow-[0_0_40px_rgba(255,255,255,0.2)]">
            Open Terminal
          </button>
          <button className="px-8 py-4 text-sm font-semibold text-white transition-all border border-white/20 rounded-lg hover:bg-white/5 backdrop-blur-sm">
            View Documentation
          </button>
        </motion.div>
      </div>
    </div>
  );
}
