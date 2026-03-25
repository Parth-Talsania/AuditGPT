import { TrendingUp, TrendingDown, Minus, Users, AlertCircle } from "lucide-react";

interface PeerBenchmark {
  company_value?: number;
  peer_median?: number;
  position?: "ABOVE" | "BELOW" | "AT_MEDIAN" | "BETTER" | "WORSE";
  deviation_pct?: number;
  metric_name?: string;
  // Legacy support
  value?: number;
  median?: number;
}

interface PeerInfo {
  company: string;
  sector: string;
  match_score: number;
  reason: string;
}

interface PeerBenchmarkTableProps {
  peers: PeerInfo[];
  benchmarks: Record<string, PeerBenchmark> | null;
  companyName: string;
}

const metricLabels: Record<string, string> = {
  revenue_growth: "Revenue Growth",
  profit_growth: "Profit Growth",
  operating_margin: "Operating Margin",
  roce: "ROCE",
  roe: "ROE",
  debt_equity: "Debt/Equity",
  current_ratio: "Current Ratio",
  interest_coverage: "Interest Coverage",
  asset_turnover: "Asset Turnover",
  npm: "Net Profit Margin",
};

const getPositionStyles = (position: string | undefined | null) => {
  switch (position) {
    case "ABOVE":
      return {
        bgColor: "bg-[#DCFCE7]",
        textColor: "text-[#22C55E]",
        icon: <TrendingUp className="h-4 w-4" />,
        label: "Above",
      };
    case "BELOW":
      return {
        bgColor: "bg-[#FEE2E2]",
        textColor: "text-[#EF4444]",
        icon: <TrendingDown className="h-4 w-4" />,
        label: "Below",
      };
    default:
      return {
        bgColor: "bg-[#FEF3C7]",
        textColor: "text-[#F59E0B]",
        icon: <Minus className="h-4 w-4" />,
        label: position ? "At Median" : "N/A",
      };
  }
};

const formatValue = (value: number | undefined | null, metric: string): string => {
  // Handle undefined/null values
  if (value === undefined || value === null || isNaN(value)) {
    return "N/A";
  }
  // Percentage-based metrics
  if (
    metric.includes("growth") ||
    metric.includes("margin") ||
    metric === "roce" ||
    metric === "roe" ||
    metric === "npm"
  ) {
    return `${value.toFixed(1)}%`;
  }
  // Ratio-based metrics
  if (metric.includes("ratio") || metric === "debt_equity" || metric === "interest_coverage") {
    return value.toFixed(2);
  }
  return value.toFixed(1);
};

const PeerBenchmarkTable = ({ peers, benchmarks, companyName }: PeerBenchmarkTableProps) => {
  // Edge case: No peers available
  if (!peers || peers.length === 0) {
    return (
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <Users className="h-4 w-4" />
          Peer Benchmarking
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="rounded-full bg-[#FEF3C7] p-4">
            <AlertCircle className="h-8 w-8 text-[#F59E0B]" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-[#1E293B]">
            No Peers Available
          </h3>
          <p className="mt-2 max-w-md text-sm text-[#64748B]">
            No comparable companies found for peer comparison in this sector. 
            This may occur for unique business models or niche sectors.
          </p>
        </div>
      </div>
    );
  }

  // Edge case: No benchmarks data
  if (!benchmarks || Object.keys(benchmarks).length === 0) {
    return (
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <Users className="h-4 w-4" />
          Peer Benchmarking
        </h2>
        
        {/* Show peer list without benchmarks */}
        <div className="mb-4 rounded-lg border border-[#DBEAFE] bg-[#EFF6FF] p-3">
          <p className="text-xs font-medium text-[#3B82F6]">
            Comparing against {peers.length} peer{peers.length > 1 ? "s" : ""}:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {peers.map((peer, index) => (
              <span
                key={index}
                className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-[#3B82F6] shadow-sm"
              >
                {peer.company}
              </span>
            ))}
          </div>
        </div>
        
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <AlertCircle className="h-8 w-8 text-[#94A3B8]" />
          <p className="mt-3 text-sm text-[#64748B]">
            Benchmark metrics not available. Insufficient comparable data.
          </p>
        </div>
      </div>
    );
  }

  // Normal case: Display full benchmark table
  const benchmarkEntries = Object.entries(benchmarks);

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
        <Users className="h-4 w-4" />
        Peer Benchmarking
      </h2>

      {/* Peer Pills */}
      <div className="mb-4 rounded-lg border border-[#DBEAFE] bg-[#EFF6FF] p-3">
        <p className="text-xs font-medium text-[#3B82F6]">
          Comparing {companyName} against {peers.length} peer{peers.length > 1 ? "s" : ""}:
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {peers.map((peer, index) => (
            <span
              key={index}
              className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-[#3B82F6] shadow-sm"
              title={peer.reason}
            >
              {peer.company}
              <span className="ml-1 text-[#94A3B8]">
                ({(peer.match_score * 100).toFixed(0)}%)
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Benchmark Table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[400px]">
          <thead>
            <tr className="border-b border-[#E2E8F0]">
              <th className="pb-3 text-left text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">
                Metric
              </th>
              <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">
                {companyName}
              </th>
              <th className="pb-3 text-right text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">
                Peer Median
              </th>
              <th className="pb-3 text-center text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">
                Position
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0]">
            {benchmarkEntries
              .filter(([, benchmark]) => benchmark != null)
              .map(([metricKey, benchmark], index) => {
              const positionStyle = getPositionStyles(benchmark?.position);
              const metricLabel = metricLabels[metricKey] || metricKey.replace(/_/g, " ");
              // Support both new (company_value/peer_median) and legacy (value/median) formats
              const companyValue = benchmark?.company_value ?? benchmark?.value;
              const peerMedian = benchmark?.peer_median ?? benchmark?.median;

              return (
                <tr
                  key={index}
                  className="transition-colors hover:bg-[#F8FAFC]"
                >
                  <td className="py-3 text-sm font-medium capitalize text-[#1E293B]">
                    {metricLabel}
                  </td>
                  <td className="py-3 text-right text-sm tabular-nums text-[#64748B]">
                    {formatValue(companyValue, metricKey)}
                  </td>
                  <td className="py-3 text-right text-sm tabular-nums text-[#64748B]">
                    {formatValue(peerMedian, metricKey)}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center justify-center">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${positionStyle.bgColor} ${positionStyle.textColor}`}
                      >
                        {positionStyle.icon}
                        {positionStyle.label}
                        {benchmark.deviation_pct != null && benchmark.deviation_pct !== 0 && (
                          <span className="opacity-75">
                            ({benchmark.deviation_pct > 0 ? "+" : ""}
                            {benchmark.deviation_pct?.toFixed(0) ?? 0}%)
                          </span>
                        )}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="mt-4 flex flex-wrap items-center justify-center gap-4 border-t border-[#E2E8F0] pt-4">
        {["ABOVE", "AT_MEDIAN", "BELOW"].map((position) => {
          const count = benchmarkEntries.filter(
            ([, b]) => b?.position === position
          ).length;
          const style = getPositionStyles(position);
          return (
            <div key={position} className="flex items-center gap-2">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${style.bgColor} ${style.textColor}`}
              >
                {count}
              </span>
              <span className="text-xs text-[#64748B]">{style.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PeerBenchmarkTable;
