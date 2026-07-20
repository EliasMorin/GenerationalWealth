import Link from "next/link";
import { Terminal } from "lucide-react";

export function Navbar() {
  return (
    <header className="fixed top-0 w-full z-50 border-b border-white/5 glass">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-white font-medium">
          <Terminal className="w-5 h-5" />
          <span>GenerationalWealth</span>
        </Link>
        
        <nav className="hidden md:flex items-center gap-8 text-sm text-gray-400">
          <Link href="#features" className="hover:text-white transition-colors">Features</Link>
          <Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link>
          <Link href="#faq" className="hover:text-white transition-colors">FAQ</Link>
        </nav>

        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm text-gray-300 hover:text-white transition-colors">
            Log in
          </Link>
          <Link href="/signup" className="text-sm bg-white text-black px-4 py-2 rounded-full font-medium hover:bg-gray-200 transition-colors">
            Get Started
          </Link>
        </div>
      </div>
    </header>
  );
}
