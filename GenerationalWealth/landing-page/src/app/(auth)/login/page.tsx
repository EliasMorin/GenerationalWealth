'use client'

import { useActionState } from 'react'
import { loginUser } from '@/app/actions/auth'
import { motion } from 'framer-motion'
import { TrendingUp, ArrowRight, Loader2 } from 'lucide-react'
import Link from 'next/link'
import { PaperDesignBackground } from '@/components/ui/neon-dither'
import { Wave } from '@/components/ui/wave'

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(loginUser, null)

  return (
    <main className="min-h-screen bg-[#050505] flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Dynamic Backgrounds */}
      <PaperDesignBackground themeMode="dark" intensity={0.06} className="absolute inset-0 z-0 opacity-50 mix-blend-screen pointer-events-none" />
      
      {/* Subtle Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-white/5 rounded-full blur-[120px] pointer-events-none z-0"></div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="flex flex-col items-center mb-8">
          <Link href="/" className="flex items-center gap-2 group mb-6">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:border-white/30 transition-colors">
              <TrendingUp className="text-white w-5 h-5" />
            </div>
            <span className="font-bold text-xl text-white tracking-tight">GenWealth</span>
          </Link>
          <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">Bon retour.</h1>
          <p className="text-slate-400 font-light text-center">Connectez-vous pour accéder à votre tableau de bord.</p>
        </div>

        <div className="bg-[#0a0a0a]/80 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
          <form action={formAction} className="space-y-5">
            {state?.error && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                {state.error}
              </div>
            )}
            
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-300 ml-1">Email</label>
              <input 
                type="email" 
                name="email"
                required
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-transparent transition-all"
                placeholder="vous@exemple.com"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between ml-1">
                <label className="text-sm font-medium text-slate-300">Mot de passe</label>
                <Link href="#" className="text-xs text-white/50 hover:text-white transition-colors">Oublié ?</Link>
              </div>
              <input 
                type="password" 
                name="password"
                required
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-transparent transition-all"
                placeholder="••••••••"
              />
            </div>

            <button 
              type="submit"
              disabled={isPending}
              className="w-full bg-white hover:bg-slate-200 text-black font-semibold rounded-2xl px-4 py-3.5 mt-4 transition-all flex items-center justify-center gap-2 group disabled:opacity-70 shadow-[0_0_15px_rgba(255,255,255,0.1)]"
            >
              {isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : (
                <>
                  Se connecter
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-slate-500 text-sm mt-8">
          Pas encore de compte ? <Link href="/signup" className="text-white hover:underline transition-colors font-medium">Créer un compte</Link>
        </p>
      </motion.div>

      {/* Decorative Wave at the bottom */}
      <div className="absolute bottom-0 left-0 w-full z-0 pointer-events-none opacity-30">
        <Wave fill="#ffffff" />
      </div>
    </main>
  )
}
