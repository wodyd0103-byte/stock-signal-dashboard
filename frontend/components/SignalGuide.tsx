const buyRows = [
  ["0 ~ 39", "매수 부적합"],
  ["40 ~ 59", "관망"],
  ["60 ~ 74", "약매수 구간"],
  ["75 ~ 84", "매수 구간"],
  ["85 ~ 100", "강한 매수 후보"],
];
const sellRows = [
  ["0 ~ 39", "매도 약함"],
  ["40 ~ 59", "관망"],
  ["60 ~ 74", "약매도 구간"],
  ["75 ~ 84", "매도 구간"],
  ["85 ~ 100", "강한 매도 후보"],
];
const riskRows = [
  ["0 ~ 30", "낮음"],
  ["31 ~ 60", "보통"],
  ["61 ~ 80", "높음"],
  ["81 ~ 100", "매우 높음"],
];
const detailSignalRows = [
  ["STRONG BUY", "매수 85+, 리스크 ≤55, ML 60%+"],
  ["BUY", "매수 75+, 리스크 ≤65"],
  ["WEAK BUY", "매수 60+, 리스크 ≤75"],
  ["STRONG SELL", "매도 85+"],
  ["SELL", "매도 75+"],
  ["WEAK SELL", "매도 60+"],
  ["HOLD", "기준 미달 또는 확인 필요"],
];

export default function SignalGuide() {
  return (
    <section className="card">
      <div className="mb-4">
        <p className="text-xs font-semibold text-muted">신호 기준</p>
        <h2 className="mt-0.5 text-heading text-ink">점수가 무엇을 의미하나요?</h2>
        <p className="mt-1.5 text-sm text-sub">
          단일 종목은 최종 점수, 매수 신호 모니터는 상대순위 + 시장 국면을 반영합니다.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <GuideTable title="매수 점수" rows={buyRows} accent="text-up" />
        <GuideTable title="매도 점수" rows={sellRows} accent="text-down" />
        <GuideTable title="리스크 점수" rows={riskRows} accent="text-warn" />
        <GuideTable title="신호 매핑" rows={detailSignalRows} accent="text-toss-600" />
      </div>
    </section>
  );
}

function GuideTable({ title, rows, accent }: { title: string; rows: string[][]; accent: string }) {
  return (
    <div className="rounded-xl bg-surface p-1">
      <h3 className={`px-3 py-2 text-xs font-bold ${accent}`}>{title}</h3>
      <div className="rounded-lg bg-bg p-1">
        {rows.map(([range, label]) => (
          <div
            key={`${title}-${range}`}
            className="grid grid-cols-[80px_1fr] gap-2 px-2.5 py-1.5 text-xs"
          >
            <span className="font-bold text-ink tabular">{range}</span>
            <span className="text-sub leading-5">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
