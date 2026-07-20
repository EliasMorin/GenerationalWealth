"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, User } from "lucide-react";
import Link from "next/link";
import { Button } from "./button";
import { checkAuthStatus } from "@/app/actions/auth";

export function Navbar() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    checkAuthStatus().then(setIsLoggedIn).catch(() => {});
  }, []);

  return (
    <motion.header 
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="fixed top-4 left-1/2 -translate-x-1/2 w-[95%] max-w-6xl mx-auto flex justify-between items-center py-4 px-6 backdrop-blur-md bg-[#0a0a0a]/70 border border-white/10 z-50 rounded-2xl shadow-2xl"
    >
      <Link href="/" className="flex items-center gap-3 group">
        <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center border border-white/5 group-hover:border-white/20 transition-all duration-300">
          <TrendingUp className="text-white w-5 h-5" />
        </div>
        <span className="font-semibold text-xl tracking-tight text-white">
          GenWealth
        </span>
      </Link>
      
      <nav className="hidden md:flex gap-8 text-sm font-medium text-slate-400">
        <a href="#features" className="hover:text-white transition-colors">Plateforme</a>
        <a href="#data" className="hover:text-white transition-colors">Données</a>
        <a href="#pricing" className="hover:text-white transition-colors">Tarifs</a>
      </nav>
      
      <div className="flex items-center gap-4">
        {isLoggedIn ? (
          <Link href="/dashboard">
            <Button variant="secondary" className="rounded-full px-6 bg-white hover:bg-slate-200 text-black font-semibold shadow-[0_0_15px_rgba(255,255,255,0.1)] transition-all flex items-center gap-2">
              <User className="w-4 h-4" />
              Mon Compte
            </Button>
          </Link>
        ) : (
          <>
            <Link href="/login" className="text-sm font-medium text-slate-400 hover:text-white transition-colors hidden md:block">
              Connexion
            </Link>
            <Link href="/signup">
              <Button variant="secondary" className="rounded-full px-6 bg-white hover:bg-slate-200 text-black font-semibold shadow-[0_0_15px_rgba(255,255,255,0.1)] transition-all">
                Créer un compte
              </Button>
            </Link>
          </>
        )}
      </div>
    </motion.header>
  );
}
