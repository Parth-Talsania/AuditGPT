import { useState, useEffect } from "react";
import type { FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ShieldAlert, TrendingDown, Activity, Search, Loader2, AlertCircle, ArrowLeft } from "lucide-react";
import MetricCard from "../components/MetricCard";
import DualRiskMatrix from "../components/DualRiskMatrix";
import XAITraceSection from "../components/XAITraceSection";
import PeerBenchmarkTable from "../components/PeerBenchmarkTable";
import AuditorSentimentChart from "../components/AuditorSentimentChart";
import DataAvailabilityPanel from "../components/DataAvailabilityPanel";

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

interface PeerBenchmark {
  value: number;
  median: number;
  position: "ABOVE" | "BELOW" | "AT_MEDIAN";
  deviation_pct: number;
}

interface PeerComparison {
  peers: PeerInfo[];
  benchmarks: Record<string, PeerBenchmark> | null;
}

interface XAISignal {
  signal_family: string;
  year: number;
  severity: string;
  contribution_pct: number;
  description: string;
}

interface XAITrace {
  primary_driver: string | null;
  evidence_chain: string[];
  logical_rule_triggered: string | null;
  signal_contributions: XAISignal[];
}

interface SentimentYear {
  score: number;
  level: string;
  keywords: string[];
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
  auditor_sentiment: Record<string, SentimentYear> | null;
  rpt_growth_data: Record<string, unknown>;
  missing_data: Record<string, boolean> | string[];
  xai_trace: XAITrace | null;
  timing: Record<string, unknown>;
  report: string;
}

// Helper Functions
const getSeverity = (level: string): "low" | "medium" | "high" | "critical" => {
  const normalized = level.toUpperCase();
  if (normalized === "LOW") return "low";
  if (normalized === "MEDIUM") return "medium";
  if (normalized === "HIGH") return "high";
  return "critical";
};

const API_BASE_URL = "http://localhost:8000";

// Dashboard Header Component
const DashboardHeader = () => {
  const navigate = useNavigate();

  return (
    <header className="border-b border-[#E2E8F0] bg-white/80 backdrop-blur-sm px-6 py-4 shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Back to Home Button */}
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-sm text-[#64748B] shadow-sm transition-all hover:border-[#3B82F6] hover:text-[#3B82F6] hover:shadow-md"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Back to Home</span>
          </button>

          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-[#3B82F6] to-[#8B5CF6] shadow-md">
              <Activity className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#1E293B]">AuditGPT</h1>
              <p className="text-xs text-[#94A3B8]">Analysis Dashboard</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="rounded-full bg-[#DCFCE7] px-3 py-1 text-xs font-medium text-[#22C55E]">
            v2.0
          </span>
        </div>
      </div>
    </header>
  );
};

// Main Dashboard Component
const Dashboard = () => {
  const { ticker: urlTicker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState<string>(urlTicker?.toUpperCase() || "");

  const fetchAnalysis = async (tickerSymbol: string): Promise<void> => {
    setIsLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/analyze/${tickerSymbol.toUpperCase()}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Failed to fetch analysis for ${tickerSymbol}`
        );
      }

      const result: AnalysisResult = await response.json();
      setData(result);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(`Failed to fetch analysis for ${tickerSymbol}`);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyze = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedTicker = ticker.trim().toUpperCase();
    if (trimmedTicker) {
      navigate(`/analyze/${trimmedTicker}`, { replace: true });
      await fetchAnalysis(trimmedTicker);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const trimmedTicker = ticker.trim().toUpperCase();
      if (trimmedTicker) {
        navigate(`/analyze/${trimmedTicker}`, { replace: true });
        fetchAnalysis(trimmedTicker);
      }
    }
  };

  useEffect(() => {
    if (urlTicker) {
      setTicker(urlTicker.toUpperCase());
      fetchAnalysis(urlTicker);
    }
  }, [urlTicker]);

  return (
    <div className="min-h-screen text-[#1E293B]">
      <DashboardHeader />

      <main className="mx-auto max-w-7xl space-y-6 p-6">
        {/* Search Bar */}
        <section className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-lg">
          <form onSubmit={handleAnalyze} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-[#94A3B8]" />
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={handleKeyDown}
                placeholder="Enter company ticker (e.g., YESBANK, HDFCBANK, TCS)"
                className="w-full rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] py-3 pl-10 pr-4 text-[#1E293B] placeholder-[#94A3B8] outline-none transition-colors focus:border-[#3B82F6] focus:bg-white focus:ring-2 focus:ring-[#3B82F6]/20"
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] px-6 py-3 font-semibold text-white shadow-md transition-all hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
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
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-[#EF4444]/30 bg-[#FEE2E2] p-3 text-[#EF4444]">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </section>

        {/* Loading State */}
        {isLoading && (
          <section className="flex flex-col items-center justify-center py-20">
            <div className="relative">
              <div className="h-16 w-16 animate-spin rounded-full border-4 border-[#E2E8F0] border-t-[#3B82F6]"></div>
            </div>
            <p className="mt-4 text-[#64748B]">Analyzing {ticker}...</p>
            <p className="mt-1 text-xs text-[#94A3B8]">
              This may take up to 90 seconds for comprehensive analysis
            </p>
          </section>
        )}

        {/* Dashboard Content */}
        {data && !isLoading && (
          <>
            {/* Company Header */}
            <section className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-lg">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-[#1E293B]">{data.ticker}</h1>
                  <p className="text-sm text-[#64748B]">{data.sector} Sector</p>
                </div>
                <div
                  className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                    data.risk_level === "LOW"
                      ? "bg-[#DCFCE7] text-[#22C55E]"
                      : data.risk_level === "MEDIUM"
                        ? "bg-[#FEF3C7] text-[#F59E0B]"
                        : data.risk_level === "HIGH"
                          ? "bg-[#FFEDD5] text-[#F97316]"
                          : "bg-[#FEE2E2] text-[#EF4444]"
                  }`}
                >
                  {data.risk_level} RISK
                </div>
              </div>
            </section>

            {/* Executive Summary */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
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
              <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
                  Explainable AI Analysis
                </h2>
                <p className="text-sm leading-relaxed text-[#64748B]">
                  {data.ticker} exhibits{" "}
                  {data.dual_score.stress_level === "CRITICAL" ||
                  data.dual_score.stress_level === "HIGH"
                    ? "elevated financial stress indicators consistent with liquidity pressure and asset quality deterioration"
                    : "stable financial indicators with manageable stress levels"}
                  . Manipulation signals remain{" "}
                  {data.dual_score.manipulation_level.toLowerCase()}, suggesting{" "}
                  {data.dual_score.manipulation_level === "LOW"
                    ? "transparent reporting practices"
                    : "potential concerns requiring further investigation"}
                  . The dual-risk positioning places the entity in the{" "}
                  <span
                    className={`font-semibold ${
                      data.dual_score.stress_score > 50 &&
                      data.dual_score.manipulation_score < 50
                        ? "text-[#F59E0B]"
                        : data.dual_score.manipulation_score > 50
                          ? "text-[#EF4444]"
                          : "text-[#22C55E]"
                    }`}
                  >
                    {data.dual_score.stress_score > 50 &&
                    data.dual_score.manipulation_score < 50
                      ? "Stressed"
                      : data.dual_score.manipulation_score > 50 &&
                          data.dual_score.stress_score < 50
                        ? "Suspicious"
                        : data.dual_score.manipulation_score > 50 &&
                            data.dual_score.stress_score > 50
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
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
                  Detected Anomalies ({data.anomalies.length})
                </h2>
                <div className="space-y-3">
                  {data.anomalies.map((anomaly, index) => (
                    <div
                      key={index}
                      className={`rounded-xl border p-4 shadow-md ${
                        anomaly.severity === "CRITICAL"
                          ? "border-[#EF4444]/30 bg-[#FEE2E2]"
                          : anomaly.severity === "HIGH"
                            ? "border-[#F97316]/30 bg-[#FFEDD5]"
                            : anomaly.severity === "MEDIUM"
                              ? "border-[#F59E0B]/30 bg-[#FEF3C7]"
                              : "border-[#E2E8F0] bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-semibold uppercase ${
                                anomaly.severity === "CRITICAL"
                                  ? "text-[#EF4444]"
                                  : anomaly.severity === "HIGH"
                                    ? "text-[#F97316]"
                                    : anomaly.severity === "MEDIUM"
                                      ? "text-[#F59E0B]"
                                      : "text-[#64748B]"
                              }`}
                            >
                              {anomaly.severity}
                            </span>
                            <span className="text-xs text-[#94A3B8]">•</span>
                            <span className="text-xs text-[#94A3B8]">{anomaly.type}</span>
                            {anomaly.year && (
                              <>
                                <span className="text-xs text-[#94A3B8]">•</span>
                                <span className="text-xs text-[#94A3B8]">{anomaly.year}</span>
                              </>
                            )}
                          </div>
                          <p className="mt-1 text-sm text-[#1E293B]">{anomaly.description}</p>
                          {anomaly.evidence.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs text-[#94A3B8]">Evidence:</p>
                              <ul className="mt-1 list-inside list-disc text-xs text-[#64748B]">
                                {anomaly.evidence.slice(0, 3).map((ev, i) => (
                                  <li key={i}>{ev}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                        <span
                          className={`rounded-lg px-2 py-1 text-xs font-medium ${
                            anomaly.category === "manipulation"
                              ? "bg-[#FEE2E2] text-[#EF4444]"
                              : "bg-[#FEF3C7] text-[#F59E0B]"
                          }`}
                        >
                          {anomaly.category}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* XAI Trace Section - Why This Score? */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
                Possible Signal Strength
              </h2>
              <XAITraceSection xaiTrace={data.xai_trace || null} />
            </section>

            {/* Peer Benchmarking Table */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
                Peer Comparison Analysis
              </h2>
              <PeerBenchmarkTable
                peers={data.peer_comparison.peers}
                benchmarks={data.peer_comparison.benchmarks}
                companyName={data.ticker}
              />
            </section>

            {/* Auditor Sentiment Trend */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
                Auditor Sentiment Analysis
              </h2>
              <AuditorSentimentChart sentimentData={data.auditor_sentiment} />
            </section>

            {/* Data Availability Panel */}
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#64748B]">
                Data Availability & Disclosures
              </h2>
              <DataAvailabilityPanel missingData={data.missing_data} />
            </section>
          </>
        )}

        {/* Empty State */}
        {!data && !isLoading && !error && !urlTicker && (
          <section className="flex flex-col items-center justify-center py-20">
            <div className="rounded-full bg-[#F1F5F9] p-6 shadow-inner">
              <Search className="h-12 w-12 text-[#94A3B8]" />
            </div>
            <h3 className="mt-4 text-lg font-semibold text-[#1E293B]">Start Your Analysis</h3>
            <p className="mt-2 max-w-md text-center text-sm text-[#64748B]">
              Enter a company ticker symbol above to generate a comprehensive forensic analysis.
            </p>
          </section>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
