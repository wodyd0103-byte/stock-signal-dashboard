"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import SignalGuide from "@/components/SignalGuide";

/** 신호 기준 안내 — 접이식 래퍼 (기본 닫힘). */
export default function IndicatorGuideInline() {
  const [open, setOpen] = useState(false);
  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-card bg-surface px-5 py-3.5 text-left transition-colors hover:bg-surface2"
      >
        <span className="text-sm font-bold text-ink">신호 점수 기준이 궁금하세요?</span>
        {open ? <ChevronUp size={16} className="text-muted" /> : <ChevronDown size={16} className="text-muted" />}
      </button>
      {open ? <div className="mt-3"><SignalGuide /></div> : null}
    </section>
  );
}
