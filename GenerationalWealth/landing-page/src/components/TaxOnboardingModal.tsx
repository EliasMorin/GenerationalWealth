import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BrainCircuit, Sparkles, ShieldCheck } from 'lucide-react'
import { updateTaxProfile } from '@/app/actions/auth'

export function TaxOnboardingModal({ onComplete, userProfile }: { onComplete: (data: any) => void, userProfile?: any }) {
  const [profession, setProfession] = useState(userProfile?.profession || "Salarié")
  const [maritalStatus, setMaritalStatus] = useState(userProfile?.maritalStatus || "Célibataire")
  const [children, setChildren] = useState(userProfile?.children || 0)
  const [income, setIncome] = useState(userProfile?.income || 0)
  const [otherIncome, setOtherIncome] = useState(userProfile?.otherIncome || 0)
  const [contractType, setContractType] = useState(userProfile?.contractType || "CDI")
  const [contractDuration, setContractDuration] = useState(userProfile?.contractDuration || "")
  const [parentsProfession, setParentsProfession] = useState(userProfile?.parentsProfession || "")
  const [financialAids, setFinancialAids] = useState(userProfile?.financialAids || "")
  const [goal, setGoal] = useState(userProfile?.taxGoal || "Réduire mes impôts massivement et rapidement")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    setIsSubmitting(true)
    const data = {
      profession, maritalStatus, children, income, otherIncome,
      contractType, contractDuration, parentsProfession, financialAids, taxGoal: goal
    }
    await updateTaxProfile(data)
    setIsSubmitting(false)
    onComplete(data)
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 relative shadow-2xl my-auto">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-500/5 to-transparent rounded-3xl pointer-events-none"></div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-emerald-500/10 p-2 rounded-lg border border-emerald-500/20">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            </div>
            <h2 className="text-2xl font-light text-white tracking-tight">Intelligence Fiscale & Ingénierie Patrimoniale</h2>
          </div>
          <p className="text-slate-400 mb-8 text-sm max-w-2xl">Avant de configurer vos portefeuilles, notre IA experte en droit fiscal a besoin de connaître votre situation précise pour structurer vos actifs de manière optimale et minimiser votre imposition.</p>

          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Statut Professionnel</label>
                <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={profession} onChange={(e) => setProfession(e.target.value)}>
                  <option className="bg-black">Salarié</option>
                  <option className="bg-black">Indépendant / Freelance</option>
                  <option className="bg-black">Chef d'entreprise (TNS / SASU)</option>
                  <option className="bg-black">Étudiant / Alternant</option>
                  <option className="bg-black">Retraité</option>
                  <option className="bg-black">Sans emploi</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">État civil</label>
                <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={maritalStatus} onChange={(e) => setMaritalStatus(e.target.value)}>
                  <option className="bg-black">Célibataire</option>
                  <option className="bg-black">Marié(e) / Pacsé(e)</option>
                  <option className="bg-black">Divorcé(e)</option>
                  <option className="bg-black">Veuf/Veuve</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Enfants à charge</label>
                <input type="number" min="0" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={children} onChange={(e) => setChildren(parseInt(e.target.value) || 0)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Revenus nets annuels (foyer) €</label>
                <input type="number" step="1000" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={income} onChange={(e) => setIncome(parseInt(e.target.value) || 0)} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Autres revenus imposables (foncier, etc.) €</label>
                <input type="number" step="1000" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={otherIncome} onChange={(e) => setOtherIncome(parseInt(e.target.value) || 0)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Type de contrat</label>
                <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={contractType} onChange={(e) => setContractType(e.target.value)}>
                  <option className="bg-black">CDI</option>
                  <option className="bg-black">CDD</option>
                  <option className="bg-black">Apprenti / Contrat Pro</option>
                  <option className="bg-black">Stage</option>
                  <option className="bg-black">Freelance / Indépendant</option>
                  <option className="bg-black">Autre</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Durée restante (si applicable)</label>
                <input type="text" placeholder="Ex: 1 an, 6 mois, Indéterminé..." className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={contractDuration} onChange={(e) => setContractDuration(e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Profession des parents (pour exonérations)</label>
                <input type="text" placeholder="Ex: Agriculteur, Fonctionnaire..." className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={parentsProfession} onChange={(e) => setParentsProfession(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-400">Aides perçues (CAF, Bourses, etc.)</label>
                <input type="text" placeholder="Ex: APL, Bourse CROUS, Prime d'activité..." className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={financialAids} onChange={(e) => setFinancialAids(e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-bold text-slate-400">Objectif patrimonial prioritaire</label>
              <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={goal} onChange={(e) => setGoal(e.target.value)}>
                <option className="bg-black">Réduire mes impôts massivement et rapidement</option>
                <option className="bg-black">Structurer à travers une société (Holding, SCI...)</option>
                <option className="bg-black">Maximiser mon capital long-terme (intérêts composés)</option>
                <option className="bg-black">Préparer ma retraite & Protéger ma famille</option>
                <option className="bg-black">Optimiser les plus-values de mon CTO actuel (Tax Harvesting)</option>
              </select>
            </div>

            <button onClick={handleSubmit} disabled={isSubmitting} className="w-full mt-6 py-4 rounded-xl bg-white text-black font-bold hover:bg-slate-200 transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] disabled:opacity-50 flex items-center justify-center gap-2">
              {isSubmitting ? <><BrainCircuit className="w-5 h-5 animate-pulse" /> Traitement en cours...</> : <><Sparkles className="w-5 h-5" /> Enregistrer et continuer</>}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
