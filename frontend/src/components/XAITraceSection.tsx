import { CheckCircle2, AlertTriangle, Info, ChevronRight } from "lucide-react";

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

interface XAITraceSectionProps {
  xaiTrace: XAITrace | null;
}

const severityColors: Record<string, { bg: string; bar: string; text: string }> = {
  CRITICAL: { bg: "bg-[#FEE2E2]", bar: "bg-[#EF4444]", text: "text-[#EF4444]" },
  HIGH: { bg: "bg-[#FFEDD5]", bar: "bg-[#F97316]", text: "text-[#F97316]" },
  MEDIUM: { bg: "bg-[#FEF3C7]", bar: "bg-[#F59E0B]", text: "text-[#F59E0B]" },
  LOW: { bg: "bg-[#DCFCE7]", bar: "bg-[#22C55E]", text: "text-[#22C55E]" },
};

const XAITraceSection = ({ xaiTrace }: XAITraceSectionProps) => {
  // Edge case: No XAI trace data available
  if (!xaiTrace) {
    return (
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <Info className="h-4 w-4" />
          Why This Score?
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="rounded-full bg-[#F1F5F9] p-4">
            <Info className="h-8 w-8 text-[#94A3B8]" />
          </div>
          <p className="mt-3 text-sm text-[#64748B]">
            Explainability data not available for this analysis.
          </p>
        </div>
      </div>
    );
  }

  // Edge case: No anomalies detected (healthy state)
  const isHealthy =
    !xaiTrace.signal_contributions ||
    xaiTrace.signal_contributions.length === 0 ||
    xaiTrace.primary_driver === "No anomalies detected" ||
    xaiTrace.primary_driver === null;

  if (isHealthy) {
    return (
      <div className="rounded-xl border border-[#22C55E]/30 bg-gradient-to-br from-[#DCFCE7]/50 to-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <CheckCircle2 className="h-4 w-4 text-[#22C55E]" />
          Why This Score?
        </h2>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="rounded-full bg-[#DCFCE7] p-4 shadow-inner">
            <CheckCircle2 className="h-10 w-10 text-[#22C55E]" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-[#22C55E]">
            No Critical Drivers Detected
          </h3>
          <p className="mt-2 max-w-md text-sm text-[#64748B]">
            Risk profile is stable. No significant anomalies or red flags were identified
            in the financial statements analysis.
          </p>
        </div>
      </div>
    );
  }

  // Normal case: Display signal contributions
  const sortedSignals = [...xaiTrace.signal_contributions].sort(
    (a, b) => b.contribution_pct - a.contribution_pct
  );

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
        <AlertTriangle className="h-4 w-4 text-[#F59E0B]" />
        Why This Score?
      </h2>

      {/* Primary Driver */}
      {xaiTrace.primary_driver && (
        <div className="mb-4 rounded-lg border border-[#F59E0B]/30 bg-[#FEF3C7]/50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-[#F59E0B]">
            Primary Driver
          </p>
          <p className="mt-1 text-sm font-medium text-[#1E293B]">
            {xaiTrace.primary_driver}
          </p>
        </div>
      )}

      {/* Signal Contributions */}
      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-[#94A3B8]">
          Signal Contributions
        </p>
        {sortedSignals.map((signal, index) => {
          const colors = severityColors[signal.severity] || severityColors.MEDIUM;
          return (
            <div
              key={index}
              className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3 transition-all hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-[#1E293B]">
                      {signal.signal_family}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}
                    >
                      {signal.severity}
                    </span>
                    {signal.year && (
                      <span className="text-xs text-[#94A3B8]">• {signal.year}</span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-[#64748B]">{signal.description}</p>
                </div>
                <span className="whitespace-nowrap text-sm font-bold text-[#1E293B]">
                  {signal.contribution_pct.toFixed(1)}%
                </span>
              </div>
              {/* Progress bar */}
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
                <div
                  className={`h-full rounded-full ${colors.bar} transition-all duration-500`}
                  style={{ width: `${Math.min(signal.contribution_pct, 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Logical Rule Triggered */}
      {xaiTrace.logical_rule_triggered && (
        <div className="mt-4 rounded-lg border border-[#DBEAFE] bg-[#EFF6FF] p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-[#3B82F6]">
            Rule Triggered
          </p>
          <p className="mt-1 text-sm text-[#1E293B]">{xaiTrace.logical_rule_triggered}</p>
        </div>
      )}

      {/* Evidence Chain */}
      {xaiTrace.evidence_chain && xaiTrace.evidence_chain.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[#94A3B8]">
            Evidence Chain
          </p>
          <div className="space-y-2">
            {xaiTrace.evidence_chain.map((evidence, index) => (
              <div
                key={index}
                className="flex items-start gap-2 rounded-lg border border-[#E2E8F0] bg-white p-2.5"
              >
                <ChevronRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#94A3B8]" />
                <p className="text-xs text-[#64748B]">{evidence}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default XAITraceSection;
