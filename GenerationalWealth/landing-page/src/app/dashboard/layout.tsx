"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, PieChart, Activity, Cpu, Briefcase, Settings, LogOut } from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { name: "Overview", href: "/dashboard", icon: <LayoutDashboard className="w-5 h-5" /> },
    { name: "Portfolio", href: "/dashboard/portfolio", icon: <PieChart className="w-5 h-5" /> },
    { name: "Market Data", href: "/dashboard/markets", icon: <Activity className="w-5 h-5" /> },
    { name: "AI Intelligence", href: "/dashboard/ai", icon: <Cpu className="w-5 h-5" /> },
    { name: "Institutional", href: "/dashboard/institutional", icon: <Briefcase className="w-5 h-5" /> },
  ];

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-neutral-800 bg-black flex flex-col">
        <div className="p-6 border-b border-neutral-800">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-white rounded flex items-center justify-center text-black font-bold text-xl">
              G
            </div>
            <span className="font-bold text-lg tracking-tight">Terminal Pro</span>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive 
                    ? "bg-blue-600/10 text-blue-500 font-medium" 
                    : "text-neutral-400 hover:text-white hover:bg-neutral-900"
                }`}
              >
                {item.icon}
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-neutral-800 space-y-1">
          <Link href="/dashboard/settings" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-900 transition-colors">
            <Settings className="w-5 h-5" />
            Settings
          </Link>
          <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-red-500 hover:bg-red-500/10 transition-colors">
            <LogOut className="w-5 h-5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto relative">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/10 via-black to-black pointer-events-none" />
        <div className="relative z-10 p-8 h-full">
          {children}
        </div>
      </main>
    </div>
  );
}
