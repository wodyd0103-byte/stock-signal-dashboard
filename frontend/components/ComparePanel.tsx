"use client";

import { useState, type ReactNode } from "react";
import { GitCompareArrows } from "lucide-react";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { fetchCompare } from "@/lib/api";
import type { CompareItem, CompareResponse } from "@/lib/types";

const signalChip: Record<string, string> = {
  "STRONG BUY": "bg-upStrong text-white",
  BUY: "bg-upStrong text-white",
  "WEAK BUY": "bg-up/15 text-up",
  HOLD: "bg-surface2 text-sub",
  "WEAK SELL": "bg-down/15 text-down",
  SELL: "bg-downStrong text-white",
  "STRONG SELL": "bg-downStrong text-white",
};

function pct(v?: number | null) {
  return v == null ? "-" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}
function pctTone(v?: number | null) {
  if (v == null) return "text-faint";
  return v >= 0 ? "text-up" : "text-down";
}

export default function ComparePanel({
  currentTicker,
  onSelect,
}: {
  currentTicker?: string;
  onSelect?: (t: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState(currentTicker ?? "");
  const [data, setData] = useState<CompareResponse | null>(null);
  // 입력이 틀렸을 때의 메시지. 요청 자체의 실패는 compare.error가 들고 있다.
  const [inputError, setInputError] = useState<string | null>(null);

  const compare = useAsyncAction(fetchCompare, { fallbackMessage: "비교 실패" });
  const loading = compare.pending;
  // 200으로 오면서 본문에 error를 담아 오는 경우가 있어 셋을 같이 본다.
  const err = inputError ?? compare.error ?? data?.error ?? null;

  async function run() {
    const tickers = input
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    if (tickers.length < 2) {
      setInputError("종목 2~4개를 쉼표로 구분해 입력하세요. 예: 005930, 000660");
      return;
    }
    setInputError(null);
    const res = await compare.run(tickers.slice(0, 4));
    if (res) setData(res);
  }

  const valid = (data?.items ?? []).filter((i) => !i.error);

  return (
    <section className="card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <GitCompareArrows size={18} className="text-toss" />
        <div className="flex-1">
          <p className="text-xs font-semibold text-muted">종목 비교</p>
          <h2 className="mt-0.5 text-heading text-ink">2~4종목 나란히 보기</h2>
        </div>
        <span className="text-xs font-bold text-muted">{open ? "접기" : "펼치기"}</span>
      </button>

      {open ? (
        <div className="mt-4">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void run();
              }}
              aria-label="비교할 종목 (쉼표로 구분)"
              placeholder="005930, 000660, 035420"
              className="h-11 flex-1 rounded-xl bg-surface px-3 text-sm font-semibold text-ink placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50"
            />
            <button
              type="button"
              onClick={() => void run()}
              className="inline-flex h-11 items-center gap-1.5 rounded-xl bg-tossStrong px-4 text-sm font-bold text-white hover:bg-toss-600"
            >
              {loading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <GitCompareArrows size={15} />
              )}
              비교
            </button>
          </div>
          {err ? (
            <p role="alert" className="mt-2 text-xs text-down">
              {err}
            </p>
          ) : null}

          {valid.length >= 2 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b border-line">
                    <th className="py-2 text-left text-[11px] font-bold text-muted">지표</th>
                    {valid.map((it) => (
                      <th key={it.ticker} className="px-2 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => onSelect?.(it.ticker)}
                          className="font-extrabold text-ink hover:text-toss"
                        >
                          {it.ticker}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <Row
                    label="현재가"
                    items={valid}
                    render={(i) => (
                      <span className="font-bold text-ink tabular">
                        {i.current_price?.toLocaleString() ?? "-"}
                      </span>
                    )}
                  />
                  <Row
                    label="등락률"
                    items={valid}
                    render={(i) => (
                      <span className={`font-bold tabular ${pctTone(i.change_rate)}`}>
                        {pct(i.change_rate)}
                      </span>
                    )}
                  />
                  <Row
                    label="20일 수익"
                    items={valid}
                    best={argbest(valid, (i) => i.return_20d)}
                    render={(i) => (
                      <span className={`font-bold tabular ${pctTone(i.return_20d)}`}>
                        {pct(i.return_20d)}
                      </span>
                    )}
                  />
                  <Row
                    label="60일 수익"
                    items={valid}
                    best={argbest(valid, (i) => i.return_60d)}
                    render={(i) => (
                      <span className={`font-bold tabular ${pctTone(i.return_60d)}`}>
                        {pct(i.return_60d)}
                      </span>
                    )}
                  />
                  <Row
                    label="변동성(연)"
                    items={valid}
                    best={argbest(valid, (i) => (i.volatility == null ? null : -i.volatility))}
                    render={(i) => (
                      <span className="tabular text-sub">
                        {i.volatility == null ? "-" : `${i.volatility}%`}
                      </span>
                    )}
                  />
                  <Row
                    label="신호"
                    items={valid}
                    render={(i) => (
                      <span
                        className={`chip text-[10px] px-1.5 py-0.5 ${signalChip[i.signal ?? "HOLD"] ?? signalChip.HOLD}`}
                      >
                        {i.signal ?? "-"}
                      </span>
                    )}
                  />
                  <Row
                    label="매수점수"
                    items={valid}
                    best={argbest(valid, (i) => i.buy_score ?? null)}
                    render={(i) => (
                      <span className="font-bold tabular text-ink">{i.buy_score ?? "-"}</span>
                    )}
                  />
                  <Row
                    label="리스크"
                    items={valid}
                    best={argbest(valid, (i) => (i.risk_score == null ? null : -i.risk_score))}
                    render={(i) => <span className="tabular text-sub">{i.risk_score ?? "-"}</span>}
                  />
                  <Row
                    label="PER"
                    items={valid}
                    render={(i) => (
                      <span className="tabular text-sub">
                        {i.per == null ? "-" : `${i.per.toFixed(1)}배`}
                      </span>
                    )}
                  />
                  <Row
                    label="PBR"
                    items={valid}
                    render={(i) => (
                      <span className="tabular text-sub">
                        {i.pbr == null ? "-" : `${i.pbr.toFixed(2)}배`}
                      </span>
                    )}
                  />
                </tbody>
              </table>
              {data?.items.some((i) => i.error) ? (
                <p className="mt-2 text-[11px] text-down">
                  실패:{" "}
                  {data.items
                    .filter((i) => i.error)
                    .map((i) => `${i.ticker}(${i.error})`)
                    .join(", ")}
                </p>
              ) : null}
              <p className="mt-2 text-[10px] leading-4 text-muted">
                초록 강조 = 항목별 우위. 신호·점수는 알고리즘 참고치이며 수익을 보장하지 않습니다.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** 행 렌더. best = 강조할 ticker (없으면 무강조). */
function Row({
  label,
  items,
  render,
  best,
}: {
  label: string;
  items: CompareItem[];
  render: (i: CompareItem) => ReactNode;
  best?: string | null;
}) {
  return (
    <tr className="border-b border-line/60">
      <td className="py-2 text-[11px] font-semibold text-muted">{label}</td>
      {items.map((i) => (
        <td
          key={i.ticker}
          className={`px-2 py-2 text-right ${best && i.ticker === best ? "rounded-md bg-up/10" : ""}`}
        >
          {render(i)}
        </td>
      ))}
    </tr>
  );
}

/** 최대값 ticker 반환 (null 제외). 동률·전부 null이면 null. */
function argbest(
  items: CompareItem[],
  getter: (i: CompareItem) => number | null | undefined,
): string | null {
  let best: string | null = null;
  let bestVal = -Infinity;
  for (const i of items) {
    const v = getter(i);
    if (v == null || Number.isNaN(v)) continue;
    if (v > bestVal) {
      bestVal = v;
      best = i.ticker;
    }
  }
  return best;
}
