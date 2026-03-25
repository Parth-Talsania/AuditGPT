import { Activity } from "lucide-react";

const DashboardHeader = () => {
  return (
    <header className="border-b border-[#334155] bg-[#1e293b] px-6 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#3b82f6]">
            <Activity className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#f8fafc]">AuditGPT</h1>
            <p className="text-xs text-[#64748b]">Financial Statement Forensics Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="rounded-full bg-[#22c55e]/20 px-3 py-1 text-xs font-medium text-[#22c55e]">
            v2.0
          </span>
        </div>
      </div>
    </header>
  );
};

export default DashboardHeader;
