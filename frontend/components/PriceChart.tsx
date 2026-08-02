"use client";

import { useMemo, useState } from "react";
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
import type { PricePoint } from "@/lib/types";

type TF = "D" | "W" | "M";

const TF_LABEL: Record<TF, string> = { D: "일", W: "주", M: "월" };

/** 일봉을 주/월로 리샘플 (마지막 거래일 종가 + MA 재계산). */
function resample(data: PricePoint[], tf: TF): PricePoint[] {
  if (tf === "D" || data.length === 0) return data;
  const bucketKey = (d: string) => {
    const dt = new Date(d);
    if (tf === "M") return `${dt.getFullYear()}-${dt.getMonth()}`;
    // 주: ISO 주차 근사 (연 + 주번호)
    const onejan = new Date(dt.getFullYear(), 0, 1);
    const week = Math.ceil(((dt.getTime() - onejan.getTime()) / 86400000 + onejan.getDay() + 1) / 7);
    return `${dt.getFullYear()}-W${week}`;
  };
  const buckets = new Map<string, PricePoint>();
  for (const p of data) buckets.set(bucketKey(p.date), p); // 각 버킷 마지막 값 유지
  const rows = Array.from(buckets.values());

  // MA 재계산 (리샘플된 종가 기준)
  const closes = rows.map((r) => r.close);
  const ma = (i: number, w: number) => {
    if (i < w - 1) return null;
    let s = 0;
    for (let k = i - w + 1; k <= i; k++) s += closes[k];
    return s / w;
  };
  return rows.map((r, i) => ({ ...r, ma20: ma(i, Math.min(20, rows.length)) ?? r.ma20, ma60: ma(i, Math.min(10, rows.length)) ?? r.ma60 }));
}

export default function PriceChart({ data }: { data: PricePoint[] }) {
  const [tf, setTf] = useState<TF>("D");
  const series = useMemo(() => resample(data, tf), [data, tf]);

  const first = series[0]?.close ?? 0;
  const last = series[series.length - 1]?.close ?? 0;
  const up = last >= first;
  const stroke = up ? "#F04452" : "#3182F6";
  const fill = stroke;

  return (
    <section className="card">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-muted">가격 차트</p>
          <h2 className="mt-0.5 text-heading text-ink">종가 추이</h2>
        </div>
        {/* 타임프레임 토글 */}
        <div className="flex items-center rounded-xl bg-surface p-1">
          {(["D", "W", "M"] as TF[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTf(t)}
              className={`h-8 rounded-lg px-3 text-xs font-bold transition-colors ${tf === t ? "bg-card text-ink shadow-card" : "text-muted hover:text-sub"}`}
            >
              {TF_LABEL[t]}
            </button>
          ))}
          <span className="ml-1 cursor-not-allowed px-2 text-[10px] font-medium text-faint" title="분/틱은 실시간 데이터가 없어 제공하지 않습니다">분·틱 N/A</span>
        </div>
      </div>

      <div className="mb-2 flex items-center gap-3 text-xs font-bold text-muted">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: stroke }} />종가</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-toss" />MA20</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-warn" />MA60</span>
      </div>

      <div className="h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 12, right: 12, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={fill} stopOpacity={0.2} />
                <stop offset="100%" stopColor={fill} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgb(var(--c-surface))" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "rgb(var(--c-muted))" }} minTickGap={40} tickLine={false} axisLine={false} />
            <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "rgb(var(--c-muted))" }} width={64} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: "rgb(var(--c-ink))",
                border: "none",
                borderRadius: 12,
                fontSize: 12,
                color: "rgb(var(--c-bg))",
                padding: "8px 12px",
                boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
              }}
              itemStyle={{ color: "rgb(var(--c-bg))" }}
              labelStyle={{ color: "rgb(var(--c-faint))", marginBottom: 4 }}
              formatter={(value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              labelFormatter={(label) => label}
            />
            <Area type="monotone" dataKey="close" name="종가" stroke={stroke} strokeWidth={2.4} fill="url(#priceGrad)" animationDuration={500} />
            <Line type="monotone" dataKey="ma20" name="MA20" stroke="#3182F6" strokeWidth={1.6} dot={false} animationDuration={500} />
            <Line type="monotone" dataKey="ma60" name="MA60" stroke="#F59F00" strokeWidth={1.6} dot={false} animationDuration={500} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
