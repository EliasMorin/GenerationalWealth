'use client'

import { useActionState, useState, useMemo } from 'react'
import { registerUser } from '@/app/actions/auth'
import { motion, AnimatePresence } from 'framer-motion'
import { TrendingUp, ArrowRight, Loader2, Sparkles, Zap, ShieldCheck, Gem } from 'lucide-react'
import Link from 'next/link'
import { PaperDesignBackground } from '@/components/ui/neon-dither'
import { Wave } from '@/components/ui/wave'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const GW_FUNDS = [
  { 
    id: 'AGGRESSIVE', 
    title: 'Performance', 
    subtitle: 'Rendement maximal',
    desc: "Notre solution la plus performante. Conçue pour surpasser largement les indices boursiers historiques avec une approche agressive.",
    icon: Zap,
    color: '#d946ef',
    apy: 0.16,
    allocation: "Allocation dynamique à haut rendement"
  },
  { 
    id: 'DIVERSIFIED', 
    title: 'Performance diversifiée', 
    subtitle: 'Risque maîtrisé',
    desc: "Un équilibre idéal. Vise une surperformance du marché tout en diluant intelligemment le risque.",
    icon: Gem,
    color: '#3b82f6',
    apy: 0.12,
    allocation: "Allocation diversifiée optimisée"
  },
  { 
    id: 'SLOW_GROWTH', 
    title: 'Croissance', 
    subtitle: 'Régularité et résilience',
    desc: "La force des intérêts composés. Bat le marché avec une volatilité minimale pour une évolution sereine du capital.",
    icon: ShieldCheck,
    color: '#22c55e',
    apy: 0.10,
    allocation: "Allocation défensive et résiliente"
  }
]

export default function SignupPage() {
  const [state, formAction, isPending] = useActionState(registerUser, null)
  
  const [step, setStep] = useState(0)
  const [selectedFundId, setSelectedFundId] = useState('')

  const selectedFund = useMemo(() => GW_FUNDS.find(f => f.id === selectedFundId), [selectedFundId])

  const handleSelectFund = (id: string) => {
    setSelectedFundId(id)
    setTimeout(() => setStep(2), 300)
  }

  // Génération des données de simulation
  const simulationData = useMemo(() => {
    if (!selectedFund) return []
    const data = []
    let valMarket = 10000 // S&P 500 historique ~8%
    let valGW = 10000
    const monthlyContribution = 500
    
    for (let year = 0; year <= 20; year++) {
      data.push({
        year: `Année ${year}`,
        MarcheGlobal: Math.round(valMarket),
        [selectedFund.title]: Math.round(valGW),
      })
      valMarket = (valMarket + monthlyContribution * 12) * 1.08
      valGW = (valGW + monthlyContribution * 12) * (1 + selectedFund.apy)
    }
    return data
  }, [selectedFund])

  const renderStepContent = () => {
    switch (step) {
      case 0:
        return (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-6">
              <TrendingUp className="w-8 h-8 text-fuchsia-400" />
            </div>
            <h2 className="text-3xl font-bold text-white mb-4">Generational Wealth</h2>
            <p className="text-slate-400 mb-8 max-w-sm mx-auto">Nous ne posons pas de questions sur votre profil psychologique. Nous vous offrons nos 3 véhicules d'investissement conçus pour battre le marché. Choisissez le vôtre.</p>
            <button onClick={() => setStep(1)} className="bg-white text-black px-8 py-4 rounded-2xl font-bold hover:bg-slate-200 transition-colors flex items-center gap-2 mx-auto">
              Voir nos Fonds Exclusifs <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>
        )
      case 1:
        return (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-2"><Sparkles className="w-5 h-5 text-fuchsia-400"/> Sélectionnez votre Fonds</h2>
            <p className="text-slate-400 mb-6 text-sm">Chaque fonds est algorithmiquement géré pour surperformer les indices traditionnels.</p>
            <div className="space-y-3">
              {GW_FUNDS.map(f => {
                const Icon = f.icon
                return (
                  <button key={f.id} onClick={() => handleSelectFund(f.id)} className="w-full text-left p-4 rounded-2xl border border-white/10 hover:border-white/30 hover:bg-white/5 transition-all group flex gap-4 items-start">
                    <div className="mt-1 w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: `${f.color}20` }}>
                      <Icon className="w-5 h-5" style={{ color: f.color }} />
                    </div>
                    <div>
                      <div className="text-white font-bold mb-1 flex items-center gap-2">
                        {f.title} <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-slate-300 font-medium">{f.subtitle}</span>
                      </div>
                      <div className="text-slate-400 text-sm leading-relaxed">{f.desc}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </motion.div>
        )
      case 2:
        return (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="w-full">
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-fuchsia-500/10 border border-fuchsia-500/20 text-fuchsia-400 text-xs font-bold uppercase tracking-widest mb-4">
                <Sparkles className="w-3 h-3" /> Fonds Sélectionné
              </div>
              <h2 className="text-3xl font-bold text-white mb-2">{selectedFund?.title}</h2>
              <p className="text-slate-400 text-sm max-w-sm mx-auto">{selectedFund?.subtitle}</p>
            </div>

            <div className="bg-black/50 border border-white/5 rounded-2xl p-4 mb-6">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Projection (10k€ + 500€/m)</div>
                <div className="text-xs font-bold text-green-400">Objectif: {(selectedFund?.apy! * 100).toFixed(0)}% / an</div>
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={simulationData} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                    <XAxis dataKey="year" stroke="#666" fontSize={10} tickMargin={10} minTickGap={20} />
                    <YAxis stroke="#666" fontSize={10} tickFormatter={(v) => `${(v/1000).toFixed(0)}k€`} width={40} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#000', borderColor: '#333', borderRadius: '12px' }}
                      formatter={(value: any) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(Number(value))}
                    />
                    <Line type="monotone" dataKey={selectedFund?.title} stroke={selectedFund?.color} strokeWidth={3} dot={false} />
                    <Line type="monotone" dataKey="MarcheGlobal" stroke="#64748b" strokeWidth={2} dot={false} strokeDasharray="5 5" name="Marché (S&P 500)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-2xl p-4 mb-6 text-sm">
              <div className="text-slate-500 mb-1">Allocation Cible</div>
              <div className="text-white font-medium">{selectedFund?.allocation}</div>
            </div>

            <button onClick={() => setStep(3)} className="w-full bg-white hover:bg-slate-200 text-black font-semibold rounded-2xl px-4 py-4 transition-all flex items-center justify-center gap-2 group shadow-[0_0_15px_rgba(255,255,255,0.1)]">
              Investir dans {selectedFund?.title} <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </motion.div>
        )
      case 3:
        return (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="w-full">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white/5 border border-white/10 mb-4">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">Rejoignez l'élite</h2>
              <p className="text-slate-400 text-sm font-light">Création de votre accès privé pour suivre {selectedFund?.title}.</p>
            </div>
            
            <form action={formAction} className="space-y-4">
              <input type="hidden" name="riskProfile" value={selectedFund?.id} />

              {state?.error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                  {state.error}
                </div>
              )}
              
              <div className="space-y-4">
                <input type="text" name="name" required className="w-full bg-transparent border-b border-white/20 px-2 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-white transition-colors" placeholder="Nom complet" />
                <input type="email" name="email" required className="w-full bg-transparent border-b border-white/20 px-2 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-white transition-colors" placeholder="Adresse email" />
                <input type="password" name="password" required className="w-full bg-transparent border-b border-white/20 px-2 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-white transition-colors" placeholder="Mot de passe" minLength={6} />
              </div>

              <div className="pt-6">
                <button type="submit" disabled={isPending} className="w-full bg-white hover:bg-slate-200 text-black font-semibold rounded-2xl px-4 py-4 transition-all flex items-center justify-center gap-2 group disabled:opacity-70 shadow-[0_0_20px_rgba(255,255,255,0.15)]">
                  {isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : "Accéder à mon espace"}
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
              </div>
            </form>
            <button onClick={() => setStep(2)} className="mt-6 w-full text-center text-xs font-medium uppercase tracking-widest text-slate-500 hover:text-white transition-colors">
              Retour au portefeuille
            </button>
          </motion.div>
        )
    }
  }

  return (
    <main className="min-h-screen bg-[#050505] flex flex-col items-center justify-center p-6 relative overflow-hidden">
      <PaperDesignBackground themeMode="dark" intensity={0.06} className="absolute inset-0 z-0 opacity-50 mix-blend-screen pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-fuchsia-500/5 rounded-full blur-[120px] pointer-events-none z-0"></div>

      <div className="w-full max-w-lg relative z-10">
        <div className="flex justify-center mb-8">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:border-white/30 transition-colors">
              <TrendingUp className="text-white w-5 h-5" />
            </div>
            <span className="font-bold text-xl text-white tracking-tight">GenerationalWealth</span>
          </Link>
        </div>

        <div className="bg-[#0a0a0a]/80 backdrop-blur-xl border border-white/10 rounded-3xl p-6 md:p-8 shadow-2xl min-h-[400px] flex flex-col justify-center">
          <AnimatePresence mode="wait">
            {renderStepContent()}
          </AnimatePresence>
        </div>

        {step === 0 && (
          <p className="text-center text-slate-500 text-sm mt-8">
            Vous avez déjà un compte ? <Link href="/login" className="text-white hover:underline transition-colors font-medium">Se connecter</Link>
          </p>
        )}
      </div>

      <div className="absolute bottom-0 left-0 w-full z-0 pointer-events-none opacity-30">
        <Wave fill="#ffffff" />
      </div>
    </main>
  )
}
