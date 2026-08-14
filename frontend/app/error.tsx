"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

/**
 * 렌더 중 터진 예외를 받는 경계. 데이터 조회 실패는 각 카드가 자체 오류 상태로
 * 처리하므로, 여기까지 오는 건 예상하지 못한 버그다. 화면을 빈 채로 두지 않고
 * 재시도 수단을 준다.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("페이지 렌더 중 오류:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="card w-full max-w-md text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-surface">
          <AlertTriangle size={26} className="text-muted" />
        </div>

        <h1 className="mt-4 text-xl font-bold text-ink">화면을 불러오지 못했습니다</h1>
        <p className="mt-2 text-sm leading-relaxed text-sub">
          예상하지 못한 오류가 발생했습니다. 다시 시도해도 같은 화면이 나오면 잠시 후 새로고침해
          주세요.
        </p>

        {error.digest ? (
          <p className="mt-4 rounded-xl bg-surface px-3 py-2 text-xs text-muted">
            오류 코드 <span className="tabular font-semibold">{error.digest}</span>
          </p>
        ) : null}

        <div className="mt-6 flex justify-center gap-2">
          <button type="button" onClick={reset} className="btn-primary">
            <RotateCw size={18} />
            다시 시도
          </button>
        </div>
      </div>
    </div>
  );
}
