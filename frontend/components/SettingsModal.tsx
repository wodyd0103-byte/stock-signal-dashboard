"use client";

import { ExternalLink, ShieldAlert, X } from "lucide-react";

const disclaimer =
  "본 도구의 분석·예측·신호는 과거 데이터 기반 알고리즘 참고 정보입니다. 실거래는 외부 증권사 앱에서 수행하며, 모든 투자 판단과 책임은 본인에게 있습니다.";

export default function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg rounded-card bg-bg p-6 shadow-cardHover">
        <div className="flex items-start justify-between">
          <h2 className="text-heading text-ink">정보 · 설정</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted hover:bg-surface"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-4 space-y-3">
          <div className="rounded-xl bg-surface p-4">
            <p className="text-xs font-semibold text-muted">데이터 제공자</p>
            <p className="mt-1 text-sm font-bold text-ink">
              국내: FinanceDataReader · 해외: yfinance
            </p>
            <p className="mt-1 text-xs text-sub">
              수급·뉴스: 네이버금융 크롤링 · 공포탐욕: VIX/KOSPI/환율 자체 산출
            </p>
          </div>

          <div className="rounded-xl bg-toss-50 p-4">
            <p className="text-sm font-bold text-toss-700">외부 매매 앱 워크플로</p>
            <p className="mt-1 text-sm leading-6 text-toss-700/85">
              이 도구는 분석 전용입니다. 실제 매매는 외부 증권사 앱에서 수행하세요. 분석 결과는
              CSV로 내보낼 수 있습니다.
            </p>
            <a
              href="https://www.tossinvest.com"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm font-bold text-toss hover:underline"
            >
              토스증권 열기 <ExternalLink size={14} />
            </a>
          </div>

          <div className="rounded-xl bg-warnBg/60 p-4">
            <div className="flex items-start gap-2">
              <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warn" />
              <p className="text-sm leading-6 text-warn/90">{disclaimer}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
