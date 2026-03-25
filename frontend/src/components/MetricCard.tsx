import { useState, useEffect, useRef } from "react";
import type { ReactNode } from "react";

interface MetricCardProps {
  title: string;
  value: number;
  maxValue: number;
  severity: "low" | "medium" | "high" | "critical";
  label: string;
  icon: ReactNode;
}

const severityColors = {
  low: {
    bg: "bg-[#DCFCE7]",
    text: "text-[#22C55E]",
    bar: "bg-[#22C55E]",
    iconBg: "bg-[#DCFCE7]",
    glow: "shadow-[#22C55E]/20",
  },
  medium: {
    bg: "bg-[#FEF3C7]",
    text: "text-[#F59E0B]",
    bar: "bg-[#F59E0B]",
    iconBg: "bg-[#FEF3C7]",
    glow: "shadow-[#F59E0B]/20",
  },
  high: {
    bg: "bg-[#FFEDD5]",
    text: "text-[#F97316]",
    bar: "bg-[#F97316]",
    iconBg: "bg-[#FFEDD5]",
    glow: "shadow-[#F97316]/20",
  },
  critical: {
    bg: "bg-[#FEE2E2]",
    text: "text-[#EF4444]",
    bar: "bg-[#EF4444]",
    iconBg: "bg-[#FEE2E2]",
    glow: "shadow-[#EF4444]/20",
  },
};

/**
 * Custom hook for animated counting
 */
const useCountUp = (target: number, duration: number = 1500, startDelay: number = 100) => {
  const [count, setCount] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    // Reset on target change
    setCount(0);
    startTimeRef.current = null;

    const startAnimation = () => {
      const animate = (currentTime: number) => {
        if (startTimeRef.current === null) {
          startTimeRef.current = currentTime;
        }

        const elapsed = currentTime - startTimeRef.current;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function: cubic-bezier(0.4, 0, 0.2, 1) approximation
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        
        const currentValue = easeOutQuart * target;
        setCount(currentValue);

        if (progress < 1) {
          animationFrameRef.current = requestAnimationFrame(animate);
        } else {
          setCount(target);
        }
      };

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    // Start with a small delay for staggered effect
    const timeoutId = setTimeout(startAnimation, startDelay);

    return () => {
      clearTimeout(timeoutId);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [target, duration, startDelay]);

  return count;
};

const MetricCard = ({ title, value, maxValue, severity, label, icon }: MetricCardProps) => {
  const colors = severityColors[severity];
  const targetPercentage = Math.min((value / maxValue) * 100, 100);
  
  // Animated values
  const animatedValue = useCountUp(value, 1500, 100);
  const [barWidth, setBarWidth] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Trigger animation after mount
    const timer = setTimeout(() => {
      setIsVisible(true);
      setBarWidth(targetPercentage);
    }, 100);

    return () => clearTimeout(timer);
  }, [targetPercentage]);

  // Reset animation when value changes
  useEffect(() => {
    setBarWidth(0);
    setIsVisible(false);
    
    const timer = setTimeout(() => {
      setIsVisible(true);
      setBarWidth(targetPercentage);
    }, 100);

    return () => clearTimeout(timer);
  }, [value, targetPercentage]);

  return (
    <div className={`rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-lg transition-all duration-300 hover:shadow-xl ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`rounded-lg p-2 ${colors.iconBg} ${colors.text} transition-transform duration-300 ${isVisible ? 'scale-100' : 'scale-90'}`}>
            {icon}
          </div>
          <span className="text-sm font-medium text-[#64748B]">{title}</span>
        </div>
        <span className={`rounded-lg px-2 py-1 text-xs font-semibold ${colors.bg} ${colors.text} transition-all duration-500 ${isVisible ? 'opacity-100' : 'opacity-0'}`}>
          {label}
        </span>
      </div>
      
      <div className="mt-4">
        <div className="flex items-baseline gap-1">
          <span className={`text-3xl font-bold tabular-nums ${colors.text}`}>
            {animatedValue.toFixed(1)}
          </span>
          <span className="text-sm text-[#94A3B8]">/ {maxValue}</span>
        </div>
      </div>

      <div className="mt-3">
        <div className="relative h-3 overflow-hidden rounded-full bg-[#F1F5F9]">
          {/* Animated progress bar */}
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${colors.bar} shadow-lg ${colors.glow}`}
            style={{
              width: `${barWidth}%`,
              transition: 'width 1.5s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
          {/* Shimmer effect */}
          <div
            className={`absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-transparent via-white/30 to-transparent ${isVisible ? 'animate-shimmer' : ''}`}
            style={{
              width: `${barWidth}%`,
              transition: 'width 1.5s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        </div>
      </div>

      {/* Percentage indicator */}
      <div className="mt-2 flex justify-end">
        <span className={`text-xs font-medium ${colors.text} tabular-nums`}>
          {animatedValue.toFixed(1)}%
        </span>
      </div>
    </div>
  );
};

export default MetricCard;
