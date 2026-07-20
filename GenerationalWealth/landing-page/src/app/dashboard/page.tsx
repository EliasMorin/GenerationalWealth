"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity, TrendingUp, DollarSign, AlertTriangle } from "lucide-react";

export default function DashboardOverview() {
  const [marketData, setMarketData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Attempt to fetch from real Python backend
    async function loadData() {
      try {
        const data = await api.market.getAll();
        setMarketData(data);
      } catch (e) {
        console.warn("Backend not running, falling back to empty state");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Market Overview</h1>
        <p className="text-neutral-400">Real-time pulse of the global markets and your portfolio.</p>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard title="Portfolio Value" value="---" icon={<DollarSign className="w-5 h-5 text-green-500" />} />
        <KPICard title="S&P 500" value={marketData?.SPY?.price || "---"} icon={<TrendingUp className="w-5 h-5 text-blue-500" />} trend="+1.2%" />
        <KPICard title="Active Signals" value="12" icon={<Activity className="w-5 h-5 text-purple-500" />} />
        <KPICard title="Risk Alerts" value="2" icon={<AlertTriangle className="w-5 h-5 text-amber-500" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        {/* Main Chart Area */}
        <div className="lg:col-span-2 bg-neutral-900/50 border border-neutral-800 rounded-xl p-6 h-[400px] flex items-center justify-center">
          {loading ? (
            <div className="animate-pulse flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-neutral-500">Connecting to GenerationalWealth Engine...</p>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-neutral-500">Chart data will be injected here</p>
              {marketData && <p className="text-xs text-green-500 mt-2">Live connection active</p>}
            </div>
          )}
        </div>

        {/* Live Feed Sidebar */}
        <div className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-6">
          <h3 className="font-medium text-lg mb-4">Live Intelligence</h3>
          <div className="space-y-4">
            <div className="p-3 bg-black border border-neutral-800 rounded-lg">
              <span className="text-xs font-bold text-red-500 uppercase tracking-wider mb-1 block">Insider Trade</span>
              <p className="text-sm">Nancy Pelosi acquired 50 CALL options on NVDA</p>
            </div>
            <div className="p-3 bg-black border border-neutral-800 rounded-lg">
              <span className="text-xs font-bold text-blue-500 uppercase tracking-wider mb-1 block">Macro</span>
              <p className="text-sm">Fed indicates potential 25bps cut in September</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function KPICard({ title, value, icon, trend }: { title: string; value: string; icon: React.ReactNode; trend?: string }) {
  return (
    <div className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-6 hover:bg-neutral-900 transition-colors cursor-default">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-neutral-400 font-medium">{title}</h3>
        <div className="p-2 bg-black rounded-lg">{icon}</div>
      </div>
      <div className="flex items-end gap-3">
        <span className="text-3xl font-bold">{value}</span>
        {trend && <span className="text-sm font-medium text-green-500 mb-1">{trend}</span>}
      </div>
    </div>
  );
}
