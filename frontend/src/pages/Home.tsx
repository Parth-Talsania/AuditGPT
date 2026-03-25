import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Activity, ShieldAlert, FileSearch, Users } from "lucide-react";

const Home = () => {
  const [ticker, setTicker] = useState<string>("");
  const navigate = useNavigate();

  const handleAnalyze = (e: FormEvent) => {
    e.preventDefault();
    const trimmedTicker = ticker.trim().toUpperCase();
    if (trimmedTicker) {
      navigate(`/analyze/${trimmedTicker}`);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const trimmedTicker = ticker.trim().toUpperCase();
      if (trimmedTicker) {
        navigate(`/analyze/${trimmedTicker}`);
      }
    }
  };

  const handleQuickAnalyze = (symbol: string) => {
    navigate(`/analyze/${symbol}`);
  };

  return (
    <div className="min-h-screen text-[#1E293B]">
      {/* Hero Section */}
      <div className="flex min-h-screen flex-col items-center justify-center px-6">
        {/* Logo & Branding */}
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-[#3B82F6] to-[#8B5CF6] shadow-xl shadow-[#3B82F6]/20">
            <Activity className="h-10 w-10 text-white" />
          </div>
          <h1 className="mb-3 bg-gradient-to-r from-[#1E293B] to-[#475569] bg-clip-text text-5xl font-bold tracking-tight text-transparent md:text-6xl">
            AuditGPT
          </h1>
          <p className="text-center text-lg text-[#64748B] md:text-xl">
            Financial Statement Forensics Engine
          </p>
          <p className="mt-2 max-w-lg text-center text-sm text-[#94A3B8]">
            The AI that reads 10 years of financial statements and finds what the auditors missed
          </p>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleAnalyze} className="w-full max-w-2xl">
          <div className="group relative">
            <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] opacity-20 blur-lg transition duration-500 group-hover:opacity-30"></div>
            <div className="relative flex items-center gap-3 rounded-xl border border-[#E2E8F0] bg-white p-2 shadow-xl">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[#94A3B8]" />
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  onKeyDown={handleKeyDown}
                  placeholder="Enter company ticker (e.g., YESBANK, HDFCBANK, TCS)"
                  className="w-full rounded-lg bg-[#F8FAFC] py-4 pl-12 pr-4 text-lg text-[#1E293B] placeholder-[#94A3B8] outline-none transition-colors focus:bg-white"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] px-8 py-4 font-semibold text-white shadow-lg shadow-[#3B82F6]/25 transition-all hover:shadow-xl hover:shadow-[#3B82F6]/30"
              >
                <Search className="h-5 w-5" />
                Analyze
              </button>
            </div>
          </div>
        </form>

        {/* Quick Access */}
        <div className="mt-8 flex flex-col items-center">
          <p className="mb-3 text-sm text-[#94A3B8]">Quick access:</p>
          <div className="flex flex-wrap justify-center gap-2">
            {[
              { symbol: "YESBANK", label: "Yes Bank", risk: "high" },
              { symbol: "HDFCBANK", label: "HDFC Bank", risk: "low" },
              { symbol: "TCS", label: "TCS", risk: "low" },
              { symbol: "RELIANCE", label: "Reliance", risk: "medium" },
            ].map((company) => (
              <button
                key={company.symbol}
                onClick={() => handleQuickAnalyze(company.symbol)}
                className="group flex items-center gap-2 rounded-lg border border-[#E2E8F0] bg-white px-4 py-2 text-sm shadow-sm transition-all hover:border-[#3B82F6] hover:shadow-md"
              >
                <span className="font-medium text-[#1E293B]">{company.symbol}</span>
                <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                  company.risk === "high" ? "bg-[#FEE2E2] text-[#EF4444]" :
                  company.risk === "medium" ? "bg-[#FEF3C7] text-[#F59E0B]" :
                  "bg-[#DCFCE7] text-[#22C55E]"
                }`}>
                  {company.risk}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Features Grid */}
        <div className="mt-16 grid max-w-4xl grid-cols-1 gap-6 md:grid-cols-3">
          <div className="rounded-xl border border-[#E2E8F0] bg-white p-6 text-center shadow-lg transition-all hover:shadow-xl">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#DBEAFE]">
              <ShieldAlert className="h-6 w-6 text-[#3B82F6]" />
            </div>
            <h3 className="mb-2 font-semibold text-[#1E293B]">Dual Risk Scoring</h3>
            <p className="text-sm text-[#64748B]">
              Separate manipulation and financial stress scores for comprehensive risk assessment
            </p>
          </div>
          <div className="rounded-xl border border-[#E2E8F0] bg-white p-6 text-center shadow-lg transition-all hover:shadow-xl">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#EDE9FE]">
              <FileSearch className="h-6 w-6 text-[#8B5CF6]" />
            </div>
            <h3 className="mb-2 font-semibold text-[#1E293B]">10-Year Analysis</h3>
            <p className="text-sm text-[#64748B]">
              Multi-year trend detection across balance sheets, P&L, and cash flows
            </p>
          </div>
          <div className="rounded-xl border border-[#E2E8F0] bg-white p-6 text-center shadow-lg transition-all hover:shadow-xl">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#DCFCE7]">
              <Users className="h-6 w-6 text-[#22C55E]" />
            </div>
            <h3 className="mb-2 font-semibold text-[#1E293B]">Peer Benchmarking</h3>
            <p className="text-sm text-[#64748B]">
              Industry-specific comparisons to contextualize every anomaly
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-16 text-center">
          <p className="text-xs text-[#94A3B8]">
            Powered by AI • Analyzing NSE-listed companies • Built for IAR Udaan Hackathon 2026
          </p>
        </div>
      </div>
    </div>
  );
};

export default Home;
