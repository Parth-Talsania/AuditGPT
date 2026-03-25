import { CheckCircle2, XCircle, Database, Info } from "lucide-react";

interface DataAvailabilityPanelProps {
  missingData: Record<string, boolean> | string[] | null;
}

const dataLabels: Record<string, string> = {
  annual_report_pdf: "Annual Report PDF",
  auditor_notes: "Auditor Notes",
  financial_statements: "Financial Statements",
  peer_data: "Peer Comparison Data",
  historical_ratios: "Historical Ratios",
  sector_benchmarks: "Sector Benchmarks",
  management_discussion: "Management Discussion",
  related_party_notes: "Related Party Notes",
  cash_flow_statement: "Cash Flow Statement",
  balance_sheet: "Balance Sheet",
  income_statement: "Income Statement",
  quarterly_data: "Quarterly Data",
  segment_data: "Segment Data",
  auditor_sentiment: "Auditor Sentiment",
  rpt_data: "Related Party Transactions",
};

const DataAvailabilityPanel = ({ missingData }: DataAvailabilityPanelProps) => {
  // Handle null or empty data
  if (!missingData) {
    return (
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <Database className="h-4 w-4" />
          Data Availability
        </h2>
        <div className="flex items-center justify-center py-6 text-center">
          <Info className="mr-2 h-5 w-5 text-[#94A3B8]" />
          <p className="text-sm text-[#64748B]">
            Data availability information not provided.
          </p>
        </div>
      </div>
    );
  }

  // Convert array format to object format if needed
  let dataStatus: Record<string, boolean>;

  if (Array.isArray(missingData)) {
    // If it's an array, these are the missing items (false = missing)
    const allKeys = Object.keys(dataLabels);
    dataStatus = {};
    allKeys.forEach((key) => {
      // If the key is in the missing array, it's missing (false)
      dataStatus[key] = !missingData.some(
        (item) => item.toLowerCase().replace(/\s+/g, "_") === key || item === key
      );
    });
    // Also add any items from the array that aren't in our predefined labels
    missingData.forEach((item) => {
      const normalizedKey = item.toLowerCase().replace(/\s+/g, "_");
      if (!(normalizedKey in dataStatus)) {
        dataStatus[normalizedKey] = false;
      }
    });
  } else {
    dataStatus = missingData;
  }

  const entries = Object.entries(dataStatus);
  const availableCount = entries.filter(([, available]) => available).length;
  const missingCount = entries.filter(([, available]) => !available).length;

  // Calculate availability percentage
  const availabilityPct = entries.length > 0 
    ? (availableCount / entries.length) * 100 
    : 0;

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
          <Database className="h-4 w-4" />
          Data Availability
        </h2>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            availabilityPct >= 80
              ? "bg-[#DCFCE7] text-[#22C55E]"
              : availabilityPct >= 50
                ? "bg-[#FEF3C7] text-[#F59E0B]"
                : "bg-[#FEE2E2] text-[#EF4444]"
          }`}
        >
          {availabilityPct.toFixed(0)}% Complete
        </span>
      </div>

      {/* Progress Bar */}
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            availabilityPct >= 80
              ? "bg-[#22C55E]"
              : availabilityPct >= 50
                ? "bg-[#F59E0B]"
                : "bg-[#EF4444]"
          }`}
          style={{ width: `${availabilityPct}%` }}
        />
      </div>

      {/* Summary */}
      <div className="mb-4 flex items-center justify-center gap-6 rounded-lg bg-[#F8FAFC] p-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-[#22C55E]" />
          <span className="text-sm font-medium text-[#1E293B]">
            {availableCount} Available
          </span>
        </div>
        <div className="h-4 w-px bg-[#E2E8F0]" />
        <div className="flex items-center gap-2">
          <XCircle className="h-5 w-5 text-[#94A3B8]" />
          <span className="text-sm font-medium text-[#1E293B]">
            {missingCount} Missing
          </span>
        </div>
      </div>

      {/* Data Grid */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([key, isAvailable], index) => {
          const label = dataLabels[key] || key.replace(/_/g, " ");
          return (
            <div
              key={index}
              className={`flex items-center gap-2 rounded-lg border p-2.5 transition-all ${
                isAvailable
                  ? "border-[#DCFCE7] bg-[#F0FDF4]"
                  : "border-[#E2E8F0] bg-[#F8FAFC]"
              }`}
            >
              {isAvailable ? (
                <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-[#22C55E]" />
              ) : (
                <XCircle className="h-4 w-4 flex-shrink-0 text-[#94A3B8]" />
              )}
              <span
                className={`truncate text-sm capitalize ${
                  isAvailable ? "text-[#1E293B]" : "text-[#94A3B8]"
                }`}
                title={label}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Warning for critical missing data */}
      {missingCount > 0 && (
        <div className="mt-4 rounded-lg border border-[#F59E0B]/30 bg-[#FEF3C7]/50 p-3">
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#F59E0B]" />
            <div>
              <p className="text-xs font-medium text-[#F59E0B]">
                Analysis Limitations
              </p>
              <p className="mt-1 text-xs text-[#92400E]">
                Some data sources are unavailable. This may affect the accuracy of
                certain risk signals. Consider uploading the annual report PDF for
                a more comprehensive analysis.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataAvailabilityPanel;
