import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { FileWarning, TrendingUp, AlertTriangle, Tag } from "lucide-react";

interface SentimentYear {
  score: number;
  level: string;
  keywords: string[];
}

interface AuditorSentimentChartProps {
  sentimentData: Record<string, SentimentYear> | null;
}

const levelColors: Record<string, { bg: string; text: string; dot: string }> = {
  CRITICAL: { bg: "bg-[#FEE2E2]", text: "text-[#EF4444]", dot: "#EF4444" },
  CONCERNING: { bg: "bg-[#FFEDD5]", text: "text-[#F97316]", dot: "#F97316" },
  CAUTIOUS: { bg: "bg-[#FEF3C7]", text: "text-[#F59E0B]", dot: "#F59E0B" },
  STABLE: { bg: "bg-[#DCFCE7]", text: "text-[#22C55E]", dot: "#22C55E" },
  POSITIVE: { bg: "bg-[#DBEAFE]", text: "text-[#3B82F6]", dot: "#3B82F6" },
};

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value?: number; payload?: { level?: string; keywords?: string[] } }>;
  label?: string;
}) => {
  if (!active || !payload || !payload.length || !payload[0]) return null;

  const data = payload[0];
  const level = data.payload?.level || "STABLE";
  const colors = levelColors[level] || levelColors.STABLE;
  const value = typeof data.value === 'number' ? data.value : 0;

  return (
    <div className="rounded-lg border border-[#E2E8F0] bg-white p-3 shadow-lg">
      <p className="text-sm font-semibold text-[#1E293B]">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-lg font-bold text-[#1E293B]">
          {value.toFixed(1)}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}>
          {level}
        </span>
      </div>
      {data.payload?.keywords && data.payload.keywords.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {data.payload.keywords.slice(0, 5).map((kw, i) => (
            <span
              key={i}
              className="rounded bg-[#F1F5F9] px-1.5 py-0.5 text-xs text-[#64748B]"
            >
              {kw}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

const CustomDot = ({
  cx,
  cy,
  payload,
}: {
  cx?: number;
  cy?: number;
  payload?: { level: string };
}) => {
  if (!cx || !cy || !payload) return null;
  
  const level = payload.level || "STABLE";
  const colors = levelColors[level] || levelColors.STABLE;

  return (
    <circle
      cx={cx}
      cy={cy}
      r={6}
      fill={colors.dot}
      stroke="white"
      strokeWidth={2}
    />
  );
};

const AuditorSentimentChart = ({ sentimentData }: AuditorSentimentChartProps) => {
  // Edge case: No sentiment data available
  if (!sentimentData || Object.keys(sentimentData).length === 0) {
    return (
      <div className="rounded-xl border border-[#F59E0B]/30 bg-gradient-to-br from-[#FEF3C7]/50 to-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <TrendingUp className="h-4 w-4" />
          Auditor Note Sentiment Trend
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="rounded-full bg-[#FEF3C7] p-4">
            <FileWarning className="h-10 w-10 text-[#F59E0B]" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-[#F59E0B]">
            Data Status: UNAVAILABLE
          </h3>
          <p className="mt-2 max-w-md text-sm text-[#64748B]">
            Manual PDF upload required. Please place the annual report in:
          </p>
          <code className="mt-2 rounded bg-[#1E293B] px-3 py-1.5 text-xs text-[#22C55E]">
            .cache/auditgpt/pdfs/
          </code>
          <p className="mt-3 text-xs text-[#94A3B8]">
            Once uploaded, re-run the analysis to extract auditor sentiment.
          </p>
        </div>
      </div>
    );
  }

  // Transform data for Recharts
  const chartData = Object.entries(sentimentData)
    .filter(([, data]) => data != null && typeof data === 'object')
    .map(([year, data]) => ({
      year,
      score: typeof data.score === 'number' ? data.score : 0,
      level: data.level || 'STABLE',
      keywords: Array.isArray(data.keywords) ? data.keywords : [],
    }))
    .filter((item) => !isNaN(item.score))
    .sort((a, b) => parseInt(a.year) - parseInt(b.year));

  // If no valid chart data after filtering, show unavailable state
  if (chartData.length === 0) {
    return (
      <div className="rounded-xl border border-[#F59E0B]/30 bg-gradient-to-br from-[#FEF3C7]/50 to-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <TrendingUp className="h-4 w-4" />
          Auditor Note Sentiment Trend
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="rounded-full bg-[#FEF3C7] p-4">
            <FileWarning className="h-10 w-10 text-[#F59E0B]" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-[#F59E0B]">
            Invalid Sentiment Data
          </h3>
          <p className="mt-2 max-w-md text-sm text-[#64748B]">
            Sentiment data format is not compatible. Please re-run the analysis.
          </p>
        </div>
      </div>
    );
  }

  // Collect all unique keywords
  const allKeywords = Array.from(
    new Set(chartData.flatMap((d) => d.keywords))
  ).slice(0, 12);

  // Calculate trend direction
  const scores = chartData.map((d) => d.score).filter((s) => typeof s === 'number' && !isNaN(s));
  const trend = scores.length >= 2 
    ? scores[scores.length - 1] - scores[0]
    : 0;

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <TrendingUp className="h-4 w-4" />
          Auditor Note Sentiment Trend
        </h2>
        {trend !== 0 && (
          <span
            className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
              trend > 0
                ? "bg-[#DCFCE7] text-[#22C55E]"
                : "bg-[#FEE2E2] text-[#EF4444]"
            }`}
          >
            {trend > 0 ? "↑ Improving" : "↓ Declining"}
          </span>
        )}
      </div>

      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 12, fill: "#64748B" }}
              axisLine={{ stroke: "#E2E8F0" }}
              tickLine={{ stroke: "#E2E8F0" }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 12, fill: "#64748B" }}
              axisLine={{ stroke: "#E2E8F0" }}
              tickLine={{ stroke: "#E2E8F0" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={50}
              stroke="#94A3B8"
              strokeDasharray="5 5"
              label={{
                value: "Neutral",
                position: "right",
                fontSize: 10,
                fill: "#94A3B8",
              }}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#3B82F6"
              strokeWidth={3}
              dot={<CustomDot />}
              activeDot={{ r: 8, strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap items-center justify-center gap-3 border-t border-[#E2E8F0] pt-4">
        {Object.entries(levelColors).map(([level, colors]) => (
          <div key={level} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: colors.dot }}
            />
            <span className="text-xs text-[#64748B]">{level}</span>
          </div>
        ))}
      </div>

      {/* Keywords */}
      {allKeywords.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-2">
            <Tag className="h-3.5 w-3.5 text-[#94A3B8]" />
            <span className="text-xs font-medium text-[#94A3B8]">
              Key Themes:
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {allKeywords.map((keyword, index) => (
              <span
                key={index}
                className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-xs text-[#64748B] transition-colors hover:border-[#3B82F6] hover:text-[#3B82F6]"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Score Summary */}
      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-[#E2E8F0] pt-4">
        {chartData.slice(-3).map((data, index) => {
          const colors = levelColors[data.level] || levelColors.STABLE;
          const scoreValue = typeof data.score === 'number' ? data.score : 0;
          return (
            <div
              key={index}
              className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2 text-center"
            >
              <p className="text-xs text-[#94A3B8]">{data.year}</p>
              <p className="text-lg font-bold text-[#1E293B]">
                {scoreValue.toFixed(1)}
              </p>
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}
              >
                {data.level || 'N/A'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AuditorSentimentChart;
