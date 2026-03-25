interface DualRiskMatrixProps {
  manipulationScore?: number;
  stressScore?: number;
}

const DualRiskMatrix = ({ manipulationScore = 50, stressScore = 50 }: DualRiskMatrixProps) => {
  // Calculate position (0-100 scale to percentage)
  const xPos = Math.min(Math.max(manipulationScore, 0), 100);
  const yPos = Math.min(Math.max(100 - stressScore, 0), 100); // Invert Y axis

  // Determine quadrant
  const getQuadrant = () => {
    if (manipulationScore < 50 && stressScore < 50) return "Healthy";
    if (manipulationScore < 50 && stressScore >= 50) return "Stressed";
    if (manipulationScore >= 50 && stressScore < 50) return "Suspicious";
    return "Critical";
  };

  const quadrant = getQuadrant();

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[#64748B]">
        Dual Risk Matrix
      </h2>
      
      <div className="relative aspect-square w-full">
        {/* Background Grid */}
        <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 overflow-hidden rounded-lg">
          {/* Healthy - Bottom Left */}
          <div className="border-b border-r border-[#E2E8F0] bg-[#DCFCE7]/50 flex items-end justify-start p-2">
            <span className="text-xs font-medium text-[#22C55E]/70">Healthy</span>
          </div>
          {/* Suspicious - Bottom Right */}
          <div className="border-b border-[#E2E8F0] bg-[#FEE2E2]/50 flex items-end justify-end p-2">
            <span className="text-xs font-medium text-[#EF4444]/70">Suspicious</span>
          </div>
          {/* Stressed - Top Left */}
          <div className="border-r border-[#E2E8F0] bg-[#FEF3C7]/50 flex items-start justify-start p-2">
            <span className="text-xs font-medium text-[#F59E0B]/70">Stressed</span>
          </div>
          {/* Critical - Top Right */}
          <div className="bg-[#FEE2E2]/70 flex items-start justify-end p-2">
            <span className="text-xs font-medium text-[#EF4444]/70">Critical</span>
          </div>
        </div>

        {/* Axis Labels */}
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs font-medium text-[#64748B]">
          Manipulation Risk →
        </div>
        <div className="absolute -left-6 top-1/2 -translate-y-1/2 -rotate-90 text-xs font-medium text-[#64748B]">
          Stress Risk →
        </div>

        {/* Current Position Marker */}
        <div
          className="absolute z-10 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-3 border-white bg-[#3B82F6] shadow-lg shadow-[#3B82F6]/40 transition-all duration-500"
          style={{
            left: `${xPos}%`,
            top: `${yPos}%`,
          }}
        >
          {/* Pulse animation */}
          <div className="absolute inset-0 animate-ping rounded-full bg-[#3B82F6] opacity-50" />
        </div>

        {/* Grid lines */}
        <div className="absolute left-1/2 top-0 h-full w-px bg-[#E2E8F0]" />
        <div className="absolute left-0 top-1/2 h-px w-full bg-[#E2E8F0]" />
      </div>

      {/* Legend */}
      <div className="mt-8 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-[#3B82F6] shadow-sm" />
          <span className="text-sm text-[#64748B]">Current Position</span>
        </div>
        <span className={`rounded-lg px-3 py-1 text-sm font-semibold ${
          quadrant === "Healthy" ? "bg-[#DCFCE7] text-[#22C55E]" :
          quadrant === "Stressed" ? "bg-[#FEF3C7] text-[#F59E0B]" :
          quadrant === "Suspicious" ? "bg-[#FFEDD5] text-[#F97316]" :
          "bg-[#FEE2E2] text-[#EF4444]"
        }`}>
          {quadrant}
        </span>
      </div>

      {/* Score Display */}
      <div className="mt-4 grid grid-cols-2 gap-4 border-t border-[#E2E8F0] pt-4">
        <div>
          <p className="text-xs text-[#94A3B8]">Manipulation Score</p>
          <p className="text-lg font-bold text-[#1E293B]">{manipulationScore.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-xs text-[#94A3B8]">Stress Score</p>
          <p className="text-lg font-bold text-[#1E293B]">{stressScore.toFixed(1)}</p>
        </div>
      </div>
    </div>
  );
};

export default DualRiskMatrix;
