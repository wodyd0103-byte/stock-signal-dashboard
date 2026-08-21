import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quant Insight",
  description: "단일 페이지 주식 분석 도구. 외부 매매 앱 보조용 참고 정보.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        {/* 폰트는 외부 CDN 에서 오고, 그 스타일시트는 렌더를 막는다. preconnect 로
            연결(DNS + TLS)을 미리 열어두면 Lighthouse 기준 300ms 가 줄어든다.
            폰트 자체를 번들에 넣는 next/font 전환은 별도 작업으로 남겨뒀다. */}
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
        {/* FOUC 방지: 렌더 전 저장된 테마 적용 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');var d=t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches);if(d)document.documentElement.classList.add('dark');}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-bg">{children}</body>
    </html>
  );
}
