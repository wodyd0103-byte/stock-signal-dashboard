import Link from "next/link";
import { Compass } from "lucide-react";

/**
 * 이 앱은 `/` 단일 페이지다. 여기로 오는 건 대부분 예전 문서에 남아 있던
 * `/dashboard` 같은 주소를 따라온 경우라, 홈으로 돌려보내는 것으로 충분하다.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="card w-full max-w-md text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-surface">
          <Compass size={26} className="text-muted" />
        </div>

        <p className="mt-4 text-sm font-bold text-muted">404</p>
        <h1 className="mt-1 text-xl font-bold text-ink">없는 주소입니다</h1>
        <p className="mt-2 text-sm leading-relaxed text-sub">
          Quant Insight는 한 화면에서 분석, 포트폴리오, 리서치를 모두 제공합니다. 홈에서 종목을
          검색해 주세요.
        </p>

        <div className="mt-6 flex justify-center">
          <Link href="/" className="btn-primary">
            홈으로 가기
          </Link>
        </div>
      </div>
    </div>
  );
}
