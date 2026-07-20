'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Eye, EyeOff, TrendingUp, TrendingDown, LogOut, Wallet, LineChart, 
  BrainCircuit, Landmark, Tv, Activity, Rss,
  DollarSign, Building, Search, BarChart3, Compass,
  Radar, Calendar, Users, Newspaper, ArrowUpRight,
  ArrowDownRight, CreditCard, ArrowRightLeft, Gift, Bell, ChevronDown, ChevronRight, Target, Globe, Sparkles, ShieldCheck, Diamond,
  ArrowRight, Plus, X, ChevronUp, Zap, Rocket, Shield, User, Settings, RefreshCw
} from 'lucide-react'
import Link from 'next/link'
import { PaperDesignBackground } from '@/components/ui/neon-dither'
import { Wave } from '@/components/ui/wave'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, PieChart, Pie, Cell, LineChart as RechartsLineChart, Line } from 'recharts'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
const FUND_PROFILES: Record<string, any> = {
  'AGGRESSIVE': { title: 'Performance', color: '#d946ef', bgClass: 'bg-fuchsia-500/10', textClass: 'text-fuchsia-400', borderClass: 'border-fuchsia-500/20' },
  'DIVERSIFIED': { title: 'Performance diversifiée', color: '#3b82f6', bgClass: 'bg-blue-500/10', textClass: 'text-blue-400', borderClass: 'border-blue-500/20' },
  'SLOW_GROWTH': { title: 'Croissance', color: '#22c55e', bgClass: 'bg-green-500/10', textClass: 'text-green-400', borderClass: 'border-green-500/20' }
}
import { logoutUser, getUserProfile } from "@/app/actions/auth"
import { TaxOnboardingModal } from '@/components/TaxOnboardingModal'


function AssetScreenerTab({ isTrConnected, onRequestTrConnect }: { isTrConnected: boolean, onRequestTrConnect: () => void }) {
  const [screenerData, setScreenerData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [selectedQuantAsset, setSelectedQuantAsset] = useState<any>(null)
  const [quantAssetData, setQuantAssetData] = useState<any>(null)
  const [loadingQuantAsset, setLoadingQuantAsset] = useState(false)

  const handleSelectQuantAsset = (asset: any) => {
    setSelectedQuantAsset(asset)
    setLoadingQuantAsset(true)
    const q = asset.ticker || asset.isin
    fetch(`http://localhost:5000/api/quant/asset?q=${q}`)
      .then(res => res.json())
      .then(data => {
        setQuantAssetData(data)
        setLoadingQuantAsset(false)
      })
      .catch(() => setLoadingQuantAsset(false))
  }

  const generateCombinedChartData = () => {
    const mom = (screenerData?.etf_momentum?.perf_qtd || 0);
    const garp = (screenerData?.etf_garp?.perf_qtd || 0);
    const shortPerf = -(screenerData?.etf_short?.perf_qtd || 0);
    const nasdaq = 15.2 / 2; // Assuming ~7.5% per quarter on average for representation
    
    return [
      { month: 'J-7', momentum: 0, garp: 0, short: 0, nasdaq: 0 },
      { month: 'J-6', momentum: mom*0.12, garp: garp*0.12, short: shortPerf*0.12, nasdaq: nasdaq*0.15 },
      { month: 'J-5', momentum: mom*0.25, garp: garp*0.25, short: shortPerf*0.25, nasdaq: nasdaq*0.35 },
      { month: 'J-4', momentum: mom*0.45, garp: garp*0.45, short: shortPerf*0.45, nasdaq: nasdaq*0.50 },
      { month: 'J-3', momentum: mom*0.65, garp: garp*0.65, short: shortPerf*0.65, nasdaq: nasdaq*0.70 },
      { month: 'J-2', momentum: mom*0.85, garp: garp*0.85, short: shortPerf*0.85, nasdaq: nasdaq*0.85 },
      { month: 'Auj', momentum: mom, garp: garp, short: shortPerf, nasdaq: nasdaq },
    ]
  }

  useEffect(() => {
    setLoading(true)
    fetch('http://localhost:5000/api/quant/screener')
      .then(res => res.json())
      .then(data => {
        setScreenerData(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      setIsSearching(false)
      return
    }
    if (!isTrConnected) {
      setIsSearching(false)
      onRequestTrConnect()
      return
    }
    const delayDebounceFn = setTimeout(() => {
      setIsSearching(true)
      fetch(`http://localhost:5000/api/tr/search?q=${encodeURIComponent(searchQuery)}`)
        .then(res => res.json())
        .then(data => {
          setSearchResults(Array.isArray(data) ? data.slice(0, 5) : [])
          setIsSearching(false)
        })
        .catch(() => {
          setSearchResults([])
          setIsSearching(false)
        })
    }, 400)
    return () => clearTimeout(delayDebounceFn)
  }, [searchQuery, isTrConnected, onRequestTrConnect])

  return (
    <div className="space-y-12 pb-20 w-full min-w-0 animate-in fade-in duration-500">
      <div className="flex flex-col gap-2">
        <h2 className="text-emerald-400 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
          <Radar className="w-4 h-4" /> Quant Engine
        </h2>
        <h1 className="text-4xl md:text-5xl font-light text-white tracking-tight">Radar de Performance</h1>
        <p className="text-slate-400 max-w-2xl mt-2 text-sm leading-relaxed">
          Notre moteur quantitatif analyse les fondamentaux, la dynamique de prix et les flux d'actualité IA pour filtrer les meilleures opportunités du marché.
        </p>
      </div>

      {loading ? (
        <div className="w-full h-64 flex flex-col items-center justify-center border border-white/5 rounded-[2rem] bg-black/50 backdrop-blur-md">
          <div className="w-12 h-12 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mb-4" />
          <p className="text-emerald-400 font-mono text-xs uppercase tracking-widest animate-pulse">Exécution des modèles quantitatifs...</p>
        </div>
      ) : screenerData && !screenerData.error ? (
        <div className="space-y-12">
          
          {/* TOP SECTORS GRAPH */}
          <div className="bg-[#050505] border border-white/5 rounded-[2rem] p-6 md:p-8">
             <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
               Secteurs en tendance
             </h3>
             <p className="text-slate-400 text-sm mb-6">Performance sectorielle (Top 8) & Analyse Macro-Économique IA</p>
              <div className="w-full flex flex-col gap-8 mt-8">
               {(() => {
                 const valid = (screenerData.all_sectors?.filter((sec: any) => sec[0] !== "Obligations d'entreprises" && sec[0] !== "Mid/Small Caps") || []).sort((a: any, b: any) => b[1] - a[1]);
                 const items = valid.length <= 8 ? valid : [...valid.slice(0, 4), ...valid.slice(-4)];
                 const maxAbsPerf = Math.max(...items.map((sec: any) => Math.abs(sec[1])), 1);

                 return items.map((sec: any, index: number) => {
                   const isPositive = sec[1] >= 0;
                   const widthPct = Math.min((Math.abs(sec[1]) / maxAbsPerf) * 100, 100);
                   
                   return (
                     <div key={index} className="flex flex-col gap-2">
                       <div className="flex justify-between items-end">
                         <span className="text-sm font-medium text-slate-300">{sec[0]}</span>
                         <span className={`text-sm font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                           {isPositive ? '+' : ''}{sec[1].toFixed(2)}%
                         </span>
                       </div>
                       <div className="w-full h-2 bg-[#0a0a0a] border border-white/5 rounded-full relative overflow-hidden flex">
                         <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-white/10 z-10" />
                         {isPositive ? (
                           <>
                             <div className="w-1/2" />
                             <div className="w-1/2 flex items-center">
                               <div className="h-full bg-emerald-500 rounded-r-full shadow-[0_0_10px_rgba(16,185,129,0.3)] transition-all duration-1000 ease-out" style={{ width: `${widthPct}%` }} />
                             </div>
                           </>
                         ) : (
                           <>
                             <div className="w-1/2 flex justify-end items-center">
                               <div className="h-full bg-rose-500 rounded-l-full shadow-[0_0_10px_rgba(244,63,97,0.3)] transition-all duration-1000 ease-out" style={{ width: `${widthPct}%` }} />
                             </div>
                             <div className="w-1/2" />
                           </>
                         )}
                       </div>
                       
                        {/* Boîte d'Analyse IA pour les Top 3 secteurs */}
                        {isPositive && index < 3 && screenerData.ai_analysis && screenerData.ai_analysis[sec[0]] && (
                          <div className="mt-3 p-4 rounded-xl bg-gradient-to-br from-emerald-900/10 to-transparent border border-emerald-500/10">
                            <div className="flex items-center gap-2 mb-2 text-emerald-400 font-mono text-[10px] uppercase tracking-wider">
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                              IA Macro Analyst
                            </div>
                            <p className="text-emerald-100/60 text-xs leading-relaxed">
                              {screenerData.ai_analysis[sec[0]]}
                            </p>
                          </div>
                        )}
                     </div>
                   );
                 });
               })()}
             </div>
          </div>

          {/* GRAPHIQUE COMPARATIF GLOBAL */}
          <div className="bg-[#050505] border border-white/5 rounded-[2rem] p-6 md:p-8">
            <h3 className="text-xl font-bold text-white mb-2">Comparatif des Performances ({screenerData.quarter_label || 'QTD'})</h3>
            <p className="text-slate-400 text-sm mb-6">Évolution des fonds quantitatifs face au Nasdaq depuis le début du trimestre</p>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsLineChart data={generateCombinedChartData()} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <XAxis dataKey="month" stroke="#666" fontSize={10} tickMargin={10} />
                  <YAxis stroke="#666" fontSize={10} tickFormatter={(v) => `+${v}%`} width={40} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#000', borderColor: '#333', borderRadius: '12px' }}
                    formatter={(value: any) => `+${Number(value).toFixed(2)}%`}
                  />
                  <Line type="monotone" dataKey="momentum" name="Fonds Performance" stroke="#d946ef" strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="garp" name="Fonds Croissance" stroke="#22c55e" strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="short" name="Radar Short (Inversé)" stroke="#ef4444" strokeWidth={3} dot={false} strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="nasdaq" name="Nasdaq" stroke="#64748b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                </RechartsLineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* FONDS ETF GÉNÉRÉS */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
            
            {/* MOMENTUM */}
            <div className="bg-[#050505] border border-white/5 rounded-[2rem] p-6">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  Fonds Performance 
                  {screenerData.etf_momentum?.is_locked && (
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700 ml-2">VERROUILLÉ ({screenerData.quarter_label})</span>
                  )}
                </h3>
                <p className="text-slate-400 text-xs mt-2 mb-4">Trend Following & Hyper-Croissance</p>
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10 mb-2">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase">Perf QTD (Trimestre)</div>
                    <div className="font-mono font-bold text-emerald-400">+{((screenerData.etf_momentum?.perf_qtd || 0)).toFixed(2)}%</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500 uppercase">Perf Globale</div>
                    <div className="font-mono text-emerald-300">+{ ((screenerData.etf_momentum?.perf_total || 0)).toFixed(2) }%</div>
                  </div>
                </div>
              </div>

            </div>

            {/* GARP */}
            <div className="bg-[#050505] border border-white/5 rounded-[2rem] p-6">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  Fonds Croissance
                  {screenerData.etf_garp?.is_locked && (
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700 ml-2">VERROUILLÉ ({screenerData.quarter_label})</span>
                  )}
                </h3>
                <p className="text-slate-400 text-xs mt-2 mb-4">Value Long-Terme & Croissance Saine</p>
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10 mb-2">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase">Perf QTD (Trimestre)</div>
                    <div className="font-mono font-bold text-emerald-400">+{((screenerData.etf_garp?.perf_qtd || 0)).toFixed(2)}%</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500 uppercase">Perf Globale</div>
                    <div className="font-mono text-emerald-300">+{ ((screenerData.etf_garp?.perf_total || 0)).toFixed(2) }%</div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 border border-red-500/20 bg-red-500/5 rounded-2xl text-red-400">
          Erreur de chargement du Quant Engine. Lancez d'abord data_engine.py.
        </div>
      )}

      {/* EXPLORATEUR MANUEL (conservé) */}
      <div className="bg-[#050505] border border-white/5 rounded-[2rem] p-6 md:p-8">
        <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
          <Compass className="w-5 h-5 text-slate-400" /> Explorateur Manuel Trade Republic
        </h3>
        
        <div className="relative mb-6">
          <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input 
            type="text" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher une action, un ETF, une crypto..." 
            className="w-full bg-[#0a0a0a] border border-white/10 rounded-2xl pl-14 pr-4 py-4 text-white text-sm focus:outline-none focus:border-white/20 focus:bg-[#0f0f0f] transition-all shadow-inner"
          />
          {isSearching && (
            <div className="absolute right-5 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          )}
        </div>

        {searchResults.length > 0 && (
          <div className="space-y-2">
            {searchResults.map((res: any, idx: number) => (
              <div 
                key={idx} 
                onClick={() => handleSelectQuantAsset(res)}
                className="bg-[#0a0a0a] hover:bg-white/5 border border-white/5 rounded-xl p-4 flex items-center justify-between cursor-pointer transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center overflow-hidden border border-white/5">
                    <img src={res.image_url || (res.isin ? `https://assets.traderepublic.com/img/logos/${res.isin}/dark.svg` : '')} alt={res.name} className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                  </div>
                  <div>
                    <h4 className="font-bold text-white text-sm">{res.name}</h4>
                    <p className="text-[11px] text-slate-500 font-mono mt-0.5">{res.ticker || res.isin} • {res.type || 'Stock'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* QUANT ASSET MODAL */}
      <AnimatePresence>
        {selectedQuantAsset && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-2xl p-4 md:p-8"
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
              className="relative w-full max-w-5xl h-full max-h-[85vh] bg-[#050505] border border-white/10 rounded-[2.5rem] overflow-hidden flex flex-col shadow-2xl"
            >
              <button onClick={() => { setSelectedQuantAsset(null); setQuantAssetData(null); }} className="absolute top-6 right-6 w-10 h-10 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center transition-colors z-50">
                <X className="w-5 h-5 text-white" />
              </button>

              <div className="flex-1 overflow-y-auto p-8 md:p-12">
                {/* HEADER */}
                <div className="flex items-center gap-6 mb-10 border-b border-white/10 pb-10">
                  <div className="w-24 h-24 rounded-3xl bg-white/5 flex items-center justify-center overflow-hidden border border-white/10 shrink-0">
                    <img src={selectedQuantAsset.image_url || (selectedQuantAsset.isin ? `https://assets.traderepublic.com/img/logos/${selectedQuantAsset.isin}/dark.svg` : '')} alt={selectedQuantAsset.name} className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">{selectedQuantAsset.type} • {selectedQuantAsset.isin}</div>
                    <h2 className="text-4xl md:text-5xl font-black text-white tracking-tight">{selectedQuantAsset.name}</h2>
                    {quantAssetData?.ticker && (
                       <div className="text-emerald-400 font-mono text-lg mt-2">{quantAssetData.ticker}</div>
                    )}
                  </div>
                </div>

                {loadingQuantAsset ? (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-4">
                    <BrainCircuit className="w-8 h-8 text-emerald-500 animate-pulse" />
                    Extraction des fondamentaux...
                  </div>
                ) : quantAssetData && quantAssetData.fundamentals && Object.keys(quantAssetData.fundamentals).length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    
                    {/* VALUATION */}
                    <div className="bg-[#0a0a0a] border border-white/5 rounded-3xl p-6">
                      <h3 className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-6 flex items-center gap-2"><Target className="w-4 h-4"/> Valorisation</h3>
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs text-slate-500 mb-1">P/E Ratio (Trailing)</div>
                          <div className="text-2xl font-mono text-white">{quantAssetData.fundamentals.trailingPE ? quantAssetData.fundamentals.trailingPE.toFixed(2) : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">P/E Ratio (Forward)</div>
                          <div className="text-xl font-mono text-slate-300">{quantAssetData.fundamentals.forwardPE ? quantAssetData.fundamentals.forwardPE.toFixed(2) : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">Market Cap</div>
                          <div className="text-lg font-mono text-emerald-400">{quantAssetData.fundamentals.marketCap ? (quantAssetData.fundamentals.marketCap / 1e9).toFixed(2) + ' B$' : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">PEG Ratio</div>
                          <div className="text-lg font-mono text-white">{quantAssetData.fundamentals.pegRatio ? quantAssetData.fundamentals.pegRatio.toFixed(2) : 'N/A'}</div>
                        </div>
                      </div>
                    </div>

                    {/* MARGINS & GROWTH */}
                    <div className="bg-[#0a0a0a] border border-white/5 rounded-3xl p-6">
                      <h3 className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-6 flex items-center gap-2"><TrendingUp className="w-4 h-4"/> Croissance & Marges</h3>
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs text-slate-500 mb-1">Croissance Revenus (YoY)</div>
                          <div className="text-2xl font-mono text-white">{quantAssetData.fundamentals.revenueGrowth ? (quantAssetData.fundamentals.revenueGrowth * 100).toFixed(2) + '%' : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">Croissance Bénéfices (YoY)</div>
                          <div className="text-xl font-mono text-emerald-400">{quantAssetData.fundamentals.earningsGrowth ? (quantAssetData.fundamentals.earningsGrowth * 100).toFixed(2) + '%' : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">Marge Brute</div>
                          <div className="text-lg font-mono text-white">{quantAssetData.fundamentals.grossMargins ? (quantAssetData.fundamentals.grossMargins * 100).toFixed(2) + '%' : 'N/A'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 mb-1">Marge Opérationnelle</div>
                          <div className="text-lg font-mono text-white">{quantAssetData.fundamentals.operatingMargins ? (quantAssetData.fundamentals.operatingMargins * 100).toFixed(2) + '%' : 'N/A'}</div>
                        </div>
                      </div>
                    </div>

                    {/* PERFORMANCE */}
                    <div className="bg-[#0a0a0a] border border-white/5 rounded-3xl p-6">
                      <h3 className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-6 flex items-center gap-2"><LineChart className="w-4 h-4"/> Performance</h3>
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs text-slate-500 mb-1">52 Semaines (Haut/Bas)</div>
                          <div className="text-lg font-mono text-white">{quantAssetData.fundamentals.fiftyTwoWeekRange || 'N/A'}</div>
                        </div>
                        {quantAssetData.performance && (
                          <>
                            <div>
                              <div className="text-xs text-slate-500 mb-1">Perf 1 Mois</div>
                              <div className={`text-xl font-mono font-bold ${quantAssetData.performance['1M'] >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {quantAssetData.performance['1M'] != null ? quantAssetData.performance['1M'].toFixed(2) + '%' : 'N/A'}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 mb-1">Perf 6 Mois</div>
                              <div className={`text-xl font-mono font-bold ${quantAssetData.performance['6M'] >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {quantAssetData.performance['6M'] != null ? quantAssetData.performance['6M'].toFixed(2) + '%' : 'N/A'}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 mb-1">Perf 1 An</div>
                              <div className={`text-xl font-mono font-bold ${quantAssetData.performance['1Y'] >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {quantAssetData.performance['1Y'] != null ? quantAssetData.performance['1Y'].toFixed(2) + '%' : 'N/A'}
                              </div>
                            </div>
                          </>
                        )}
                        <div>
                           <div className="text-xs text-slate-500 mb-1">Dividende (Rendement)</div>
                           <div className="text-lg font-mono text-slate-300">{quantAssetData.fundamentals.dividendYield ? (quantAssetData.fundamentals.dividendYield * 100).toFixed(2) + '%' : 'N/A'}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                    <p>Fondamentaux indisponibles pour cet actif (Peut-être un ETF ou une crypto).</p>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  )
}



export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('portfolio')
  const [userProfile, setUserProfile] = useState<any>(null)
  const [showUserProfileModal, setShowUserProfileModal] = useState(false)
  const [forceTaxModal, setForceTaxModal] = useState(false)
  
  useEffect(() => {
    getUserProfile().then(profile => {
      if (profile) setUserProfile(profile)
    })
  }, [])
  
  const [bbgLive, setBbgLive] = useState({ running: false, segments_captured: 0 })
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<{role: 'user' | 'ai', text: string}[]>([])
  const [isChatLoading, setIsChatLoading] = useState(false)
  const chatScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [chatMessages])
  
  const handleSendChatMessage = async () => {
    if (!chatInput.trim() || isChatLoading) return
    const userMsg = chatInput.trim()
    setChatInput('')
    setChatMessages(prev => [...prev, {role: 'user', text: userMsg}])
    setIsChatLoading(true)
    
    try {
      const res = await fetch('http://localhost:5000/api/ai/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: userMsg})
      })
      const data = await res.json()
      if (data.error) {
        setChatMessages(prev => [...prev, {role: 'ai', text: "Erreur: " + data.error}])
      } else {
        setChatMessages(prev => [...prev, {role: 'ai', text: data.response}])
      }
    } catch (e) {
      setChatMessages(prev => [...prev, {role: 'ai', text: "Erreur de connexion au backend."}])
    } finally {
      setIsChatLoading(false)
    }
  }

  useEffect(() => {
    // Fetch Bloomberg live state
    const pollBbg = () => {
      fetch('http://localhost:5000/api/bloomberg-live/status')
        .then(res => res.json())
        .then(data => {
          setBbgLive({ running: data.running, segments_captured: data.segments_captured })
        })
        .catch(() => {})
    }
    pollBbg()
    const intv = setInterval(pollBbg, 5000)
    return () => clearInterval(intv)
  }, [])
  
  // TR State
  const [isAuthChecking, setIsAuthChecking] = useState(true)
  const [isTrConnected, setIsTrConnected] = useState(false)
  const [aiConnections, setAiConnections] = useState({ gemini: false, groq: false })
  const [showTrModal, setShowTrModal] = useState(false)
  const [trStep, setTrStep] = useState(1)
  const [trProcessId, setTrProcessId] = useState('')
  const [trPhone, setTrPhone] = useState('+33 6 ')
  const [trPin, setTrPin] = useState('')
  const [trSms, setTrSms] = useState('')
  const [trError, setTrError] = useState('')
  const [trLoading, setTrLoading] = useState(false)
  const [isRefreshingTR, setIsRefreshingTR] = useState(false)
  const [saveCredentials, setSaveCredentials] = useState(true)
  const authLockRef = useRef(false)

  useEffect(() => {
    const checkTrStatus = (isInitial = false) => {
      if (authLockRef.current) return;
      fetch('http://localhost:5000/api/tr/status')
        .then(res => res.json())
        .then(data => {
          if (data.loggedIn || data.status === 'connected') {
            setIsTrConnected(true)
            setShowTrModal(false)
            setIsAuthChecking(false)
          } else {
            setIsTrConnected(false)
            fetch('http://localhost:5000/api/auth/remembered')
              .then(res => res.json())
              .then(rem => {
                if (rem.phone) setTrPhone(rem.phone)
                if (rem.pin) setTrPin(rem.pin)
                
                setTrStep(prev => prev === 2 ? 2 : 1)
                setShowTrModal(true)
                setIsAuthChecking(false)
              })
              .catch(() => {
                setTrStep(prev => prev === 2 ? 2 : 1)
                setShowTrModal(true)
                setIsAuthChecking(false)
              })
          }
        })
        .catch(() => {
          setIsTrConnected(false)
          fetch('http://localhost:5000/api/auth/remembered')
            .then(res => res.json())
            .then(rem => {
              if (rem.phone) setTrPhone(rem.phone)
              if (rem.pin) setTrPin(rem.pin)
              setTrStep(prev => prev === 2 ? 2 : 1)
              setShowTrModal(true)
              setIsAuthChecking(false)
            })
            .catch(() => {
              setTrStep(prev => prev === 2 ? 2 : 1)
              setShowTrModal(true)
              setIsAuthChecking(false)
            })
        })
    }

    checkTrStatus(true)

    const checkLogin = () => {
      fetch('http://localhost:5000/api/auth/status')
        .then(res => res.json())
        .then(data => {
          if (data.status === 'authenticated') {
            // Do not override TR connection state based on local auth
          }
        })
        .catch(() => {})
        
      fetch('http://localhost:5000/api/status/connections')
        .then(res => res.json())
        .then(data => {
          setAiConnections({ gemini: data.gemini_connected, groq: data.groq_connected })
        })
        .catch(() => {})
    }

    const interval = setInterval(checkLogin, 5000)
    checkLogin()
    const intvTr = setInterval(() => checkTrStatus(false), 30000)
    
    return () => {
      clearInterval(interval)
      clearInterval(intvTr)
    }
  }, [])

  const handleTrLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    authLockRef.current = true
    setTrLoading(true)
    setTrError('')
    try {
      const res = await fetch('http://localhost:5000/api/tr/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: trPhone.replace(/\s+/g, ''), pin: trPin })
      })
      const data = await res.json()
      if (data.processId || data.process_id || data.action === 'code_required') {
        setTrProcessId(data.processId || data.process_id || 'dummy')
        setTrStep(2)
      } else if (data.success && !data.action) {
        setIsTrConnected(true)
        setShowTrModal(false)
      } else {
        setTrError(data.error || "Identifiants invalides")
      }
    } catch (err) {
      setTrError("Serveur injoignable")
    }
    setTrLoading(false)
    setTimeout(() => { authLockRef.current = false }, 5000)
  }

  const handleTrVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    authLockRef.current = true
    setTrLoading(true)
    setTrError('')
    try {
      const res = await fetch('http://localhost:5000/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ processId: trProcessId, code: trSms, phone: trPhone.replace(/\s+/g, '') })
      })
      const data = await res.json()
      if (data.success) {
        setIsTrConnected(true)
        setShowTrModal(false)
        setTrStep(1)
        setTrSms('')
      } else {
        setTrError(data.error || "Code SMS invalide")
      }
    } catch (err) {
      setTrError("Serveur injoignable")
    }
    setTrLoading(false)
    setTimeout(() => { authLockRef.current = false }, 5000)
  }

  const patrimonyTabs = [
    { id: 'portfolio', label: 'Vue d\'ensemble', icon: LayoutDashboardIcon },
    { id: 'cash', label: 'Économies & Cash', icon: Wallet },
    { id: 'calendar', label: 'Calendrier', icon: Calendar },
    { id: 'tax', label: 'Optimisation Fiscale', icon: ShieldCheck },
    { id: 'alts', label: 'Actifs Alternatifs', icon: Diamond }
  ]

  const copilotTabs = [
    { id: 'screener', label: 'Radar de Performance', icon: Radar },
  ]

  const marketTabs = [
    { id: 'market', label: 'Prévisions Bancaires', icon: Building },
    { id: 'news', label: 'Actualités & Bloomberg', icon: Newspaper }
  ]

  const allTabs = [...patrimonyTabs, ...copilotTabs, ...marketTabs]

  const handleTrRefresh = async () => {
    if (!isTrConnected) return;
    setIsRefreshingTR(true);
    try {
      await fetch('http://localhost:5000/api/refresh/portfolio', { method: 'POST' });
      // Attendre 3 secondes que le thread finisse
      setTimeout(() => {
        setIsRefreshingTR(false);
        window.location.reload();
      }, 3000);
    } catch (e) {
      console.error(e);
      setIsRefreshingTR(false);
    }
  }

  const handleLogout = async () => {
    try {
      await fetch('http://localhost:5000/api/tr/logout', { method: 'POST' })
    } catch (err) {
      console.error(err)
    }
    await logoutUser()
  }

  return (
    <div className="flex h-screen bg-[#000000] text-slate-300 font-sans selection:bg-slate-800 overflow-hidden relative">
      <PaperDesignBackground themeMode="dark" intensity={0.04} className="fixed inset-0 z-0 opacity-30 mix-blend-screen pointer-events-none" />

      {/* Tax Onboarding Overlay */}
      <AnimatePresence>
        {userProfile && (!userProfile.taxOnboarded || forceTaxModal) && !isAuthChecking && (
          <TaxOnboardingModal userProfile={userProfile} onComplete={(data) => { setUserProfile({...userProfile, ...data, taxOnboarded: true}); setForceTaxModal(false); }} />
        )}
      </AnimatePresence>

      {/* TR Modal Overlay */}
      <AnimatePresence>
        {userProfile?.taxOnboarded && !isAuthChecking && showTrModal && !isTrConnected && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-[#000000]/80 backdrop-blur-xl"
          >
            <motion.div 
              initial={{ scale: 0.95, opacity: 0, y: 10 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: "spring", duration: 0.5 }}
              className="bg-[#050505] border border-white/10 rounded-[2rem] p-10 w-[420px] shadow-[0_0_80px_rgba(255,255,255,0.03)] flex flex-col items-center relative"
            >
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-1 bg-white/20 rounded-b-full"></div>
              
              <div className="w-20 h-20 rounded-[1.5rem] mb-6 overflow-hidden shadow-2xl border border-white/10 bg-white">
                <img 
                  src="https://cdn.brandfetch.io/id5mURhE1s/w/400/h/400/theme/dark/icon.jpeg?c=1bxid64Mup7aczewSAYMX&t=1695070241793" 
                  alt="Trade Republic" 
                  className="w-full h-full object-cover mix-blend-multiply" 
                />
              </div>
              
              <h2 className="text-2xl font-light text-white mb-2 tracking-tight">Trade Republic</h2>
              <div className="flex items-center gap-2 mb-6 text-slate-400">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                <p className="text-sm">Connexion chiffrée & sécurisée</p>
              </div>

              {trError && (
                <div className="w-full bg-red-500/10 text-red-500 border border-red-500/20 text-xs p-3 rounded-xl mb-4 text-center font-medium animate-in fade-in">
                  {trError}
                </div>
              )}
              
              {trStep === 1 ? (
                <form onSubmit={handleTrLogin} className="w-full space-y-5 animate-in fade-in">
                  <div>
                    <label className="text-[10px] text-slate-500 font-bold mb-2 block uppercase tracking-widest pl-1">Numéro de téléphone</label>
                    <input 
                      type="tel" 
                      name="username"
                      value={trPhone} 
                      onChange={e => setTrPhone(e.target.value)} 
                      className="w-full bg-[#0a0a0a] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-white/20 focus:bg-[#0f0f0f] transition-all font-mono text-sm" 
                      placeholder="+33 6 00 00 00 00" 
                      required
                      autoComplete="username"
                      disabled={trLoading}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 font-bold mb-2 block uppercase tracking-widest pl-1">Code PIN</label>
                    <input 
                      type="password" 
                      name="password"
                      value={trPin} 
                      onChange={e => setTrPin(e.target.value)} 
                      className="w-full bg-[#0a0a0a] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-white/20 focus:bg-[#0f0f0f] transition-all text-center tracking-[1em] text-xl font-bold font-mono placeholder:tracking-normal" 
                      placeholder="••••" 
                      maxLength={4} 
                      required
                      autoComplete="current-password"
                      disabled={trLoading}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between pt-2 px-1">
                    <div className="flex items-center gap-3">
                      <input 
                        type="checkbox" 
                        id="save-creds" 
                        checked={saveCredentials} 
                        onChange={e => setSaveCredentials(e.target.checked)} 
                        className="w-4 h-4 rounded border-white/10 bg-[#0a0a0a] accent-white cursor-pointer" 
                      />
                      <label htmlFor="save-creds" className="text-xs text-slate-400 cursor-pointer select-none font-medium">
                        Mémoriser l'appareil
                      </label>
                    </div>
                  </div>
                  
                  <button type="submit" disabled={trLoading} className="w-full bg-white text-black font-semibold rounded-2xl py-4 mt-6 hover:bg-slate-200 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                    {trLoading ? "Connexion..." : "Synchroniser mon portefeuille"}
                    {!trLoading && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M5 12h14M12 5l7 7-7 7"/></svg>}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleTrVerify} className="w-full space-y-5 animate-in slide-in-from-right-4 fade-in duration-300">
                  <div className="text-center mb-2">
                    <p className="text-sm text-slate-300">Un code SMS a été envoyé au</p>
                    <p className="text-sm font-bold text-white mt-1">{trPhone}</p>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 font-bold mb-2 block uppercase tracking-widest pl-1 text-center">Code SMS à 4 chiffres</label>
                    <input 
                      type="text" 
                      name="otp"
                      value={trSms} 
                      onChange={e => setTrSms(e.target.value)} 
                      className="w-full bg-[#0a0a0a] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-white/20 focus:bg-[#0f0f0f] transition-all text-center tracking-[1em] text-2xl font-bold font-mono placeholder:tracking-normal" 
                      placeholder="1234" 
                      maxLength={4} 
                      required
                      autoFocus
                      autoComplete="one-time-code"
                      disabled={trLoading}
                    />
                  </div>
                  <button type="submit" disabled={trLoading} className="w-full bg-emerald-500 text-white font-semibold rounded-2xl py-4 mt-6 hover:bg-emerald-600 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                    {trLoading ? "Vérification..." : "Valider le code"}
                  </button>
                  <div className="text-center mt-4">
                    <button type="button" onClick={() => setTrStep(1)} className="text-xs text-slate-500 hover:text-white transition-colors">
                      Retour
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sidebar */}
      {isAuthChecking ? (
        <div className="flex-1 flex flex-col items-center justify-center z-50 h-screen w-full">
          <div className="w-12 h-12 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mb-4" />
          <p className="text-emerald-400 font-mono text-xs uppercase tracking-widest animate-pulse">Connexion au coffre-fort...</p>
        </div>
      ) : isTrConnected && (
        <>
          <aside className="w-64 shrink-0 border-r border-white/5 bg-[#000000]/80 backdrop-blur-md flex flex-col z-20 relative">
        <div className="h-20 shrink-0 flex flex-col justify-center px-8 border-b border-white/5 gap-1">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="bg-white p-1 rounded-md">
              <TrendingUp className="text-black w-4 h-4 group-hover:scale-110 transition-transform" />
            </div>
            <span className="font-bold text-lg text-white tracking-tight">GenWealth</span>
          </Link>
          {userProfile?.riskProfile && FUND_PROFILES[userProfile.riskProfile] && (
            <div className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded w-fit border ${FUND_PROFILES[userProfile.riskProfile].bgClass} ${FUND_PROFILES[userProfile.riskProfile].textClass} ${FUND_PROFILES[userProfile.riskProfile].borderClass}`}>
              Fonds: {FUND_PROFILES[userProfile.riskProfile].title}
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto custom-scrollbar py-8 px-4 flex flex-col gap-8">
          
          {/* PILIER 1: MON PATRIMOINE */}
          <div className="flex flex-col gap-2">
            <span className="px-4 text-xs font-bold text-slate-500 tracking-wider uppercase mb-1">Mon Patrimoine</span>
            {patrimonyTabs.map((tab) => {
              const isActive = activeTab === tab.id
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive 
                      ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-black' : 'text-slate-500'}`} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* PILIER 2: LE COPILOTE */}
          <div className="flex flex-col gap-2">
            <span className="px-4 text-xs font-bold text-fuchsia-400 tracking-wider uppercase mb-1 flex items-center gap-2">
              <BrainCircuit className="w-3 h-3" /> Copilot
            </span>
            {copilotTabs.map((tab) => {
              const isActive = activeTab === tab.id
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive 
                      ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-black' : 'text-slate-500'}`} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* PILIER 3: LE MARCHÉ */}
          <div className="flex flex-col gap-2">
            <span className="px-4 text-xs font-bold text-emerald-400 tracking-wider uppercase mb-1 flex items-center gap-2">
              <Globe className="w-3 h-3" /> Marché
            </span>
            {marketTabs.map((tab) => {
              const isActive = activeTab === tab.id
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive 
                      ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-black' : 'text-slate-500'}`} />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </nav>

        <div className="p-4 border-t border-white/5">
          <button onClick={handleLogout} className="flex items-center gap-3 px-4 py-3 w-full rounded-xl text-sm font-medium text-slate-500 hover:text-white hover:bg-white/5 transition-colors">
            <LogOut className="w-5 h-5" />
            Déconnexion
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col z-30 relative h-screen min-w-0">
        <header className="h-20 flex items-center justify-between px-10 border-b border-white/5 bg-[#000000]/50 backdrop-blur-sm relative z-30">
          <h2 className="text-xl font-semibold text-white flex items-center gap-3">
            {allTabs.find(t => t.id === activeTab)?.label}
          </h2>
          <div className="flex items-center gap-6">
            {bbgLive.running && (
              <div className="flex items-center gap-2 bg-red-500/10 text-red-400 px-3 py-1.5 rounded-full text-xs font-bold border border-red-500/20">
                <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse"></div>
                Bloomberg Live ({bbgLive.segments_captured} IA)
              </div>
            )}
            <div className="flex items-center gap-3">
              {/* TR Badge */}
              <div 
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${isTrConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 cursor-pointer hover:bg-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}
                onClick={isTrConnected ? handleTrRefresh : undefined}
                title={isTrConnected ? "Cliquez pour forcer l'actualisation du patrimoine" : ""}
              >
                <img src="https://cdn.brandfetch.io/id5mURhE1s/w/400/h/400/theme/dark/icon.jpeg?c=1bxid64Mup7aczewSAYMX&t=1695070241793" alt="TR" className={`w-4 h-4 rounded-full mix-blend-screen ${isRefreshingTR ? 'animate-spin' : ''}`} />
                TR {isRefreshingTR ? 'Actualisation...' : isTrConnected ? 'Synchronisé' : 'Déconnecté'}
              </div>

              {/* Gemini Badge */}
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold border ${aiConnections.gemini ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                <Sparkles className="w-4 h-4" />
                Gemini {aiConnections.gemini ? 'Connecté' : 'Déconnecté'}
              </div>
            </div>
            <div onClick={() => setShowUserProfileModal(true)} className="w-9 h-9 rounded-full bg-slate-800 border border-white/10 flex items-center justify-center text-white font-bold cursor-pointer hover:bg-slate-700 transition-colors shadow-[0_0_10px_rgba(255,255,255,0.1)]">
              {userProfile?.name ? userProfile.name.charAt(0).toUpperCase() : 'U'}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-scroll p-10 custom-scrollbar">
          <div className="max-w-[1200px] mx-auto w-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
              >
                {activeTab === 'portfolio' && <PortfolioTab isTrConnected={isTrConnected} />}
                {activeTab === 'screener' && <AssetScreenerTab isTrConnected={isTrConnected} onRequestTrConnect={() => { setShowTrModal(true); setIsAuthChecking(false); }} />}
                {activeTab === 'cash' && <CashTab isTrConnected={isTrConnected} />}
                {activeTab === 'market' && <MarketTab />}
                {activeTab === 'news' && <NewsTab />}
                {activeTab === 'calendar' && <CalendarTab />}
                {activeTab === 'tax' && <TaxOptimizationTab userProfile={userProfile} onRequestEdit={() => setForceTaxModal(true)} />}
                {activeTab === 'alts' && <AlternativeAssetsTab />}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>

      <div className="fixed bottom-0 left-64 right-0 z-0 pointer-events-none opacity-20">
        <Wave fill="#ffffff" />
      </div>

      {/* Floating AI Chat */}
      <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end">
        <AnimatePresence>
          {isChatOpen && (
            <motion.div 
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="bg-[#050505] border border-white/10 shadow-2xl rounded-2xl w-80 sm:w-96 h-[500px] mb-4 flex flex-col overflow-hidden"
            >
              <div className="h-14 border-b border-white/10 flex items-center justify-between px-4 bg-white/5 backdrop-blur-md shrink-0">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-sky-400" />
                  <h2 className="text-sm font-bold text-white uppercase tracking-widest">WealthAI</h2>
                </div>
                <button onClick={() => setIsChatOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                  <ChevronDown className="w-5 h-5" />
                </button>
              </div>

              <div ref={chatScrollRef} className="flex-1 p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar text-sm">
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-bold text-sky-400">WealthAI</span>
                  <div className="bg-white/5 backdrop-blur-sm border border-white/10 shadow-[inset_0_1px_4px_rgba(255,255,255,0.05)] rounded-xl rounded-tl-none p-3 text-slate-300">
                    Bonjour ! Je suis connecté directement via votre compte. Que souhaitez-vous analyser aujourd'hui ?
                  </div>
                </div>
                
                {chatMessages.map((msg, i) => (
                  <div key={i} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <span className={`text-xs font-bold ${msg.role === 'user' ? 'text-slate-400' : 'text-sky-400'}`}>
                      {msg.role === 'user' ? 'Vous' : 'WealthAI'}
                    </span>
                    <div className={`p-3 border backdrop-blur-sm shadow-[inset_0_1px_4px_rgba(255,255,255,0.05)] rounded-xl ${msg.role === 'user' ? 'bg-white/10 border-white/20 rounded-tr-none text-white' : 'bg-white/5 border-white/10 rounded-tl-none text-slate-300'}`}>
                      {msg.role === 'user' ? (
                        <div className="whitespace-pre-wrap">{msg.text}</div>
                      ) : (
                        <ReactMarkdown>{msg.text}</ReactMarkdown>
                      )}
                    </div>
                  </div>
                ))}
                
                {isChatLoading && (
                  <div className="flex flex-col gap-1 items-start">
                    <span className="text-xs font-bold text-sky-400">WealthAI</span>
                    <div className="bg-white/5 backdrop-blur-sm border border-white/10 shadow-[inset_0_1px_4px_rgba(255,255,255,0.05)] rounded-xl rounded-tl-none p-3 text-slate-400 flex gap-2 items-center">
                      <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                      <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                      <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                    </div>
                  </div>
                )}
              </div>
              
              <div className="p-3 border-t border-white/5 bg-[#050505] shrink-0">
                <div className="flex bg-[#0a0a0a] border border-white/10 rounded-xl">
                  <input 
                    type="text" 
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSendChatMessage()}
                    placeholder="Poser une question..." 
                    className="flex-1 bg-transparent px-4 py-2 text-sm focus:outline-none text-white placeholder-slate-600" 
                  />
                  <button 
                    onClick={handleSendChatMessage}
                    disabled={isChatLoading}
                    className="p-2 m-1 bg-white/10 backdrop-blur-md border border-white/20 rounded-lg text-white shadow-md hover:bg-white/20 disabled:opacity-50 transition-all duration-300"
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button 
          onClick={() => setIsChatOpen(!isChatOpen)}
          className="group relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-500 hover:scale-110 active:scale-95 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
        >
          {/* Liquid Glass Background */}
          <div className="absolute inset-0 rounded-full bg-white/5 backdrop-blur-xl border border-white/20 shadow-[inset_0_4px_10px_rgba(255,255,255,0.1),inset_0_-4px_10px_rgba(0,0,0,0.4)] group-hover:bg-white/10 transition-colors duration-500" />
          
          {/* Specular Highlight (Reflection) */}
          <div className="absolute inset-x-2 top-1 h-1/3 rounded-full bg-gradient-to-b from-white/40 to-transparent blur-[1px]" />
          
          {/* Content */}
          <div className="relative z-20 flex items-center justify-center">
            {isChatOpen ? <ChevronDown className="w-7 h-7 text-white drop-shadow-md" /> : <BrainCircuit className="w-7 h-7 text-white drop-shadow-md" />}
          </div>
        </button>
      </div>
        </>


      )}
      <AnimatePresence>
        {showUserProfileModal && userProfile && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }} className="w-full max-w-3xl max-h-[90vh] overflow-y-auto custom-scrollbar bg-[#0a0a0a] border border-white/10 rounded-3xl p-6 md:p-10 relative shadow-2xl">
              <button onClick={() => setShowUserProfileModal(false)} className="absolute top-6 right-6 text-slate-500 hover:text-white z-10 bg-[#050505] p-2 rounded-full border border-white/10 transition-colors"><X className="w-5 h-5" /></button>
              <SettingsTab userProfile={userProfile} onRequestEdit={() => { setShowUserProfileModal(false); setForceTaxModal(true); }} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ==========================================
// ==========================================
// PLACEMENTS TAB (Placements & Opportunités)
// ==========================================

function LayoutDashboardIcon(props: any) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>
}

// ==========================================
// SMART AI INSIGHT BANNER
function SmartAiInsight({ investments, truePnlPct }: { investments: any, truePnlPct: number }) {
  const [insight, setInsight] = useState<string | null>(null)

  const CACHE_KEY = 'wealthai_insight_cache'
  const TIME_KEY = 'wealthai_insight_time'

  useEffect(() => {
    let mounted = true;
    const fetchInsight = async () => {
      try {
        // Try to load cached insight first
        const cached = localStorage.getItem(CACHE_KEY)
        const cachedTime = localStorage.getItem(TIME_KEY)
        if (cached && cachedTime && (Date.now() - parseInt(cachedTime)) < 1200000) {
          if (mounted) setInsight(cached)
          return
        }

        const resNews = await fetch('http://localhost:5000/api/data/news')
        const dataNews = await resNews.json()
        
        const resTruth = await fetch('http://localhost:5000/api/data/truth_social').catch(() => ({ json: () => [] }))
        const dataTruth = await resTruth.json()
        
        const resIndices = await fetch('http://localhost:5000/api/data/market_indices').catch(() => ({ json: () => ({}) }))
        const dataIndices: any = await resIndices.json()

        // Extract market context
        let marketContext = ""
        try {
          const sp500 = dataIndices['S&P 500']?.change_pct
          const nasdaq = dataIndices['NASDAQ']?.change_pct
          if (sp500 !== undefined && nasdaq !== undefined) {
             marketContext = `Réaction actuelle du marché : S&P500 (${sp500 > 0 ? '+':''}${sp500}%), NASDAQ (${nasdaq > 0 ? '+':''}${nasdaq}%).`
          }
        } catch (e) {}

        // Find if there is a critical breaking news today (e.g., Trump, War, etc.)
        const yesterday = new Date()
        yesterday.setDate(yesterday.getDate() - 1)
        
        const recentNews = (dataNews?.items || []).filter((item: any) => new Date(item.published_iso || item.published) >= yesterday)
        const recentTruths = (dataTruth || []).filter((item: any) => new Date(item.created_at) >= yesterday)
        
        // Take top 3 most critical recent news + top 2 truth social posts
        const topNews = recentNews.slice(0, 3).map((n:any) => n.title).join(" | ")
        const topTruths = recentTruths.slice(0, 2).map((t:any) => `Donald Trump via Truth Social: ${t.content}`).join(" | ")
        const mergedNews = `${topTruths ? topTruths + ' | ' : ''}${topNews}`

        const positions = (investments || []).map((i:any) => i.name || i.ticker).slice(0, 5).join(", ")

        let prompt = ""
        if (mergedNews.trim().length > 0) {
            prompt = `Voici mon portefeuille partiel (${positions}) avec une performance de ${truePnlPct}%. Voici les news et déclarations brûlantes des dernières heures : ${mergedNews}. ${marketContext}
            Génère UNE SEULE PHRASE D'ALERTE ou d'INSIGHT (très courte, style 'breaking news intelligente') en tant que WealthAI pour m'informer de l'impact immédiat potentiel de ces informations sur mes actifs ou le marché. 
            CRITIQUE : Vérifie la réaction actuelle du marché (indices ci-dessus). Si les news sont dramatiques mais que le marché monte (ex: NASDAQ positif), signale explicitement que le marché "ignore" ou "digère bien" la nouvelle au lieu d'être alarmiste. Sois direct, percutant, pas de politesse.`
        } else {
            prompt = `Voici mon portefeuille partiel (${positions}) avec une performance de ${truePnlPct}%. ${marketContext}
            Génère UNE SEULE PHRASE D'INSIGHT (très courte) en tant que WealthAI pour résumer la situation de mon portefeuille face au marché du jour. Sois direct, percutant, pas de politesse. Ne parle pas de news s'il n'y en a pas.`
        }

        const resChat = await fetch('http://localhost:5000/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: prompt })
        })
        const chatData = await resChat.json()
        if (mounted && chatData.response) {
           const finalInsight = chatData.response.replace(/\*/g, '')
           setInsight(finalInsight)
           localStorage.setItem(CACHE_KEY, finalInsight)
           localStorage.setItem(TIME_KEY, Date.now().toString())
        }
      } catch (err) {
        console.error("AI Insight Error:", err)
      }
    }
    if (investments && investments.length > 0 && truePnlPct !== undefined) {
      fetchInsight()
    }
    return () => { mounted = false }
  }, [investments, truePnlPct])

  if (!investments || investments.length === 0) return null

  if (!insight) {
    return (
      <div className="bg-gradient-to-r from-sky-900/40 to-blue-900/10 border border-sky-500/20 rounded-2xl p-4 flex items-center gap-4 mb-6 shadow-lg shadow-sky-900/20 backdrop-blur-md">
        <div className="w-10 h-10 bg-sky-500/20 rounded-full flex items-center justify-center shrink-0 animate-pulse">
          <BrainCircuit className="w-5 h-5 text-sky-400" />
        </div>
        <div className="flex-1">
          <h4 className="text-sky-400 font-bold text-xs uppercase tracking-wider mb-1">Alerte Proactive WealthAI</h4>
          <div className="h-4 bg-sky-500/10 rounded w-3/4 animate-pulse"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-r from-sky-900/40 to-blue-900/10 border border-sky-500/20 rounded-2xl p-4 flex items-center gap-4 mb-6 shadow-lg shadow-sky-900/20 backdrop-blur-md">
      <div className="w-10 h-10 bg-sky-500/20 rounded-full flex items-center justify-center shrink-0 animate-pulse">
        <BrainCircuit className="w-5 h-5 text-sky-400" />
      </div>
      <div>
        <h4 className="text-sky-400 font-bold text-xs uppercase tracking-wider mb-1">Alerte Proactive WealthAI</h4>
        <p className="text-slate-200 text-sm">{insight}</p>
      </div>
    </div>
  )
}

// ==========================================
// PORTFOLIO TAB (Vue Globale Finary-style)
// ==========================================
function PortfolioTab({ isTrConnected }: { isTrConnected: boolean }) {
  const [performance, setPerformance] = useState<any>(null)
  const [hideAmounts, setHideAmounts] = useState(false)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setHideAmounts(localStorage.getItem('hideAmounts') === 'true')
    }
  }, [])
  
  const toggleHideAmounts = () => {
    const newVal = !hideAmounts
    setHideAmounts(newVal)
    if (typeof window !== 'undefined') {
      localStorage.setItem('hideAmounts', String(newVal))
    }
  }
  const [investments, setInvestments] = useState<any>(null)
  const [cashAnalysis, setCashAnalysis] = useState<any>(null)
  const [loadingPerf, setLoadingPerf] = useState(true)
  const [loadingInv, setLoadingInv] = useState(true)

  useEffect(() => {
    if (isTrConnected) {
      // 1. Performance data
      const cachedPerf = localStorage.getItem('wealth_perf')
      if (cachedPerf) {
        setPerformance(JSON.parse(cachedPerf))
        setLoadingPerf(false)
      } else {
        setLoadingPerf(true)
      }

      fetch('http://localhost:5000/api/portfolio/performance?refresh=true&t=' + Date.now())
        .then(res => res.json())
        .then(data => {
          if (data?.data) {
            setPerformance(data.data)
            localStorage.setItem('wealth_perf', JSON.stringify(data.data))
          }
          setLoadingPerf(false)
        })
        .catch(err => { console.error(err); setLoadingPerf(false) })

      // 2. Investments data
      const cachedInv = localStorage.getItem('wealth_inv')
      if (cachedInv) {
        setInvestments(JSON.parse(cachedInv))
        setLoadingInv(false)
      } else {
        setLoadingInv(true)
      }

      fetch('http://localhost:5000/api/wallet/investments')
        .then(res => res.json())
        .then(data => {
          if (data) {
            setInvestments(data)
            localStorage.setItem('wealth_inv', JSON.stringify(data))
          }
          setLoadingInv(false)
        })
        .catch(err => { console.error(err); setLoadingInv(false) })
        
      fetch('http://localhost:5000/api/cash/analysis')
        .then(res => res.json())
        .then(data => setCashAnalysis(data?.data))
        .catch(console.error)
    } else {
      setLoadingPerf(false)
      setLoadingInv(false)
    }
  }, [isTrConnected])

  const [chartRange, setChartRange] = useState('1M')

  const totalValueNum = investments && Array.isArray(investments) ? investments.reduce((acc: number, inv: any) => acc + (parseFloat(inv.total_value) || 0), 0) : 0
  const cashAmountNum = typeof cashAnalysis?.current_cash === 'number' ? cashAnalysis.current_cash : (cashAnalysis?.cash_flow?.length > 0 ? Math.max(0, cashAnalysis.cash_flow.reduce((acc: number, c: any) => acc + (c.net || 0), 0)) : 0)
  const grossWealth = totalValueNum + cashAmountNum

  const truePnlPct = performance?.true_pnl_pct || 0
  const lastTwr = isTrConnected && performance?.portfolio && performance.portfolio.length > 0 
    ? performance.portfolio[performance.portfolio.length - 1].value 
    : 0
  const baseValue = grossWealth / (1 + lastTwr / 100)
  
  const chartDataRaw = isTrConnected && performance?.portfolio && performance.portfolio.length > 0 ? performance.portfolio.map((pt: any) => ({
    name: pt.date,
    // Provide both raw % and computed rough EUR value for tooltip
    value: pt.value,
    eurValue: Math.round(baseValue * (1 + (pt.value / 100)))
  })) : [
    { name: 'Jan', value: 0 }, { name: 'Fév', value: 0 }, { name: 'Mar', value: 0 }
  ]

  const getChartData = () => {
    if (chartRange === '1M') return chartDataRaw.slice(-30)
    if (chartRange === '6M') return chartDataRaw.slice(-180)
    if (chartRange === '1Y') return chartDataRaw.slice(-365)
    return chartDataRaw // MAX
  }
  const chartData = getChartData()

  let stockValue = 0, cryptoValue = 0, altValue = 0
  if (investments) {
     investments.forEach((inv: any) => {
        if (inv.instrumentType === 'crypto') cryptoValue += parseFloat(inv.total_value) || 0
        else if (inv.instrumentType === 'derivative' || inv.instrumentType === 'bond') altValue += parseFloat(inv.total_value) || 0
        else stockValue += parseFloat(inv.total_value) || 0
     })
  }
  const totalAllocation = stockValue + cryptoValue + altValue + cashAmountNum || 1



return (
  <div className="space-y-8 pb-20">
    <SmartAiInsight investments={investments} truePnlPct={truePnlPct} />
    
    <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h2 className="text-slate-500 text-sm font-bold uppercase tracking-widest">Patrimoine Brut</h2>
            <button onClick={toggleHideAmounts} className="text-slate-500 hover:text-white transition-colors ml-2" title="Masquer les montants">
              {hideAmounts ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <div className="flex items-baseline gap-4">
            <h1 className="text-5xl lg:text-6xl font-light text-white tracking-tight">
              {isTrConnected && !isNaN(grossWealth) ? (hideAmounts ? "**** €" : new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(grossWealth)) : "0,00 €"}
            </h1>
            {isTrConnected && performance && (
               <span className={`font-bold px-2 py-1 rounded-md text-sm flex items-center gap-1 ${truePnlPct >= 0 ? 'text-emerald-400 bg-emerald-400/10' : 'text-red-400 bg-red-400/10'}`}>
                 {truePnlPct >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                 {truePnlPct > 0 ? '+' : ''}{truePnlPct.toFixed(2)}%
               </span>
            )}
          </div>
        </div>
        
        {/* Range Selector */}
        <div className="flex bg-[#050505] border border-white/10 rounded-lg p-1">
          {['1M', '6M', '1Y', 'MAX'].map(r => (
            <button 
              key={r}
              onClick={() => setChartRange(r)}
              className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${chartRange === r ? 'bg-white text-black' : 'text-slate-500 hover:text-white'}`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart */}
      <div className="h-[320px] w-full mt-8">
        {!isTrConnected ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 border border-white/5 rounded-2xl bg-white/[0.02]">
            <LineChart className="w-8 h-8 mb-3 opacity-20" />
            <p className="text-sm">Connectez Trade Republic pour afficher l'évolution de vos performances</p>
          </div>
        ) : loadingPerf ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 border border-white/5 rounded-2xl bg-white/[0.02]">
            <div className="w-6 h-6 border-2 border-slate-500 border-t-white rounded-full animate-spin mb-3"></div>
            <p className="text-sm">Analyse de vos performances historiques...</p>
          </div>
        ) : (!performance || chartData.length <= 3) ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 border border-white/5 rounded-2xl bg-white/[0.02]">
            <LineChart className="w-8 h-8 mb-3 opacity-20" />
            <p className="text-sm">Pas assez de données pour afficher l'historique</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ffffff" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{fill: '#475569', fontSize: 12}} 
                tickFormatter={(val) => `${val}%`}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0a0a0a', borderColor: '#ffffff1a', borderRadius: '12px' }}
                itemStyle={{ color: '#fff', fontWeight: 'bold' }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: any, name: any, props: any) => [
                  `${value}% (${new Intl.NumberFormat('fr-FR').format(props.payload.eurValue || 0)} €)`,
                  'Performance'
                ]}
              />
              <Area type="monotone" dataKey="value" stroke="#ffffff" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Asset Allocation Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
        {[
          { title: 'Actions & ETF', amount: stockValue, icon: LineChart, color: 'text-blue-400 bg-blue-400/10' },
          { title: 'Crypto', amount: cryptoValue, icon: Activity, color: 'text-purple-400 bg-purple-400/10' },
          { title: 'Liquidités', amount: cashAmountNum, icon: Wallet, color: 'text-emerald-400 bg-emerald-400/10' },
          { title: 'Alternatif', amount: altValue, icon: BarChart3, color: 'text-amber-400 bg-amber-400/10' }
        ].map((asset, i) => (
          <div key={i} className="bg-[#050505] border border-white/5 rounded-2xl p-5 hover:bg-white/[0.02] transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className={`p-2 rounded-xl ${asset.color}`}>
                <asset.icon className="w-5 h-5" />
              </div>
              <span className="text-slate-500 font-bold text-sm">
                {isTrConnected ? `${Math.round((asset.amount/totalAllocation)*100)}%` : '0%'}
              </span>
            </div>
            <h3 className="text-slate-400 text-sm font-medium mb-1">{asset.title}</h3>
            <p className="text-xl font-medium text-white">
              {isTrConnected && !isNaN(asset.amount) ? (hideAmounts ? "**** €" : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(asset.amount) + ' €') : '0 €'}
            </p>
          </div>
        ))}
      </div>

      {/* Investments List */}
      <div className="bg-[#050505] border border-white/5 rounded-2xl p-6 mt-8">
        <h3 className="text-lg font-bold text-white mb-6">Vos Actifs (Positions)</h3>
        <div className="space-y-3">
          {!isTrConnected ? (
            <div className="text-sm text-slate-500 text-center py-10">Connectez votre compte pour voir vos actifs</div>
          ) : loadingInv ? (
            <div className="flex items-center justify-center py-10">
              <div className="w-6 h-6 border-2 border-slate-500 border-t-white rounded-full animate-spin"></div>
            </div>
          ) : (!investments || !Array.isArray(investments) || investments.length === 0) ? (
            <div className="text-sm text-slate-500 text-center py-10">Aucune position trouvée</div>
          ) : (
            investments.sort((a: any, b: any) => b.total_value - a.total_value).map((inv: any, i: number) => (
              <AssetRow key={i} inv={inv} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ==========================================
// CASH TAB (Économies, Cash Flow & Transactions)
// ==========================================
function CashTab({ isTrConnected }: { isTrConnected: boolean }) {
  const [cashAnalysis, setCashAnalysis] = useState<any>(null)
  const [pieRange, setPieRange] = useState('1M')

  useEffect(() => {
    if (isTrConnected) {
      fetch('http://localhost:5000/api/cash/analysis')
        .then(res => res.json())
        .then(data => setCashAnalysis(data?.data))
        .catch(console.error)
    }
  }, [isTrConnected])

  const transactions = cashAnalysis?.transactions || []
  const cashFlow = cashAnalysis?.cash_flow || []
  // Estimate liquidities, floor at 0 if investments exceed tracked income
  const cashBalance = typeof cashAnalysis?.current_cash === 'number' ? cashAnalysis.current_cash : (cashFlow.length > 0 ? Math.max(0, cashFlow.reduce((acc: number, c: any) => acc + (c.net || 0), 0)) : 0)

  const getTransactionIcon = (tx: any) => {
    const title = (tx.title || tx.merchant || "").toLowerCase()
    if (title.includes('dividende')) return <Gift className="w-4 h-4 text-purple-400" />
    if (title.includes('virement') || title.includes('dépôt') || title.includes('deposit')) return <ArrowRightLeft className="w-4 h-4 text-blue-400" />
    if (title.includes('carte') || title.includes('saveback') || title.includes('card')) return <CreditCard className="w-4 h-4 text-amber-400" />
    if (tx.amount < 0) return <TrendingDown className="w-4 h-4 text-slate-400" />
    return <TrendingUp className="w-4 h-4 text-emerald-400" />
  }

  const currentMonthData = cashFlow.length > 0 ? cashFlow[cashFlow.length - 1] : { income: 0, expense: 0, investment: 0, savings: 0 }
  const remainingBudget = Math.max(0, currentMonthData.income - currentMonthData.expense - currentMonthData.investment)

  const getPieData = () => {
    let income = 0, expense = 0, investment = 0
    let months = cashFlow
    if (pieRange === '1M') months = cashFlow.slice(-1)
    else if (pieRange === '6M') months = cashFlow.slice(-6)
    else if (pieRange === '1Y') months = cashFlow.slice(-12)
    
    months.forEach((m: any) => {
      income += m.income
      expense += m.expense
      investment += m.investment
    })
    
    return [
      { name: 'Dépenses', value: expense, fill: '#f87171' },
      { name: 'Investi', value: investment, fill: '#a78bfa' },
      { name: 'Épargne', value: Math.max(0, income - expense - investment), fill: '#34d399' }
    ].filter(d => d.value > 0)
  }
  const pieData = getPieData()

  return (
    <div className="space-y-8 pb-20">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-slate-500 text-sm font-bold uppercase tracking-widest">Liquidités & Épargne</h2>
          <h1 className="text-4xl lg:text-5xl font-light text-white tracking-tight">
            {isTrConnected && !isNaN(cashBalance) ? new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(cashBalance) : "0,00 €"}
          </h1>
        </div>
        
        {isTrConnected && (
          <div className="bg-[#050505] border border-white/5 rounded-2xl p-4 flex flex-col items-end">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">Reste à vivre (Ce mois)</h3>
            <div className="text-2xl font-bold text-white">{remainingBudget.toFixed(2)} €</div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Flux Chart */}
        <div className="col-span-1 lg:col-span-2 bg-[#050505] border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-bold text-white mb-6">Évolution de la trésorerie nette</h3>
          <div className="h-[250px] w-full">
            {(!isTrConnected || cashFlow.length === 0) ? (
              <div className="w-full h-full flex items-center justify-center text-slate-600 bg-white/[0.02] rounded-xl border border-white/5">
                Données indisponibles
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cashFlow}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="month" stroke="#475569" tick={{fontSize: 12}} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0a0a0a', borderColor: '#ffffff1a', borderRadius: '12px' }}
                    itemStyle={{ color: '#fff', fontWeight: 'bold' }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Bar dataKey="net" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Camembert (Pie Chart) */}
        <div className="col-span-1 bg-[#050505] border border-white/5 rounded-2xl p-6 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-bold text-white">Flux Trésorerie</h3>
            <div className="flex bg-[#0a0a0a] border border-white/10 rounded-lg p-0.5">
              {['1M', '6M', '1Y', 'MAX'].map(r => (
                <button key={r} onClick={() => setPieRange(r)} className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${pieRange === r ? 'bg-white text-black' : 'text-slate-500 hover:text-white'}`}>
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 min-h-[200px] flex items-center justify-center relative">
            {(!isTrConnected || pieData.length === 0) ? (
              <div className="text-sm text-slate-500">Aucune donnée</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value" stroke="none">
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0a0a0a', borderColor: '#ffffff1a', borderRadius: '12px' }}
                    itemStyle={{ color: '#fff', fontWeight: 'bold' }}
                    formatter={(val) => `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(val as number)} €`}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
            {isTrConnected && pieData.length > 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-xs text-slate-500 font-bold uppercase">Total</span>
                <span className="text-lg font-bold text-white">{new Intl.NumberFormat('fr-FR').format(pieData.reduce((acc, d) => acc + d.value, 0))} €</span>
              </div>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 mt-4">
            {pieData.map((d, i) => (
              <div key={i} className="flex flex-col items-center p-2 rounded-lg bg-[#0a0a0a] border border-white/5">
                <div className="w-2 h-2 rounded-full mb-1" style={{ backgroundColor: d.fill }}></div>
                <span className="text-[10px] text-slate-400 font-medium mb-0.5">{d.name}</span>
                <span className="text-xs font-bold text-white">{new Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(d.value)} €</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-[#050505] border border-white/5 rounded-2xl p-6">
        <h3 className="text-lg font-bold text-white mb-6">Historique des transactions</h3>
        <div className="space-y-3">
          {(!isTrConnected || transactions.length === 0) ? (
            <div className="text-sm text-slate-500 text-center py-10">Connectez votre compte pour voir l'historique</div>
          ) : (
            transactions.slice(0, 15).map((tx: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-4 bg-[#0a0a0a] border border-white/5 rounded-xl hover:border-white/10 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center overflow-hidden">
                    {tx.isin ? (
                      <img src={`https://assets.traderepublic.com/img/logos/${tx.isin}/dark.svg`} className="w-full h-full object-cover" alt="logo" onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextElementSibling?.classList.remove('hidden') }} />
                    ) : tx.logo ? (
                      <img src={tx.logo} className="w-full h-full object-cover" alt="logo" onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextElementSibling?.classList.remove('hidden') }} />
                    ) : null}
                    <div className={`${(tx.isin || tx.logo) ? 'hidden' : ''} flex items-center justify-center w-full h-full`}>
                      {getTransactionIcon(tx)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-white font-medium">{tx.title || tx.merchant || "Transaction"}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{new Date(tx.date).toLocaleDateString('fr-FR', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}</div>
                  </div>
                </div>
                <div className={`text-base font-bold ${tx.amount > 0 ? 'text-emerald-400' : 'text-white'}`}>
                  {tx.amount > 0 ? '+' : ''}{tx.amount.toFixed(2)} €
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ==========================================
// CALENDAR TAB (Évènements, Dividendes)
// ==========================================
function CalendarTab() {
  const [events, setEvents] = useState<any[]>([])
  const [globalEvents, setGlobalEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 1. Fetch wallet investments to get the tickers/ISINs
    fetch('http://localhost:5000/api/wallet/investments')
      .then(res => res.json())
      .then(investments => {
        const isins = Array.isArray(investments) ? investments.map((inv: any) => inv.isin).filter(Boolean) : [];
        const tickers = [...isins, 'AAPL', 'TSLA', 'NVDA', 'MSFT']
        
        // 2. Fetch events for these tickers
        return fetch('http://localhost:5000/api/portfolio-events', { 
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers })
        });
      })
      .then(res => res.json())
      .then(data => {
        setEvents(data?.events || [])
        setLoading(false)
      })
      .catch(() => {
        setEvents([])
        setLoading(false)
      })

    // 3. Fetch global earnings & macro events
    fetch('http://localhost:5000/api/earnings')
      .then(res => res.json())
      .then(data => setGlobalEvents(data?.data || []))
      .catch(console.error)
  }, [])

  return (
    <div className="space-y-8 pb-20">
      <div className="flex flex-col gap-1 mb-6">
        <h2 className="text-slate-500 text-sm font-bold uppercase tracking-widest">Calendrier Financier</h2>
        <h1 className="text-4xl font-light text-white tracking-tight">Dividendes & Résultats</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Portfolio Events */}
        <div className="bg-[#050505] border border-white/5 rounded-2xl p-6 flex flex-col">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
            <Wallet className="w-5 h-5 text-emerald-400" /> Relatif à vos actifs
          </h3>
          {loading ? (
             <div className="flex-1 flex items-center justify-center">
               <div className="w-6 h-6 border-2 border-slate-500 border-t-white rounded-full animate-spin"></div>
             </div>
          ) : events.length === 0 ? (
             <div className="flex-1 flex items-center justify-center text-slate-500">Aucun évènement imminent pour votre portefeuille</div>
          ) : (
             <div className="space-y-4">
               {events.map((ev, i) => (
                 <div key={i} className="flex items-center gap-4 p-4 border border-white/5 bg-[#0a0a0a] rounded-xl hover:border-white/10 transition-colors">
                   <div className="flex flex-col items-center justify-center bg-white/5 rounded-lg w-14 h-14 shrink-0">
                     <span className="text-[10px] text-slate-500 uppercase">{new Date(ev.date).toLocaleString('fr-FR', { month: 'short' })}</span>
                     <span className="text-lg font-bold text-white">{new Date(ev.date).getDate()}</span>
                   </div>
                   <div className="flex-1">
                     <div className="text-base font-bold text-white flex items-center gap-2">
                       {ev.type === 'dividend' ? <Gift className="w-4 h-4 text-purple-400" /> : <Bell className="w-4 h-4 text-blue-400" />}
                       {ev.ticker} - {ev.name}
                     </div>
                     <div className="text-xs text-slate-400 mt-1">
                       {ev.type === 'dividend' ? `Dividende annoncé : ${ev.amount} €` : "Publication des résultats"}
                     </div>
                   </div>
                 </div>
               ))}
             </div>
          )}
        </div>

        {/* Global Macro & Earnings */}
        <div className="bg-[#050505] border border-white/5 rounded-2xl p-6 flex flex-col">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
            <LineChart className="w-5 h-5 text-blue-400" /> Principaux Résultats (Macro)
          </h3>
          {globalEvents.length === 0 ? (
             <div className="flex-1 flex items-center justify-center text-slate-500">Aucun évènement global imminent</div>
          ) : (
             <div className="space-y-3 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
               {globalEvents.slice(0, 15).map((ev, i) => (
                 <div key={i} className="flex items-center justify-between p-3 border border-white/5 bg-[#0a0a0a] rounded-xl hover:border-white/10 transition-colors">
                   <div className="flex items-center gap-4">
                     <div className="flex flex-col items-center justify-center w-10 shrink-0">
                       <span className="text-[10px] text-slate-500 uppercase">{new Date(ev.date).toLocaleString('fr-FR', { month: 'short' })}</span>
                       <span className="text-sm font-bold text-white">{new Date(ev.date).getDate()}</span>
                     </div>
                     <div>
                       <div className="text-sm font-bold text-white">{ev.ticker} <span className="font-normal text-slate-500 text-xs ml-1 line-clamp-1">{ev.name}</span></div>
                       {ev.eps_estimate !== null && <div className="text-[10px] text-slate-400 mt-0.5">EPS Est: ${ev.eps_estimate}</div>}
                     </div>
                   </div>
                 </div>
               ))}
             </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ==========================================
// NEWS TAB (Flux RSS, Bloomberg TV)
// ==========================================
function NewsTab() {
  const [streamData, setStreamData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [newsData, setNewsData] = useState<any[]>([])
  const [loadingNews, setLoadingNews] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('http://localhost:5000/api/data/news').then(res => res.json()).catch(() => ({})),
      fetch('http://localhost:5000/api/data/truth_social').then(res => res.json()).catch(() => ([]))
    ]).then(([newsRes, truthRes]) => {
      let newsItems = newsRes?.items || []
      
      const truthItems = (Array.isArray(truthRes) ? truthRes : []).map((t: any) => ({
        title: `Donald Trump via Truth Social`,
        summary: t.content,
        link: t.url || 'https://truthsocial.com',
        published: t.created_at,
        isTruth: true,
        avatar: t.avatar
      }))
      
      const merged = [...newsItems, ...truthItems].sort((a, b) => {
        return new Date(b.published).getTime() - new Date(a.published).getTime()
      })
      
      setNewsData(merged)
      setLoadingNews(false)
    })
    
    // Check if Bloomberg Live is already running (optional, but video is always visible)
    fetch('http://localhost:5000/api/bloomberg-live/status')
      .then(res => res.json())
      .then(data => {
        if (data.running) setStreamData(data)
      })
      .catch(() => {})
  }, [])

  return (
    <div className="space-y-8 pb-20">
      <div className="flex flex-col gap-1">
        <h2 className="text-slate-500 text-sm font-bold uppercase tracking-widest">Veille Marché</h2>
        <h1 className="text-4xl font-light text-white tracking-tight">Actualités & Live TV</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#050505] border border-white/5 rounded-2xl p-6 flex flex-col min-h-[400px]">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2"><Tv className="w-5 h-5 text-red-400" /> Bloomberg Live</h3>
          </div>

          <div className="flex-1 bg-black rounded-xl border border-white/10 flex flex-col items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 w-full h-full">
              <iframe 
                className="w-full h-full pointer-events-none"
                src="https://www.youtube.com/embed/QB5BNdBFujE?autoplay=1&mute=1&controls=0&modestbranding=1&disablekb=1" 
                title="Bloomberg Live" 
                frameBorder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowFullScreen
              ></iframe>
              <div className="absolute top-4 left-4 bg-red-500/90 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow-lg uppercase animate-pulse backdrop-blur-md">
                IA Active
              </div>
            </div>
          </div>
        </div>

        <div className="bg-[#050505] border border-white/5 rounded-2xl p-6 flex flex-col">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
            <Rss className="w-5 h-5 text-orange-400" /> Flux RSS & Marché
          </h3>
          <div className="flex-1 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar space-y-4">
            {loadingNews ? (
              <div className="h-full flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-slate-500 border-t-white rounded-full animate-spin"></div>
              </div>
            ) : newsData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm border border-white/5 bg-[#0a0a0a] rounded-xl">
                Aucune actualité disponible
              </div>
            ) : (
              newsData.map((item, i) => (
                <a key={i} href={item.link} target="_blank" rel="noreferrer" className={`block p-4 border rounded-xl transition-colors group ${item.isTruth ? 'border-pink-500/20 bg-pink-500/5 hover:border-pink-500/40' : 'border-white/5 bg-[#0a0a0a] hover:border-white/20'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {item.isTruth && item.avatar && <img src={item.avatar} alt="avatar" className="w-5 h-5 rounded-full" />}
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${item.isTruth ? 'text-pink-400' : 'text-slate-500'}`}>
                        {item.isTruth ? 'TRUTH SOCIAL' : new Date(item.published).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {item.isTruth && <span className="text-[10px] text-pink-500/60 font-medium">{new Date(item.published).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>}
                      {!item.isTruth && <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-white transition-colors" />}
                    </div>
                  </div>
                  <h4 className={`text-sm font-bold mb-2 leading-snug ${item.isTruth ? 'text-pink-100' : 'text-white'}`}>{item.title}</h4>
                  <p className={`text-xs line-clamp-3 ${item.isTruth ? 'text-pink-200/70' : 'text-slate-400'}`}>{item.summary}</p>
                </a>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}



// ==========================================
// ASSET ROW (Portfolio + AI Analysis)
// ==========================================
function AssetRow({ inv }: { inv: any }) {
  const [expanded, setExpanded] = useState(false)
  const [loadingAi, setLoadingAi] = useState(false)
  const [aiData, setAiData] = useState<any>(null)
  const [loadingNews, setLoadingNews] = useState(false)
  const [newsData, setNewsData] = useState<any>(null)

  const handleExpand = () => {
    if (!expanded && !aiData) {
      setLoadingAi(true)
      // inv.isin is used, backend resolves it
      fetch(`http://localhost:5000/api/assets/ai-analysis/${inv.isin}`)
        .then(res => res.json())
        .then(data => {
          setAiData(data?.analyses || null)
          setLoadingAi(false)
        })
        .catch(() => setLoadingAi(false))
        
      setLoadingNews(true)
      fetch(`http://localhost:5000/api/assets/news/${inv.ticker || inv.isin}?name=${encodeURIComponent(inv.name)}`)
        .then(res => res.json())
        .then(data => {
          setNewsData(data)
          setLoadingNews(false)
        })
        .catch(() => setLoadingNews(false))
    }
    setExpanded(!expanded)
  }

  return (
    <div className="bg-[#0a0a0a] border border-white/5 rounded-xl hover:border-white/10 transition-colors overflow-hidden">
      <div className="flex items-center justify-between p-4 cursor-pointer select-none" onClick={handleExpand}>
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center overflow-hidden">
            <img 
              src={`https://assets.traderepublic.com/img/logos/${inv.isin}/dark.svg`} 
              alt={inv.name} 
              className="w-full h-full object-cover" 
              onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextElementSibling?.classList.remove('hidden') }} 
            />
            <Building className="w-5 h-5 text-slate-400 hidden" />
          </div>
          <div>
            <div className="text-sm text-white font-bold">{inv.name}</div>
            <div className="text-xs text-slate-500 mt-0.5">{inv.quantity.toFixed(4)} parts • {inv.current_price.toFixed(2)} € /u</div>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-base font-bold text-white">{inv.total_value.toFixed(2)} €</div>
            <div className={`text-xs font-bold mt-0.5 ${inv.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {inv.pnl >= 0 ? '+' : ''}{inv.pnl.toFixed(2)} € ({inv.pnl_percent >= 0 ? '+' : ''}{inv.pnl_percent.toFixed(2)}%)
            </div>
          </div>
        </div>
      </div>
      
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-white/5"
          >
            <div className="p-5 bg-gradient-to-b from-indigo-500/[0.02] to-transparent">
              <h4 className="text-sm font-bold text-indigo-400 mb-4 flex items-center gap-2">
                <BrainCircuit className="w-4 h-4" /> Analyse Stratégique (Finary AI)
              </h4>
              {loadingAi ? (
                <div className="flex flex-col items-center justify-center py-6">
                  <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-3"></div>
                  <p className="text-xs text-slate-500">Génération de l'analyse en cours...</p>
                </div>
              ) : aiData ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="bg-[#050505] p-4 rounded-xl border border-white/5">
                    <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">{aiData.what_to_study?.text}</p>
                  </div>
                  <div className="bg-[#050505] p-4 rounded-xl border border-white/5">
                    <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">{aiData.data_analysis?.text}</p>
                  </div>
                  <div className="bg-[#050505] p-4 rounded-xl border border-white/5">
                    <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">{aiData.risks_and_exit?.text}</p>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">Impossible de générer l'analyse pour cet actif.</p>
              )}
              
              {/* LIVE NEWS TRACKING */}
              <div className="mt-6 border-t border-white/5 pt-5">
                <h4 className="text-sm font-bold text-sky-400 mb-4 flex items-center gap-2">
                  <Globe className="w-4 h-4" /> Live News Tracking
                </h4>
                {loadingNews ? (
                  <div className="flex flex-col items-center justify-center py-6">
                    <div className="w-6 h-6 border-2 border-sky-500/30 border-t-sky-500 rounded-full animate-spin mb-3"></div>
                    <p className="text-xs text-slate-500">Scraping des news mondiales...</p>
                  </div>
                ) : newsData ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="bg-[#050505] p-4 rounded-xl border border-sky-500/20">
                      <div className="text-[11px] font-bold text-sky-400 uppercase tracking-wider mb-2">Analyse IA des News</div>
                      <p className="text-xs text-slate-300 leading-relaxed">{newsData.analysis}</p>
                    </div>
                    <div className="bg-[#050505] p-4 rounded-xl border border-white/5 overflow-hidden">
                      <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Derniers Titres</div>
                      <ul className="space-y-2">
                        {newsData.articles?.map((article: any, idx: number) => (
                          <li key={idx} className="text-xs text-slate-300 truncate">
                            • <a href={article.link} target="_blank" rel="noreferrer" className="hover:text-sky-400 transition-colors">{article.title}</a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">Impossible de charger les news.</p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ==========================================
// MARKET INTEL TAB (Smart Money, Insiders, Senators)
// ==========================================

const BANK_LOGOS: Record<string, string> = {
  'JPMorgan': '/logos/JPMorgan.png',
  'Goldman Sachs': '/logos/Goldman Sachs.png',
  'Morgan Stanley': '/logos/Morgan Stanley.png',
  'Bank of America': '/logos/Bank of America.png',
  'Citigroup': '/logos/Citigroup.png',
  'UBS': '/logos/UBS.png',
  'Barclays': '/logos/Barclays.png',
  'Société Générale': '/logos/Société Générale.png',
  'BNP Paribas': '/logos/BNP Paribas.png',
  'Deloitte': '/logos/Deloitte.png',
  'McKinsey': '/logos/McKinsey.png',
  'BlackRock': '/logos/BlackRock.png',
}

function MarketTab() {
  const [loading, setLoading] = useState(false)
  const [banks, setBanks] = useState<any>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [synthesis, setSynthesis] = useState<any>(null)
  const [synthesizing, setSynthesizing] = useState(false)

  useEffect(() => {
    if (!banks) {
      setLoading(true)
      
      const cachedSynthesis = localStorage.getItem('banks_synthesis')
      if (cachedSynthesis) {
        try { setSynthesis(JSON.parse(cachedSynthesis)) } catch (e) {}
      }

      fetch('http://localhost:5000/api/bank-forecasts')
      .then(res => res.json())
      .then(data => {
        if (data.results) setBanks(data.results)
        if (data.last_scraped_at) setLastUpdated(data.last_scraped_at)
        setLoading(false)
      })
      .catch(err => { console.error(err); setLoading(false) })
    }
  }, [banks])

  useEffect(() => {
    if (banks && !synthesis && !synthesizing) {
      setSynthesizing(true)
      const prompt = `Voici des prévisions bancaires: ${JSON.stringify(banks.map((b:any)=>({bank: b.bank, ai: b.ai_analysis})))}\n\nFais une synthèse sous format STRICTEMENT JSON avec cette structure exacte (SANS AUCUN TEXTE AUTOUR):\n{\n"overview": "Résumé global et direct de la tendance du consensus (2 phrases max)",\n"timeline": [\n{ "period": "Ce Trimestre", "title": "Court terme", "description": "...", "sentiment": "Bullish|Bearish|Neutral" },\n{ "period": "Fin d'année", "title": "Moyen terme", "description": "...", "sentiment": "Bullish|Bearish|Neutral" },\n{ "period": "2027 et au-delà", "title": "Long terme", "description": "...", "sentiment": "Bullish|Bearish|Neutral" }\n],\n"sectors": [\n{ "name": "Secteur", "action": "Surpondérer|Sous-pondérer", "reason": "Pourquoi" }\n]\n}`
      
      fetch('http://localhost:5000/api/ai/chat', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ message: prompt })
      })
      .then(res => res.json())
      .then(data => {
         try {
             let text = data.response.replace(/```json/gi, '').replace(/```/g, '').trim()
             const parsed = JSON.parse(text)
             setSynthesis(parsed)
             localStorage.setItem('banks_synthesis', JSON.stringify(parsed))
         } catch (e) {
             console.error("Failed to parse synthesis", e)
         }
         setSynthesizing(false)
      })
      .catch(() => setSynthesizing(false))
    }
  }, [banks, synthesis, synthesizing])

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between mb-8 gap-4">
        <div>
          <h2 className="text-3xl font-black text-white tracking-tight">Prévisions Bancaires</h2>
          <p className="text-slate-400 mt-2">La vision macroéconomique des plus grandes institutions mondiales.</p>
        </div>
        {lastUpdated && (
          <div className="flex items-center gap-2 bg-[#050505] border border-white/5 px-3 py-1.5 rounded-full text-xs text-slate-500">
            <RefreshCw className="w-3 h-3" />
            Actualisé le {new Date(lastUpdated).toLocaleDateString('fr-FR')} à {new Date(lastUpdated).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>

      {/* CONTENT AREA */}
      <div className="flex flex-col gap-6">
        {loading && <div className="text-center text-slate-400 py-10 animate-pulse bg-white/5 rounded-3xl border border-white/5">Chargement des données macroéconomiques...</div>}

        {!loading && banks && (
          <>
            {synthesizing ? (
              <div className="bg-white/[0.02] border border-emerald-500/20 rounded-3xl p-8 flex flex-col items-center justify-center min-h-[300px]">
                <BrainCircuit className="w-10 h-10 text-emerald-500 animate-pulse mb-4" />
                <p className="text-emerald-400 font-bold">WealthAI synthétise les consensus bancaires...</p>
                <p className="text-slate-400 text-sm mt-2">Génération de votre projection financière</p>
              </div>
            ) : synthesis ? (
              <div className="space-y-6">
                {/* OVERVIEW */}
                <div className="bg-gradient-to-br from-emerald-500/10 to-transparent border border-emerald-500/20 rounded-3xl p-8 md:p-10 relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -mr-20 -mt-20"></div>
                  <h3 className="text-emerald-400 font-black text-2xl mb-4 flex items-center gap-2">
                    <Sparkles className="w-6 h-6" /> Consensus Global Stratégique
                  </h3>
                  <p className="text-white text-lg md:text-xl leading-relaxed relative z-10 mb-8">{synthesis.overview}</p>
                  
                  {/* INSTITUTIONS CONSULTÉES */}
                  <div className="relative z-10 pt-6 border-t border-emerald-500/20">
                    <h4 className="text-xs font-bold text-emerald-400/50 uppercase tracking-wider mb-4">Bases de connaissances ingérées</h4>
                    <div className="flex flex-wrap gap-3 items-center">
                      {banks.map((b: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 bg-black/40 backdrop-blur-md border border-white/10 rounded-full px-3 py-1.5 cursor-default" title={b.summary}>
                          {BANK_LOGOS[b.bank] ? (
                            <img src={BANK_LOGOS[b.bank]} alt={b.bank} className="w-5 h-5 object-cover rounded-full bg-white/10" />
                          ) : (
                            <Building className="w-4 h-4 text-emerald-400" />
                          )}
                          <span className="text-xs font-bold text-slate-300">{b.bank}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* TIMELINE & SECTORS COMBINED */}
                <div className="bg-[#050505] border border-white/5 rounded-3xl p-6 md:p-10">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
                    {/* TIMELINE */}
                    <div>
                      <h3 className="text-white font-bold text-xl mb-6 flex items-center gap-2">
                        <Compass className="w-5 h-5 text-slate-400" /> Projection Macro
                      </h3>
                      <div className="space-y-6">
                        {synthesis.timeline?.map((item: any, i: number) => (
                          <div key={i} className="flex gap-4 relative">
                            <div className="flex flex-col items-center mt-1">
                              <div className={`w-3 h-3 rounded-full ${item.sentiment === 'Bullish' ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : item.sentiment === 'Bearish' ? 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]' : 'bg-slate-500'}`}></div>
                              {i !== synthesis.timeline.length - 1 && <div className="w-px h-full bg-white/10 mt-2"></div>}
                            </div>
                            <div className={i !== synthesis.timeline.length - 1 ? "pb-6" : ""}>
                              <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{item.period}</span>
                              <h4 className="text-white font-bold text-lg mt-1">{item.title}</h4>
                              <p className="text-slate-400 text-sm mt-1 leading-relaxed">{item.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* SECTORS */}
                    <div>
                      <h3 className="text-white font-bold text-xl mb-6 flex items-center gap-2">
                        <LineChart className="w-5 h-5 text-slate-400" /> Rotations Sectorielles
                      </h3>
                      <div className="space-y-4">
                        {synthesis.sectors?.map((sec: any, i: number) => (
                          <div key={i} className="flex items-start gap-4 border-b border-white/5 pb-4 last:border-0 last:pb-0">
                            <div className={`mt-1 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${sec.action === 'Surpondérer' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                              {sec.action === 'Surpondérer' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                            </div>
                            <div>
                              <h4 className="text-white font-bold">{sec.name}</h4>
                              <p className="text-slate-400 text-sm mt-1">{sec.reason}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}


// ==========================================
// AI ASSETS TAB (WealthAI Portfolio Analysis)
// ==========================================

function TaxOptimizationTab({ userProfile, onRequestEdit }: { userProfile: any, onRequestEdit?: () => void }) {
  const [maritalStatus, setMaritalStatus] = useState('Célibataire')
  const [children, setChildren] = useState(0)
  const [income, setIncome] = useState(50000)
  const [otherIncome, setOtherIncome] = useState(0)
  const [profession, setProfession] = useState('Salarié')
  const [contractType, setContractType] = useState('CDI')
  const [contractDuration, setContractDuration] = useState('Indéterminé')
  const [parentsProfession, setParentsProfession] = useState('Non applicable')
  const [financialAids, setFinancialAids] = useState('Aucune')
  const [goal, setGoal] = useState('Préparer ma retraite')
  
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<string | null>(null)

  const handleAnalyze = async () => {
    setIsAnalyzing(true)
    try {
      // Pour une analyse ultra-complète, on envoie aussi un résumé du portefeuille existant
      // Dans la réalité, on pourrait récupérer ça du store global ou d'autres endpoints,
      // ici on l'envoie au backend
      const res = await fetch('http://localhost:5000/api/tax/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          marital_status: maritalStatus,
          children,
          income,
          other_income: otherIncome,
          profession,
          contractType,
          contractDuration,
          parentsProfession,
          financialAids,
          goal
        })
      })
      const data = await res.json()
      if (data.success) {
        setAnalysisResult(data.analysis)
      } else {
        setAnalysisResult("Erreur lors de l'analyse: " + data.error)
      }
    } catch (e: any) {
      setAnalysisResult("Erreur de connexion au serveur.")
    }
    setIsAnalyzing(false)
  }

  return (
    <div className="space-y-8 pb-20">
      <div className="flex flex-col gap-1">
        <h2 className="text-slate-500 text-sm font-bold uppercase tracking-widest">Optimisation Haut-de-Gamme</h2>
        <h1 className="text-4xl font-light text-white tracking-tight">Intelligence Fiscale & Ingénierie Patrimoniale</h1>
        <p className="text-slate-400 mt-2">Votre situation et votre portefeuille sont analysés par notre IA experte en droit fiscal.</p>
      </div>

      {!analysisResult ? (
        <div className="bg-[#050505] border border-white/5 rounded-2xl p-8 max-w-4xl">
          <h3 className="text-2xl font-light text-white mb-6">Précisez votre situation</h3>
          
          {userProfile?.taxOnboarded ? (
            <div className="mb-6 p-6 bg-white/5 border border-emerald-500/30 rounded-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-emerald-500/10 blur-[50px] rounded-full pointer-events-none" />
              <p className="text-emerald-400 font-bold mb-4 flex items-center gap-2"><Sparkles className="w-5 h-5"/> Profil fiscal sécurisé depuis votre intégration</p>
              <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm relative z-10">
                <div><span className="text-slate-500 block mb-1">Statut Pro</span> <span className="text-white font-medium block">{userProfile?.profession}</span></div>
                <div><span className="text-slate-500 block mb-1">Contrat</span> <span className="text-white font-medium block">{userProfile?.contractType} {userProfile?.contractDuration && `(${userProfile.contractDuration})`}</span></div>
                <div><span className="text-slate-500 block mb-1">État civil</span> <span className="text-white font-medium block">{userProfile?.maritalStatus}</span></div>
                <div><span className="text-slate-500 block mb-1">Enfants à charge</span> <span className="text-white font-medium block">{userProfile?.children}</span></div>
                <div><span className="text-slate-500 block mb-1">Revenus Nets</span> <span className="text-white font-medium block">{userProfile?.income} €</span></div>
                <div><span className="text-slate-500 block mb-1">Autres Revenus</span> <span className="text-white font-medium block">{userProfile?.otherIncome} €</span></div>
                <div><span className="text-slate-500 block mb-1">Prof. des Parents</span> <span className="text-white font-medium block">{userProfile?.parentsProfession || 'Non renseigné'}</span></div>
                <div><span className="text-slate-500 block mb-1">Aides / Bourses</span> <span className="text-white font-medium block">{userProfile?.financialAids || 'Aucune'}</span></div>
                <div className="col-span-2 mt-2 pt-4 border-t border-white/5"><span className="text-emerald-500 font-bold block mb-1">Objectif Principal</span> <span className="text-white font-medium block text-base">{userProfile?.taxGoal}</span></div>
              </div>
              <button 
                onClick={() => onRequestEdit?.()} 
                className="mt-4 w-full bg-white/5 hover:bg-white/10 text-emerald-400 font-bold py-2 rounded-xl transition-colors text-sm"
              >
                Modifier mes informations
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-bold text-slate-400">Statut Professionnel</label>
                  <select className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors" value={profession} onChange={(e) => setProfession(e.target.value)}>
                    <option className="bg-black">Salarié</option>
                    <option className="bg-black">Indépendant / Freelance</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          <button 
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="w-full mt-6 py-4 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-400 text-black font-bold text-lg hover:from-emerald-500 hover:to-emerald-300 transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isAnalyzing ? (
              <><BrainCircuit className="w-5 h-5 animate-pulse" /> Analyse experte en cours...</>
            ) : (
              <><Sparkles className="w-5 h-5" /> Générer ma stratégie d'ingénierie patrimoniale</>
            )}
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <button 
            onClick={() => setAnalysisResult(null)}
            className="flex items-center gap-2 text-sm font-bold text-slate-400 hover:text-white transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" /> Ajuster ma situation
          </button>
          
          <div className="bg-[#050505] border border-emerald-500/30 rounded-2xl p-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/10 blur-[120px] rounded-full pointer-events-none" />
            
            <div className="prose prose-invert prose-emerald max-w-none text-slate-300">
              {/* Force markdown to render nicely and safely */}
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({node, ...props}) => <div className="overflow-x-auto"><table className="w-full text-left border-collapse" {...props} /></div>,
                  th: ({node, ...props}) => <th className="border-b border-white/10 py-3 font-bold text-white" {...props} />,
                  td: ({node, ...props}) => <td className="border-b border-white/5 py-3" {...props} />,
                  h1: ({node, ...props}) => <h1 className="text-3xl font-light text-white mt-8 mb-4" {...props} />,
                  h2: ({node, ...props}) => <h2 className="text-2xl font-light text-emerald-400 mt-8 mb-4" {...props} />,
                  h3: ({node, ...props}) => <h3 className="text-xl font-bold text-white mt-6 mb-3" {...props} />,
                  ul: ({node, ...props}) => <ul className="list-disc pl-5 space-y-2 my-4" {...props} />,
                  li: ({node, ...props}) => <li className="pl-1" {...props} />,
                  strong: ({node, ...props}) => <strong className="font-bold text-white" {...props} />
                }}
              >
                {analysisResult}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==========================================
// ALTERNATIVE ASSETS TAB (PREMIUM DESIGN)
// ==========================================
function AlternativeAssetsTab() {
  const [alts, setAlts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<any>(null)
  
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [newName, setNewName] = useState('')

  const [newType, setNewType] = useState('Horlogerie')
  const [manualPrice, setManualPrice] = useState('')
  const [customImage, setCustomImage] = useState('')

  const fetchAlts = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/alts', { cache: 'no-store' })
      const data = await res.json()
      setAlts(data)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchAlts()
  }, [])

  const handleAdd = async () => {
    if (!newName) return
    setIsEvaluating(true)
    try {
      const payload: any = { name: newName, type: newType }
      if (manualPrice) {
        payload.manual_price = parseFloat(manualPrice)
      }
      if (customImage) {
        payload.image_url = customImage
      }
      await fetch('http://localhost:5000/api/alts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      await fetchAlts()
      setShowAddModal(false)
      setNewName('')
      setManualPrice('')
      setCustomImage('')
    } catch (e) {
      console.error(e)
    }
    setIsEvaluating(false)
  }

  const handleDelete = async (id: number) => {
    try {
      await fetch(`http://localhost:5000/api/alts/${id}`, { method: 'DELETE' })
      setSelectedAsset(null)
      await fetchAlts()
    } catch (e) {
      console.error(e)
    }
  }

  const getTypeIcon = (type: string) => {
    switch(type) {
      case 'Immobilier': return <Building className="w-6 h-6" />
      case 'Horlogerie': return <Target className="w-6 h-6" />
      case 'Private Equity': return <Compass className="w-6 h-6" />
      case 'Crypto': return <DollarSign className="w-6 h-6" />
      case 'Objet': return <Tv className="w-6 h-6" />
      default: return <Sparkles className="w-6 h-6" />
    }
  }

  const getTypeTheme = (type: string) => {
    switch(type) {
      case 'Immobilier': return 'from-blue-500/20 to-indigo-500/0 text-blue-400 border-blue-500/20'
      case 'Horlogerie': return 'from-amber-500/20 to-orange-500/0 text-amber-400 border-amber-500/20'
      case 'Private Equity': return 'from-purple-500/20 to-fuchsia-500/0 text-purple-400 border-purple-500/20'
      case 'Crypto': return 'from-emerald-500/20 to-teal-500/0 text-emerald-400 border-emerald-500/20'
      case 'Objet': return 'from-cyan-500/20 to-blue-500/0 text-cyan-400 border-cyan-500/20'
      default: return 'from-slate-500/20 to-slate-500/0 text-slate-400 border-slate-500/20'
    }
  }

  return (
    <div className="space-y-12 pb-20 relative">
      <div className="flex flex-col gap-2">
        <h2 className="text-slate-400 text-xs font-bold uppercase tracking-[0.2em]">Diversification de portefeuille</h2>
        <h1 className="text-5xl font-light text-white tracking-tight">Actifs <span className="font-bold">Alternatifs</span></h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {loading ? (
          <div className="text-slate-400 animate-pulse col-span-full">Chargement du coffre-fort...</div>
        ) : alts.map((alt, i) => {
          const theme = getTypeTheme(alt.type)
          return (
            <motion.div 
              key={alt.id}
              whileHover={{ y: -5, scale: 1.02 }}
              onClick={() => setSelectedAsset(alt)}
              className={`bg-[#0A0A0A] border ${theme.split(' ')[2]} rounded-[2rem] p-8 cursor-pointer transition-all relative overflow-hidden flex flex-col justify-between min-h-[380px] group shadow-2xl shadow-black/50`}
            >
              <div className={`absolute inset-0 bg-gradient-to-b ${theme.split(' ')[0]} ${theme.split(' ')[1]} opacity-50`} />
              
              {alt.image_url && (
                <div className="absolute inset-0 w-full h-full opacity-30 group-hover:opacity-50 group-hover:scale-105 transition-all duration-700">
                  <img src={alt.image_url} alt={alt.name} className="w-full h-full object-cover grayscale mix-blend-screen" />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/90 to-transparent" />
                </div>
              )}
              
              <div className="relative z-10 flex justify-between items-start">
                <div className={`w-14 h-14 rounded-2xl bg-black/50 backdrop-blur-xl border border-white/10 flex items-center justify-center mb-6 shadow-xl ${theme.split(' ')[1]}`}>
                  {getTypeIcon(alt.type)}
                </div>
              </div>
              
              <div className="relative z-10">
                <div className="text-xs uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">{alt.type}</div>
                <div className="text-2xl font-light text-white mb-2 leading-tight">{alt.name}</div>
                {alt.description && <p className="text-sm text-slate-400 line-clamp-2 mb-6 font-light">{alt.description}</p>}
                
                <div className="mt-4 pt-6 border-t border-white/5 flex items-end justify-between backdrop-blur-sm">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Évaluation (EUR)</div>
                    <div className="text-3xl font-bold text-white tracking-tighter">
                      {(alt.estimated_min || 0).toLocaleString()} <span className="text-lg font-light text-slate-500">€</span>
                    </div>
                  </div>
                  <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center group-hover:bg-white/10 transition-colors">
                    <ArrowRight className="w-4 h-4 text-white" />
                  </div>
                </div>
              </div>
            </motion.div>
          )
        })}
        
        <motion.div 
          whileHover={{ scale: 1.02 }}
          onClick={() => setShowAddModal(true)} 
          className="bg-transparent border border-dashed border-white/10 hover:border-emerald-500/50 rounded-[2rem] p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-emerald-500/5 transition-all group min-h-[380px]"
        >
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6 group-hover:bg-emerald-500/20 group-hover:scale-110 transition-all duration-500">
            <Plus className="w-8 h-8 text-white group-hover:text-emerald-400" />
          </div>
          <div className="text-xl font-light text-white tracking-tight">Ajouter un Actif</div>
          <div className="text-sm text-slate-500 mt-2 text-center font-light">Montres, Art, Private Equity...<br/>Évaluation par IA.</div>
        </motion.div>
      </div>

      {/* MODAL AJOUT */}
      <AnimatePresence>
        {showAddModal && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-xl p-4"
          >
            <motion.div 
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
              className="bg-[#0A0A0A] border border-white/10 rounded-[2rem] p-8 w-full max-w-lg shadow-2xl relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -mr-32 -mt-32" />
              
              <h3 className="text-3xl font-light text-white tracking-tight mb-8">Nouveau <span className="font-bold">Bijou</span></h3>
              
              <div className="space-y-6 relative z-10">
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-bold">Catégorie</label>
                  <select value={newType} onChange={e => setNewType(e.target.value)} className="w-full mt-2 bg-black/50 border border-white/10 rounded-2xl px-5 py-4 text-white outline-none focus:border-emerald-500/50 focus:bg-emerald-500/5 transition-all appearance-none font-light">
                    <option value="Horlogerie">Horlogerie (Montres)</option>
                    <option value="Immobilier">Immobilier</option>
                    <option value="Art">Oeuvre d'art</option>
                    <option value="Private Equity">Private Equity / Startup</option>
                    <option value="Voiture">Voiture de collection</option>
                    <option value="Crypto">Crypto (Cold Wallet)</option>
                    <option value="Objet">Objet / High-Tech (PC, etc.)</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-bold">Modèle / Nom exact</label>
                  <input 
                    type="text" 
                    value={newName} 
                    onChange={e => setNewName(e.target.value)} 
                    placeholder="ex: Tissot PRX Powermatic 80"
                    className="w-full mt-2 bg-black/50 border border-white/10 rounded-2xl px-5 py-4 text-white outline-none focus:border-emerald-500/50 focus:bg-emerald-500/5 transition-all font-light"
                  />
                </div>
                
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-bold flex justify-between">
                    <span>Prix estimé (Optionnel)</span>
                    <span className="text-emerald-500/50">Laissez vide pour l'IA</span>
                  </label>
                  <div className="relative mt-2">
                    <input 
                      type="number" 
                      value={manualPrice} 
                      onChange={e => setManualPrice(e.target.value)} 
                      placeholder="ex: 750"
                      className="w-full bg-black/50 border border-white/10 rounded-2xl px-5 py-4 text-white outline-none focus:border-emerald-500/50 focus:bg-emerald-500/5 transition-all font-light"
                    />
                    <div className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-500">€</div>
                  </div>
                </div>
                
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-bold flex justify-between mt-6">
                    <span>Lien de l'image (Optionnel)</span>
                    <span className="text-emerald-500/50">Pour la perfection</span>
                  </label>
                  <input 
                    type="url" 
                    value={customImage} 
                    onChange={e => setCustomImage(e.target.value)} 
                    placeholder="https://..."
                    className="w-full mt-2 bg-black/50 border border-white/10 rounded-2xl px-5 py-4 text-white outline-none focus:border-emerald-500/50 focus:bg-emerald-500/5 transition-all font-light"
                  />
                  {newName && (
                    <a
                      href={`https://www.google.com/search?tbm=isch&q=${encodeURIComponent(newName + (newType === 'Horlogerie' ? ' montre' : ''))}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-emerald-400/70 hover:text-emerald-400 mt-2 flex items-center gap-1 font-medium transition-colors"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                      Chercher l'image sur Google
                    </a>
                  )}
                </div>

              </div>

              <div className="mt-10 flex gap-4 relative z-10">
                <button onClick={() => setShowAddModal(false)} className="px-6 py-4 rounded-2xl border border-white/10 text-white font-bold hover:bg-white/5 transition-colors disabled:opacity-50">
                  Annuler
                </button>
                <button onClick={handleAdd} className="flex-1 py-4 rounded-2xl bg-white text-black font-bold hover:bg-emerald-400 hover:text-black hover:shadow-lg hover:shadow-emerald-500/25 transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:hover:bg-white" disabled={isEvaluating || !newName}>
                  {isEvaluating ? (
                    <><BrainCircuit className="w-5 h-5 animate-pulse" /> Traitement IA...</>
                  ) : (
                    <><Sparkles className="w-5 h-5" /> Ajouter au coffre</>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* MODAL DETAIL ASSET */}
      <AnimatePresence>
        {selectedAsset && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-2xl p-4 md:p-12"
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
              className="relative w-full max-w-6xl h-full max-h-[800px] bg-[#050505] border border-white/10 rounded-[3rem] overflow-hidden flex flex-col md:flex-row shadow-2xl"
            >
              <button onClick={() => setSelectedAsset(null)} className="absolute top-6 right-6 w-12 h-12 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center transition-colors z-50 shadow-lg">
                <X className="w-5 h-5 text-white" />
              </button>

              {/* IMAGE SIDE */}
              <div className="w-full md:w-1/2 h-64 md:h-full bg-black relative">
                {selectedAsset.image_url ? (
                  <img src={selectedAsset.image_url} alt={selectedAsset.name} className="w-full h-full object-cover" />
                ) : (
                  <div className={`w-full h-full flex items-center justify-center bg-gradient-to-br ${getTypeTheme(selectedAsset.type).split(' ')[0]} ${getTypeTheme(selectedAsset.type).split(' ')[1]}`}>
                    {getTypeIcon(selectedAsset.type)}
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t md:bg-gradient-to-r from-[#050505] to-transparent" />
              </div>
              
              {/* DETAILS SIDE */}
              <div className="w-full md:w-1/2 p-8 md:p-16 flex flex-col overflow-y-auto">
                <div className="text-xs uppercase tracking-[0.3em] font-bold text-slate-500 mb-4">{selectedAsset.type}</div>
                <h2 className="text-4xl md:text-5xl font-light text-white tracking-tight leading-tight mb-8">{selectedAsset.name}</h2>
                
                <div className="bg-white/5 border border-white/10 rounded-3xl p-8 mb-8 backdrop-blur-xl">
                  <div className="text-xs uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">Valorisation</div>
                  <div className="text-5xl font-light text-white tracking-tighter mb-2">
                    {(selectedAsset.estimated_min || 0).toLocaleString()} <span className="text-2xl font-light text-slate-500">€</span>
                  </div>
                  {selectedAsset.estimated_max > selectedAsset.estimated_min && (
                    <div className="text-sm text-emerald-400 font-bold">
                      Jusqu'à {(selectedAsset.estimated_max || 0).toLocaleString()} €
                    </div>
                  )}
                </div>
                
                <div className="prose prose-invert prose-p:text-slate-400 prose-p:font-light prose-p:leading-relaxed mb-auto">
                  <p>{selectedAsset.description}</p>
                </div>
                
                <div className="mt-12 pt-8 border-t border-white/10 flex justify-between items-center">
                  <button onClick={() => handleDelete(selectedAsset.id)} className="flex items-center gap-2 text-red-500/70 hover:text-red-400 transition-colors font-bold text-sm uppercase tracking-widest">
                    <X className="w-4 h-4" /> Supprimer l'actif
                  </button>
                  <div className="flex items-center gap-2 text-slate-600 text-xs uppercase tracking-widest">
                    <BrainCircuit className="w-4 h-4" /> Évalué par IA
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    

</div>
  )
}

// ==========================================
// SETTINGS TAB (Paramètres & Profil)
// ==========================================
function SettingsTab({ userProfile, onRequestEdit }: { userProfile: any, onRequestEdit?: () => void }) {
  return (
    <div className="w-full space-y-10">
      {/* Header Modal */}
      <div className="mb-4 pr-10">
        <h2 className="text-3xl font-bold text-white tracking-tight mb-2">Profil & Paramètres</h2>
        <p className="text-slate-400 text-sm">Gérez vos informations, votre fiscalité et votre abonnement.</p>
      </div>

      {/* Identité & Fiscalité Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-800 border border-white/10 flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
            <h3 className="text-xl font-bold text-white tracking-tight">Mon Profil Fiscal</h3>
          </div>
          <button onClick={onRequestEdit} className="text-xs bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg font-bold transition-colors">
            Modifier
          </button>
        </div>

        <div className="bg-[#050505] border border-white/5 rounded-3xl p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 block">Nom complet</label>
              <div className="bg-[#0a0a0a] border border-white/5 rounded-xl px-4 py-2.5 text-white text-sm">
                {userProfile?.name || 'Non renseigné'}
              </div>
            </div>
            <div>
              <label className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 block">Adresse Email</label>
              <div className="bg-[#0a0a0a] border border-white/5 rounded-xl px-4 py-2.5 text-slate-400 text-sm">
                {userProfile?.email || 'Non renseigné'}
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-white/5">
             <div className="flex items-center gap-4 mb-6">
                <div className={`w-12 h-12 shrink-0 rounded-full flex items-center justify-center ${FUND_PROFILES[userProfile?.riskProfile || 'DIVERSIFIED']?.bgClass} border ${FUND_PROFILES[userProfile?.riskProfile || 'DIVERSIFIED']?.borderClass}`}>
                  <ShieldCheck className={`w-5 h-5 ${FUND_PROFILES[userProfile?.riskProfile || 'DIVERSIFIED']?.textClass}`} />
                </div>
                <div>
                  <div className="text-lg font-bold text-white">{FUND_PROFILES[userProfile?.riskProfile || 'DIVERSIFIED']?.title || 'Non défini'}</div>
                  <div className="text-sm text-slate-500">Profil d'investissement actif</div>
                </div>
              </div>

              {userProfile?.taxOnboarded && (
                <div className="bg-[#0a0a0a] border border-white/5 rounded-xl p-4 space-y-2">
                  <div className="flex justify-between"><span className="text-slate-500 text-sm">Statut</span><span className="text-white text-sm text-right">{userProfile.profession}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500 text-sm">Contrat</span><span className="text-white text-sm text-right">{userProfile.contractType} {userProfile.contractDuration && `(${userProfile.contractDuration})`}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500 text-sm">État civil</span><span className="text-white text-sm text-right">{userProfile.maritalStatus}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500 text-sm">Enfants à charge</span><span className="text-white text-sm text-right">{userProfile.children}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500 text-sm">Revenus Nets</span><span className="text-white text-sm text-right">{userProfile.income} €</span></div>
                  <div className="flex flex-col mt-2 pt-2 border-t border-white/5 gap-1"><span className="text-slate-500 text-sm">Objectif</span><span className="text-emerald-400 font-medium text-sm leading-tight">{userProfile.taxGoal}</span></div>
                </div>
              )}
          </div>
        </div>
      </section>

      {/* Abonnement Section */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-slate-800 border border-white/10 flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-xl font-bold text-white tracking-tight">Abonnement</h3>
        </div>

        <div className="bg-gradient-to-br from-[#0a0a0a] to-[#050505] border border-white/5 rounded-3xl p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-fuchsia-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <div className="text-xl font-light text-white tracking-tight">Membre <span className="font-bold">Premium</span></div>
                <div className="bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border border-emerald-500/20">Actif</div>
              </div>
              <p className="text-slate-400 text-xs">Prochaine facturation de 49€ le {new Date(new Date().setMonth(new Date().getMonth() + 1)).toLocaleDateString('fr-FR')}.</p>
            </div>
            
            <button className="bg-white text-black hover:bg-slate-200 transition-colors px-4 py-2 rounded-xl font-bold text-sm shadow-[0_0_20px_rgba(255,255,255,0.1)] whitespace-nowrap">
              Gérer l'abonnement
            </button>
          </div>
        </div>
      </section>
      
      {/* Préférences */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-slate-800 border border-white/10 flex items-center justify-center">
            <Settings className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-xl font-bold text-white tracking-tight">Préférences</h3>
        </div>

        <div className="bg-[#050505] border border-white/5 rounded-3xl p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="text-white font-bold text-sm mb-1">Mode Discret</div>
              <div className="text-slate-500 text-xs">Masque le montant exact de votre patrimoine.</div>
            </div>
            <button 
              onClick={() => {
                const current = localStorage.getItem('hideAmounts') === 'true';
                localStorage.setItem('hideAmounts', (!current).toString());
                window.location.reload();
              }}
              className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-xl font-bold text-sm transition-colors border border-white/10"
            >
              Basculer l'affichage
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
