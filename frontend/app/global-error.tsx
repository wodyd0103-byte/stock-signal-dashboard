"use client";

import { useEffect } from "react";
import "./globals.css";

/**
 * 루트 레이아웃 자체가 터졌을 때만 쓰인다. 이 경우 layout.tsx가 통째로 대체되므로
 * html/body와 스타일, 테마 스크립트를 여기서 다시 갖춰야 한다.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("루트 레이아웃 오류:", error);
  }, [error]);

  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');var d=t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches);if(d)document.documentElement.classList.add('dark');}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-bg">
        <div className="flex min-h-screen items-center justify-center px-4">
          <div className="card w-full max-w-md text-center">
            <h1 className="text-xl font-bold text-ink">앱을 시작하지 못했습니다</h1>
            <p className="mt-2 text-sm leading-relaxed text-sub">
              페이지를 다시 불러와 주세요. 문제가 계속되면 잠시 후 다시 접속해 주세요.
            </p>

            {error.digest ? (
              <p className="mt-4 rounded-xl bg-surface px-3 py-2 text-xs text-muted">
                오류 코드 <span className="tabular font-semibold">{error.digest}</span>
              </p>
            ) : null}

            <div className="mt-6 flex justify-center">
              <button type="button" onClick={reset} className="btn-primary">
                다시 시도
              </button>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
