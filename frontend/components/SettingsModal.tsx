"use client";

import { useEffect, useId, useRef } from "react";
import { ExternalLink, ShieldAlert, X } from "lucide-react";

const disclaimer =
  "본 도구의 분석·예측·신호는 과거 데이터 기반 알고리즘 참고 정보입니다. 실거래는 외부 증권사 앱에서 수행하며, 모든 투자 판단과 책임은 본인에게 있습니다.";

/** 포커스를 받을 수 있는 것들. disabled 와 tabindex=-1 은 순회에서 뺀다. */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    // 열기 직전에 포커스가 있던 곳. 닫을 때 여기로 돌려보내지 않으면 키보드
    // 사용자는 문서 맨 처음부터 다시 Tab 해야 한다.
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      // 포커스 트랩. 없으면 Tab 이 대화상자 밖(뒤에 깔린 페이지)으로 새어나가
      // 화면에 보이지도 않는 것에 포커스가 간다.
      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 바깥 클릭으로 닫기. 키보드에는 Escape 와 닫기 버튼이 있으므로 이 요소
          자체를 포커스 대상으로 만들지 않는다(트랩 안에 빈 정거장이 생긴다). */}
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative z-10 w-full max-w-lg rounded-card bg-bg p-6 shadow-cardHover outline-none"
      >
        <div className="flex items-start justify-between">
          <h2 id={titleId} className="text-heading text-ink">
            정보 · 설정
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="설정 닫기"
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
