"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BacktestPoint } from "@/lib/types";

export default function BacktestChart({ data }: { data: BacktestPoint[] }) {
  return (
    <section className="card">
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">백테스트</p>
          <h2 className="mt-0.5 text-heading text-ink">누적 수익률 비교</h2>
        </div>
        <div className="flex items-center gap-3 text-xs font-bold text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-toss" />
            신호 전략
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-warn" />
            보유 전략
          </span>
        </div>
      </div>

      <div className="h-[380px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 12, right: 12, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="stratGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3182F6" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#3182F6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgb(var(--c-surface))" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "rgb(var(--c-muted))" }}
              minTickGap={40}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "rgb(var(--c-muted))" }}
              width={56}
              unit="%"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "rgb(var(--c-ink))",
                border: "none",
                borderRadius: 12,
                fontSize: 12,
                padding: "8px 12px",
                color: "rgb(var(--c-bg))",
              }}
              itemStyle={{ color: "rgb(var(--c-bg))" }}
              labelStyle={{ color: "rgb(var(--c-faint))", marginBottom: 4 }}
              formatter={(value: number) => `${value.toFixed(2)}%`}
            />
            <Area
              type="monotone"
              dataKey="cumulative_return"
              name="신호 전략"
              stroke="#3182F6"
              strokeWidth={2.4}
              fill="url(#stratGrad)"
            />
            <Line
              type="monotone"
              dataKey="hold_return"
              name="보유 전략"
              stroke="#F59F00"
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
