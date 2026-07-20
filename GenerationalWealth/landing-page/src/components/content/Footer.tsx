import Link from "next/link";
import { Activity } from "lucide-react";

const links = {
  Product: ["Features", "Pricing", "API", "Download", "Changelog"],
  Company: ["About", "Blog", "Careers", "Customers", "Contact"],
  Legal: ["Privacy Policy", "Terms of Service", "Cookie Policy", "Security"],
};

export function Footer() {
  return (
    <footer className="border-t border-neutral-800 bg-black pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-16">
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-2 mb-6 w-fit group">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center group-hover:bg-neutral-200 transition-colors">
                <Activity className="w-5 h-5 text-black" />
              </div>
              <span className="text-xl font-medium text-white tracking-tight">
                GenerationalWealth
              </span>
            </Link>
            <p className="text-neutral-500 max-w-sm mb-6 text-sm leading-relaxed">
              The modern financial terminal. Institutional-grade data, analytics, and execution, built for the next generation of firms.
            </p>
          </div>
          
          {Object.entries(links).map(([category, items]) => (
            <div key={category}>
              <h3 className="font-medium text-white mb-4 text-sm">{category}</h3>
              <ul className="space-y-3">
                {items.map((item) => (
                  <li key={item}>
                    <Link 
                      href="#" 
                      className="text-neutral-400 hover:text-white transition-colors text-sm"
                    >
                      {item}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        
        <div className="flex flex-col md:flex-row items-center justify-between pt-8 border-t border-neutral-800/50 text-neutral-500 text-sm">
          <p>© {new Date().getFullYear()} GenerationalWealth Inc. All rights reserved.</p>
          <div className="flex space-x-6 mt-4 md:mt-0">
            <Link href="#" className="hover:text-white transition-colors">Twitter</Link>
            <Link href="#" className="hover:text-white transition-colors">LinkedIn</Link>
            <Link href="#" className="hover:text-white transition-colors">GitHub</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
