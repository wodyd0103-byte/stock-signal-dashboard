import { ArrowUpRight, CalendarClock, Target, TrendingUp } from "lucide-react";
import type { HorizonPrediction, OptimalExit, PriceTarget } from "@/lib/types";

interface Props {
  currentPrice: number;
  longTerm?: HorizonPrediction[];
  optimalExit?: OptimalExit | null;
  priceTarget?: PriceTarget | null;
}

export default function PriceTargetCard({ currentPrice, longTerm, optimalExit, priceTarget }: Props) {
  if (!optimalExit && !priceTarget && (!longTerm || longTerm.length === 0)) {
    return null;
  }

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {/* 최적 매도 시점 */}
      {optimalExit ? (
        <ExitCard exit={optimalExit} currentPrice={currentPrice} />
      ) : null}

      {/* 장기 목표가 */}
      {priceTarget ? (
        <TargetCard target={priceTarget} />
      ) : null}

      {/* 장기 예측 행 (full width) */}
      {longTerm && longTerm.length > 0 ? (
        <div className="card lg:col-span-2">
          <div className="mb-4 flex items-baseline justify-between">
            <div>
              <p className="text-xs font-semibold text-muted">장기 예측</p>
              <h2 className="mt-0.5 text-heading text-ink">3개월 · 6개월 후 가격</h2>
            </div>
            <span className="text-xs font-medium text-muted">Walk-forward 검증</span>
          </div>
          {/* 좁을 때 2열이면 예상 가격 숫자가 칸을 넘어 옆 칸과 겹친다. */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {longTerm.map((p) => {
              const up = p.expected_return_pct >= 0;
              return (
                <div key={p.horizon_days} className="rounded-xl bg-surface p-4">
                  <div className="flex items-baseline justify-between">
                    <p className="text-sm font-bold text-sub">
                      {p.horizon_days === 60 ? "약 3개월 후" : p.horizon_days === 120 ? "약 6개월 후" : `${p.horizon_days}일 후`}
                    </p>
                    <p className={`text-sm font-bold tabular ${up ? "text-up" : "text-down"}`}>
                      {up ? "+" : ""}{p.expected_return_pct.toFixed(2)}%
                    </p>
                  </div>
                  <p className="mt-2 text-2xl font-extrabold text-ink tabular">
                    {p.predicted_price.toLocaleString()}
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg">
                      <div className="h-1.5 rounded-full bg-toss" style={{ width: `${p.confidence_score}%` }} />
                    </div>
                    <span className="text-xs font-bold text-muted tabular">신뢰 {p.confidence_score}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ExitCard({ exit, currentPrice }: { exit: OptimalExit; currentPrice: number }) {
  const up = exit.expected_return_pct >= 0;
  return (
    <div className="card bg-gradient-to-br from-toss-50 to-bg">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-toss text-white">
          <CalendarClock size={16} />
        </div>
        <div>
          <p className="text-xs font-bold text-toss-600">권장 매도 시점</p>
          <p className="text-[10px] text-muted">위험 조정 기대수익 최대 horizon</p>
        </div>
      </div>

      <div className="mt-5 flex items-baseline gap-2">
        <p className="text-display font-extrabold text-toss-700 tabular leading-none">
          {exit.horizon_days}
        </p>
        <span className="text-base font-bold text-toss-600">일 뒤</span>
      </div>
      <p className="mt-1 text-sm font-semibold text-sub">{exit.horizon_label}</p>

      <div className="mt-5 rounded-xl bg-bg p-4">
        <div className="flex items-baseline justify-between">
          <p className="text-xs font-bold text-muted">예상 가격</p>
          <p className={`text-xs font-bold tabular ${up ? "text-up" : "text-down"}`}>
            {up ? "+" : ""}{exit.expected_return_pct.toFixed(2)}%
          </p>
        </div>
        <p className="mt-1 text-2xl font-extrabold text-ink tabular">
          {exit.target_price.toLocaleString()}
          <span className="ml-2 text-xs font-medium text-muted">원</span>
        </p>
        <p className="mt-1 text-xs text-muted tabular">
          현재가 {currentPrice.toLocaleString()} → 목표 {exit.target_price.toLocaleString()}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg">
          <div className="h-1.5 rounded-full bg-toss" style={{ width: `${exit.confidence_score}%` }} />
        </div>
        <span className="text-xs font-bold text-muted tabular">신뢰 {exit.confidence_score}</span>
      </div>

      <p className="mt-4 text-xs leading-5 text-sub">{exit.rationale}</p>

      <p className="mt-3 rounded-lg bg-warnBg/60 px-3 py-2 text-[11px] leading-5 text-warn">
        ⓘ 매수 시점을 오늘로 가정. 실거래는 외부 매매 앱에서 직접 매도 주문하세요.
      </p>
    </div>
  );
}

function TargetCard({ target }: { target: PriceTarget }) {
  const up = target.expected_return_pct >= 0;
  const months = Math.round(target.horizon_days / 21);
  const upConservative = (target.conservative_price - target.current_price) / target.current_price * 100;
  const upOptimistic = (target.optimistic_price - target.current_price) / target.current_price * 100;

  return (
    <div className="card">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-up text-white">
          <Target size={16} />
        </div>
        <div>
          <p className="text-xs font-bold text-up">장기 목표가</p>
          <p className="text-[10px] text-muted">약 {months}개월 후 도달 가능 가격대</p>
        </div>
      </div>

      <div className="mt-5 flex items-baseline gap-2">
        <p className="text-display font-extrabold text-ink tabular leading-none">
          {target.base_price.toLocaleString()}
        </p>
        <span className="text-xs font-medium text-muted">원</span>
      </div>
      <p className={`mt-1 text-base font-bold tabular ${up ? "text-up" : "text-down"}`}>
        {up ? "+" : ""}{target.expected_return_pct.toFixed(2)}% <span className="text-xs font-medium text-muted">대비 현재가</span>
      </p>

      {/* 시나리오 3종 */}
      <div className="mt-5 space-y-2">
        <ScenarioRow
          label="보수 시나리오"
          price={target.conservative_price}
          changePct={upConservative}
          tone="text-sub"
          bg="bg-surface"
        />
        <ScenarioRow
          label="중립 (모델)"
          price={target.base_price}
          changePct={target.expected_return_pct}
          tone="text-ink font-extrabold"
          bg="bg-surface2"
          icon={<TrendingUp size={14} />}
        />
        <ScenarioRow
          label="낙관 시나리오"
          price={target.optimistic_price}
          changePct={upOptimistic}
          tone="text-up"
          bg="bg-up/5"
          icon={<ArrowUpRight size={14} />}
        />
      </div>

      <p className="mt-4 text-xs leading-5 text-muted">{target.rationale}</p>
    </div>
  );
}

function ScenarioRow({
  label,
  price,
  changePct,
  tone,
  bg,
  icon,
}: {
  label: string;
  price: number;
  changePct: number;
  tone: string;
  bg: string;
  icon?: React.ReactNode;
}) {
  const up = changePct >= 0;
  return (
    <div className={`flex items-center justify-between rounded-xl px-3 py-2.5 ${bg}`}>
      <p className="flex items-center gap-1.5 text-xs font-bold text-sub">
        {icon}
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <p className={`text-sm tabular ${tone}`}>{price.toLocaleString()}</p>
        <p className={`text-xs font-bold tabular ${up ? "text-up" : "text-down"}`}>
          {up ? "+" : ""}{changePct.toFixed(1)}%
        </p>
      </div>
    </div>
  );
}
