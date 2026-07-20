"use client";

import React, { useState, useEffect, useRef } from "react";

interface TerminalMessage {
  id: number;
  timestamp: string;
  type: "INFO" | "ALERT" | "TRADE" | "SYSTEM" | "DATA";
  content: string;
}

const mockEvents = [
  { type: "SYSTEM", content: "Initializing GenerationalWealth Terminal v2.4.1..." },
  { type: "INFO", content: "Connecting to global market data feeds..." },
  { type: "INFO", content: "Connected to SEC EDGAR database." },
  { type: "INFO", content: "Connected to FINRA Trade Reporting Facility." },
  { type: "SYSTEM", content: "Data stream synchronized. Waiting for events..." },
  { type: "DATA", content: "ANALYZING 13F: Berkshire Hathaway Inc. (CIK: 0001067983)" },
  { type: "TRADE", content: "CAPITOL TRADE ALERT: Hon. Nancy Pelosi (D) bought $500k-$1M NVDA Call Options" },
  { type: "ALERT", content: "TECHNICAL SIGNAL: $TSLA RSI(14) Oversold at 28.5 - Probable bounce." },
  { type: "DATA", content: "COMMODITY UPDATE: GC=F (Gold) spiked +1.2% in the last 15 minutes." },
  { type: "INFO", content: "MARKET CORRELATION: Detected high correlation (0.89) between $BTC and $QQQ." },
  { type: "TRADE", content: "INSIDER TRADE: Mark Zuckerberg (META) sold 15,000 shares at $482.10." },
  { type: "DATA", content: "MACRO: Treasury 10-Year Yield (TNX) dropped to 4.12%." },
  { type: "ALERT", content: "SENTIMENT SHIFT: Truth Social sentiment on $DJT turned heavily negative." },
  { type: "TRADE", content: "INSTITUTIONAL FLOW: Dark pool block trade detected on $AAPL - 1.2M shares." },
  { type: "DATA", content: "POLYMARKET: Probability of Rate Cut in Sept increased to 82%." },
  { type: "INFO", content: "PORTFOLIO: Re-evaluating Beta based on new VIX levels (VIX: 14.5)." },
  { type: "ALERT", content: "VOLATILITY: $SMCI options implied volatility rank > 95%." },
];

const getTypeColor = (type: string) => {
  switch (type) {
    case "SYSTEM":
      return "text-purple-400";
    case "INFO":
      return "text-blue-400";
    case "ALERT":
      return "text-red-400";
    case "TRADE":
      return "text-green-400";
    case "DATA":
      return "text-yellow-400";
    default:
      return "text-gray-400";
  }
};

export default function LiveTerminalPreview() {
  const [messages, setMessages] = useState<TerminalMessage[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let currentIndex = 0;
    
    // Add initial messages faster
    const initialInterval = setInterval(() => {
      if (currentIndex < 5) {
        const event = mockEvents[currentIndex];
        const now = new Date();
        const timestamp = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;
        
        setMessages((prev) => [
          ...prev,
          { id: Date.now() + currentIndex, timestamp, type: event.type as any, content: event.content },
        ]);
        currentIndex++;
      } else {
        clearInterval(initialInterval);
        startRandomFeed(currentIndex);
      }
    }, 400);

    const startRandomFeed = (startIndex: number) => {
      let idx = startIndex;
      const interval = setInterval(() => {
        if (idx < mockEvents.length) {
          const event = mockEvents[idx];
          const now = new Date();
          const timestamp = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;
          
          setMessages((prev) => {
            const newMessages = [...prev, { id: Date.now(), timestamp, type: event.type as any, content: event.content }];
            if (newMessages.length > 20) return newMessages.slice(newMessages.length - 20); // Keep last 20
            return newMessages;
          });
          idx++;
        } else {
          idx = 5; // Loop back after initial setup
        }
      }, 2500 + Math.random() * 2000); // Random delay between 2.5s and 4.5s
      
      return () => clearInterval(interval);
    };

    return () => clearInterval(initialInterval);
  }, []);

  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: "smooth"
      });
    }
  }, [messages]);

  return (
    <div className="w-full max-w-4xl mx-auto rounded-xl overflow-hidden border border-zinc-800 bg-zinc-950/80 backdrop-blur-xl shadow-2xl">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
        </div>
        <div className="text-xs font-mono text-zinc-500">Live Data Stream</div>
        <div className="flex space-x-1">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-[10px] text-green-500 uppercase tracking-widest font-semibold ml-1">Live</span>
        </div>
      </div>

      {/* Terminal Body */}
      <div ref={scrollContainerRef} className="p-4 sm:p-6 font-mono text-sm h-[350px] overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        <div className="space-y-2">
          {messages.map((msg) => (
            <div key={msg.id} className="flex flex-col sm:flex-row sm:items-start group">
              <div className="flex items-center text-zinc-500 w-32 shrink-0">
                <span>[{msg.timestamp}]</span>
              </div>
              <div className="flex flex-1 mt-1 sm:mt-0">
                <span className={`w-20 shrink-0 font-semibold ${getTypeColor(msg.type)}`}>
                  {msg.type}
                </span>
                <span className="text-zinc-300 ml-2 group-hover:text-white transition-colors duration-200">
                  {msg.content}
                </span>
              </div>
            </div>
          ))}
        </div>
        
        {/* Blinking Cursor */}
        <div className="flex items-center mt-2 text-zinc-500">
          <span>{'>'}</span>
          <div className="w-2 h-4 bg-zinc-400 ml-2 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}
