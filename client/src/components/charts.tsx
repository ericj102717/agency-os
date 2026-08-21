import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Cell as PieCell, Legend, RadialBarChart, RadialBar,
} from "recharts";
import type { FunnelStage, ProductMixItem } from "@shared/types";

// ---- FunnelChart ----
export function FunnelChart({ data, height = 220 }: { data: FunnelStage[]; height?: number }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const colors = ["#0d7490", "#0891b2", "#06b6d4", "#22d3ee", "#67e8f9", "#a5f3fc", "#cffafe"];

  return (
    <div className="space-y-2" style={{ minHeight: height }}>
      {data.map((stage, i) => {
        const width = (stage.count / max) * 100;
        return (
          <div key={i} className="flex items-center gap-3">
            <div className="w-32 sm:w-40 text-xs text-muted-foreground truncate shrink-0">{stage.label}</div>
            <div className="flex-1 relative">
              <div
                className="h-8 rounded-md flex items-center justify-end pr-2 transition-all"
                style={{
                  width: `${Math.max(width, 5)}%`,
                  backgroundColor: colors[i % colors.length],
                }}
              >
                <span className="text-xs font-semibold text-white">{stage.count}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---- DonutBreakdown ----
export function DonutBreakdown({
  data,
  height = 180,
  colors = ["#0d7490", "#0891b2", "#06b6d4", "#22d3ee", "#67e8f9", "#94a3b8"],
}: {
  data: Array<{ label: string; count: number }>;
  height?: number;
  colors?: string[];
}) {
  const chartData = data.filter((d) => d.count > 0);
  if (chartData.length === 0) {
    return <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }}>No data</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="count"
          nameKey="label"
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={70}
          paddingAngle={2}
        >
          {chartData.map((_, i) => (
            <PieCell key={i} fill={colors[i % colors.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--background))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "11px" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ---- MetricBarList ----
export function MetricBarList({
  data,
  height = 200,
  color = "#0d7490",
  formatValue,
}: {
  data: Array<{ label: string; count: number; color?: string }>;
  height?: number;
  color?: string;
  formatValue?: (v: number) => string;
}) {
  const chartData = data.map((d) => ({ ...d, color: d.color || color }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={120}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--background))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
          formatter={(v: number) => formatValue ? formatValue(v) : v}
        />
        <Bar dataKey="count" radius={[4, 4, 4, 4]}>
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.color || color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---- ProductMixDonut ----
export function ProductMixDonut({ data, height = 180 }: { data: ProductMixItem[]; height?: number }) {
  return (
    <DonutBreakdown
      data={data}
      height={height}
      colors={["#0d7490", "#0891b2", "#06b6d4", "#22d3ee", "#67e8f9", "#94a3b8"]}
    />
  );
}

// ---- GaugeChart ----
export function GaugeChart({ value, max = 100, height = 120 }: { value: number; max?: number; height?: number }) {
  const pct = Math.min(value / max, 1);
  const angle = 180 * pct;
  const color = pct > 0.8 ? "#059669" : pct > 0.5 ? "#0d7490" : "#d97706";

  return (
    <div className="flex flex-col items-center justify-center" style={{ height }}>
      <svg viewBox="0 0 200 100" className="w-full" style={{ maxHeight: height }}>
        <path d="M 20 90 A 80 80 0 0 1 180 90" fill="none" stroke="hsl(var(--muted))" strokeWidth="12" strokeLinecap="round" />
        <path
          d="M 20 90 A 80 80 0 0 1 180 90"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${angle * 1.4} 999`}
        />
      </svg>
      <div className="text-2xl font-bold" style={{ color }}>{value}%</div>
    </div>
  );
}
