import { useState } from "react";
import type { FormEvent } from "react";
import { ShieldAlert, TrendingDown, Activity, Search, Loader2, AlertCircle } from "lucide-react";
import DashboardHeader from "../components/DashboardHeader";
import MetricCard from "../components/MetricCard";
import DualRiskMatrix from "../components/DualRiskMatrix";

// ============================================
// TypeScript Interfaces
// ============================================

interface DualScore {
  manipulation_score: number;
  manipulation_level: string;
  stress_score: number;
  stress_level: string;
}

interface Anomaly {
  type: string;
  year: number | null;
  severity: string;
  category: string;
  description: string;
  evidence: string[];
}

interface PeerInfo {
  company: string;
  sector: string;
  match_score: number;
  reason: string;
}

interface PeerComparison {
  peers: PeerInfo[];
  benchmarks: Record<string, unknown>;
}

interface AnalysisResult {
  ticker: string;
  name: string;
  sector: string;
  risk_score: number;
  risk_level: string;
  dual_score: DualScore;
  anomalies: Anomaly[];
  peer_comparison: PeerComparison;
  ratios: Record<string, unknown>;
  auditor_sentiment: Record<string, unknown> | null;
  rpt_growth_data: Record<string, unknown>;
  missing_data: string[];
  timing: Record<string, unknown>;
  report: string;
}

// ============================================
// Helper Functions
// ============================================

/**
 * Maps risk level string to severity for MetricCard styling
 */
const getSeverity = (level: string): "low" | "medium" | "high" | "critical" => {
  const normalized = level.toUpperCase();
  if (normalized === "LOW") return "low";
  if (normalized === "MEDIUM") return "medium";
  if (normalized === "HIGH") return "high";
  return "critical";
};

// ============================================
// Main Component
// ============================================

// API Base URL - change this for production deployment
const API_BASE_URL = "http://localhost:8000";

const Index = () => {
  // State management
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState<string>("");

  /**
   * Fetch analysis from backend API
   * @param tickerSymbol - Company ticker symbol (e.g., "YESBANK", "HDFCBANK")
   */
  const fetchAnalysis = async (tickerSymbol: string): Promise<void> => {
    setIsLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/analyze/${tickerSymbol.toUpperCase()}`
      );

      if (!response.ok) {
        // Try to parse error details from response
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Failed to fetch analysis for ${tickerSymbol}`
        );
      }

      const result: AnalysisResult = await response.json();
      setData(result);
    } catch (err) {
      // Handle network errors and API errors
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(`Failed to fetch analysis for ${tickerSymbol}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle form submission (triggered by button click or Enter key)
   */
  const handleAnalyze = async (e: FormEvent) => {
    e.preventDefault();

    const trimmedTicker = ticker.trim();
    if (!trimmedTicker) {
      setError("Please enter a ticker symbol");
      return;
    }

    await fetchAnalysis(trimmedTicker);
  };

  /**
   * Handle keyboard events for the input field
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const trimmedTicker = ticker.trim();
      if (trimmedTicker) {
        fetchAnalysis(trimmedTicker);
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-[#f8fafc]">
      <DashboardHeader />
      
      <main className="mx-auto max-w-7xl space-y-6 p-6">
        {/* Search Bar */}
        <section className="rounded-xl border border-[#334155] bg-[#1e293b] p-4 shadow-lg">
          <form onSubmit={handleAnalyze} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-[#64748b]" />
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={handleKeyDown}
                placeholder="Enter company ticker (e.g., YESBANK, HDFCBANK, TCS)"
                className="w-full rounded-lg border border-[#334155] bg-[#0f172a] py-3 pl-10 pr-4 text-[#f8fafc] placeholder-[#64748b] outline-none transition-colors focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]"
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 rounded-lg bg-[#3b82f6] px-6 py-3 font-semibold text-white transition-colors hover:bg-[#2563eb] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="h-5 w-5" />
                  Analyze
                </>
              )}
            </button>
          </form>

          {/* Error Message */}
          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-[#ef4444]/30 bg-[#ef4444]/10 p-3 text-[#ef4444]">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </section>

        {/* Loading State */}
        {isLoading && (
          <section className="flex flex-col items-center justify-center py-20">
            <div className="relative">
              <div className="h-16 w-16 animate-spin rounded-full border-4 border-[#334155] border-t-[#3b82f6]"></div>
            </div>
            <p className="mt-4 text-[#94a3b8]">Analyzing {ticker}...</p>
            <p className="mt-1 text-xs text-[#64748b]">This may take up to 90 seconds for comprehensive analysis</p>
          </section>
        )}

        {/* Dashboard Content - Only show when data is available */}
        {data && !isLoading && (
          <>
            {/* Company Header */}
            <section className="rounded-xl border border-[#334155] bg-[#1e293b] p-4 shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-[#f8fafc]">{data.ticker}</h1>
                  <p className="text-sm text-[#94a3b8]">{data.sector} Sector</p>
                </div>
                <div className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                  data.risk_level === "LOW" ? "bg-[#22c55e]/20 text-[#22c55e]" :
                  data.risk_level === "MEDIUM" ? "bg-[#f59e0b]/20 text-[#f59e0b]" :
                  data.risk_level === "HIGH" ? "bg-[#f97316]/20 text-[#f97316]" :
                  "bg-[#ef4444]/20 text-[#ef4444]"
                }`}>
                  {data.risk_level} RISK
                </div>
              </div>
            </section>

            {/* Executive Summary */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
                Executive Summary
              </h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <MetricCard
                  title="Manipulation Risk"
                  value={data.dual_score.manipulation_score}
                  maxValue={100}
                  severity={getSeverity(data.dual_score.manipulation_level)}
                  label={data.dual_score.manipulation_level}
                  icon={<ShieldAlert className="h-4 w-4" />}
                />
                <MetricCard
                  title="Financial Stress Risk"
                  value={data.dual_score.stress_score}
                  maxValue={100}
                  severity={getSeverity(data.dual_score.stress_level)}
                  label={data.dual_score.stress_level}
                  icon={<TrendingDown className="h-4 w-4" />}
                />
                <MetricCard
                  title="Combined Score"
                  value={data.risk_score}
                  maxValue={100}
                  severity={getSeverity(data.risk_level)}
                  label={data.risk_level}
                  icon={<Activity className="h-4 w-4" />}
                />
              </div>
            </section>

            {/* Two-column grid */}
            <section className="grid gap-6 lg:grid-cols-2">
              <DualRiskMatrix 
                manipulationScore={data.dual_score.manipulation_score}
                stressScore={data.dual_score.stress_score}
              />
              <div className="rounded-xl border border-[#334155] bg-[#1e293b] p-5 shadow-lg">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[#94a3b8]">
                  Analysis Details
                </h2>
                <p className="text-sm leading-relaxed text-[#94a3b8]">
                  {data.ticker} exhibits {data.dual_score.stress_level === "CRITICAL" || data.dual_score.stress_level === "HIGH" 
                    ? "elevated financial stress indicators consistent with liquidity pressure and asset quality deterioration" 
                    : "stable financial indicators with manageable stress levels"}. 
                  Manipulation signals remain {data.dual_score.manipulation_level.toLowerCase()}, suggesting {
                    data.dual_score.manipulation_level === "LOW" 
                      ? "transparent reporting practices" 
                      : "potential concerns requiring further investigation"
                  }. The dual-risk positioning places the entity in the{" "}
                  <span className={`font-medium ${
                    data.dual_score.stress_score > 50 && data.dual_score.manipulation_score < 50 
                      ? "text-[#f59e0b]" 
                      : data.dual_score.manipulation_score > 50 
                        ? "text-[#ef4444]" 
                        : "text-[#22c55e]"
                  }`}>
                    {data.dual_score.stress_score > 50 && data.dual_score.manipulation_score < 50 
                      ? "Stressed" 
                      : data.dual_score.manipulation_score > 50 && data.dual_score.stress_score < 50 
                        ? "Suspicious" 
                        : data.dual_score.manipulation_score > 50 && data.dual_score.stress_score > 50 
                          ? "Critical" 
                          : "Healthy"}
                  </span>{" "}
                  quadrant.
                </p>
              </div>
            </section>

            {/* Anomalies Section */}
            {data.anomalies.length > 0 && (
              <section>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
                  Detected Anomalies ({data.anomalies.length})
                </h2>
                <div className="space-y-3">
                  {data.anomalies.map((anomaly, index) => (
                    <div
                      key={index}
                      className={`rounded-lg border p-4 ${
                        anomaly.severity === "CRITICAL" 
                          ? "border-[#ef4444]/30 bg-[#ef4444]/10" 
                          : anomaly.severity === "HIGH"
                            ? "border-[#f97316]/30 bg-[#f97316]/10"
                            : anomaly.severity === "MEDIUM"
                              ? "border-[#f59e0b]/30 bg-[#f59e0b]/10"
                              : "border-[#334155] bg-[#1e293b]"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs font-semibold uppercase ${
                              anomaly.severity === "CRITICAL" ? "text-[#ef4444]" :
                              anomaly.severity === "HIGH" ? "text-[#f97316]" :
                              anomaly.severity === "MEDIUM" ? "text-[#f59e0b]" :
                              "text-[#94a3b8]"
                            }`}>
                              {anomaly.severity}
                            </span>
                            <span className="text-xs text-[#64748b]">•</span>
                            <span className="text-xs text-[#64748b]">{anomaly.type}</span>
                            {anomaly.year && (
                              <>
                                <span className="text-xs text-[#64748b]">•</span>
                                <span className="text-xs text-[#64748b]">{anomaly.year}</span>
                              </>
                            )}
                          </div>
                          <p className="mt-1 text-sm text-[#f8fafc]">{anomaly.description}</p>
                          {anomaly.evidence.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs text-[#64748b]">Evidence:</p>
                              <ul className="mt-1 list-inside list-disc text-xs text-[#94a3b8]">
                                {anomaly.evidence.slice(0, 3).map((ev, i) => (
                                  <li key={i}>{ev}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                        <span className={`rounded px-2 py-1 text-xs font-medium ${
                          anomaly.category === "manipulation" 
                            ? "bg-[#ef4444]/20 text-[#ef4444]" 
                            : "bg-[#f59e0b]/20 text-[#f59e0b]"
                        }`}>
                          {anomaly.category}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Peer Comparison */}
            {data.peer_comparison.peers.length > 0 && (
              <section>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
                  Peer Comparison
                </h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {data.peer_comparison.peers.map((peer, index) => (
                    <div
                      key={index}
                      className="rounded-lg border border-[#334155] bg-[#1e293b] p-4"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-[#f8fafc]">{peer.company}</span>
                        <span className="text-xs text-[#64748b]">{(peer.match_score * 100).toFixed(0)}% match</span>
                      </div>
                      <p className="mt-1 text-xs text-[#94a3b8]">{peer.reason}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {/* Empty State */}
        {!data && !isLoading && !error && (
          <section className="flex flex-col items-center justify-center py-20">
            <div className="rounded-full bg-[#1e293b] p-6">
              <Search className="h-12 w-12 text-[#64748b]" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-[#f8fafc]">Start Your Analysis</h3>
            <p className="mt-2 max-w-md text-center text-sm text-[#94a3b8]">
              Enter a company ticker symbol above to generate a comprehensive forensic analysis
              including fraud risk assessment, peer comparison, and anomaly detection.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {["YESBANK", "HDFCBANK", "TCS", "RELIANCE"].map((example) => (
                <button
                  key={example}
                  onClick={() => setTicker(example)}
                  className="rounded-lg border border-[#334155] bg-[#1e293b] px-3 py-1 text-sm text-[#94a3b8] transition-colors hover:border-[#3b82f6] hover:text-[#f8fafc]"
                >
                  {example}
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
};

export default Index;
