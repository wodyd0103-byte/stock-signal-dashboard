"use client";

import { useImperativeHandle, forwardRef } from "react";
import { Star, Trash2 } from "lucide-react";
import { useWatchlist } from "@/hooks/queries";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { deleteWatchlist } from "@/lib/api";
import type { Signal } from "@/lib/types";

const signalChip: Record<Signal, string> = {
  "STRONG BUY": "bg-upStrong text-white",
  BUY: "bg-upStrong text-white",
  "WEAK BUY": "bg-up/15 text-up",
  HOLD: "bg-surface text-sub",
  "WEAK SELL": "bg-down/15 text-down",
  SELL: "bg-downStrong text-white",
  "STRONG SELL": "bg-downStrong text-white",
};

export interface WatchlistRailHandle {
  reload: () => void;
}

interface Props {
  onSelect: (t: string) => void;
  selected?: string;
}

const WatchlistRail = forwardRef<WatchlistRailHandle, Props>(({ onSelect, selected }, ref) => {
  // 오류는 화면에 띄우지 않는다. 관심종목이 비었거나 백엔드가 안 떠 있는 것이
  // 대부분이고, 그때는 아래 빈 목록 문구로 충분하다.
  const { data, loading, refetch } = useWatchlist();
  const items = data ?? [];

  // 종목을 관심목록에 추가하는 버튼은 page.tsx에 있다. 추가 후 이 목록을
  // 새로 고치라고 알리는 통로.
  useImperativeHandle(ref, () => ({ reload: refetch }), [refetch]);

  const removeHolding = useAsyncAction(deleteWatchlist);

  async function remove(ticker: string, e: React.MouseEvent) {
    e.stopPropagation();
    await removeHolding.run(ticker);
    refetch();
  }

  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center gap-1.5 px-1">
        <Star size={15} className="text-toss" />
        <h3 className="text-sm font-bold text-ink">관심 종목</h3>
        <span className="ml-auto text-xs text-muted">{items.length}</span>
      </div>

      {loading && items.length === 0 ? (
        <div className="space-y-1">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-11 animate-pulse rounded-xl bg-surface" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="px-2 py-4 text-center text-xs text-muted">
          관심 종목 없음.
          <br />
          분석 후 &apos;관심&apos; 버튼으로 추가.
        </p>
      ) : (
        <div className="space-y-1">
          {items.map((it) => {
            const up = (it.change_rate ?? 0) >= 0;
            return (
              <div
                key={it.id}
                onClick={() => onSelect(it.ticker)}
                className={`group flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 transition-colors ${selected === it.ticker ? "bg-toss-50 ring-1 ring-toss/30" : "hover:bg-surface"}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-ink">{it.name || it.ticker}</p>
                  <p className="text-[10px] text-muted">
                    {it.ticker}
                    {it.change_rate != null ? (
                      <>
                        {" "}
                        ·{" "}
                        <span className={up ? "text-up" : "text-down"}>
                          {up ? "+" : ""}
                          {it.change_rate.toFixed(2)}%
                        </span>
                      </>
                    ) : null}
                  </p>
                </div>
                {it.signal ? (
                  <span className={`chip text-[10px] px-1.5 py-0.5 ${signalChip[it.signal]}`}>
                    {it.signal}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={(e) => void remove(it.ticker, e)}
                  className="rounded-lg p-1.5 text-faint opacity-0 transition-opacity hover:bg-down/10 hover:text-down group-hover:opacity-100"
                  aria-label="삭제"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

WatchlistRail.displayName = "WatchlistRail";
export default WatchlistRail;
