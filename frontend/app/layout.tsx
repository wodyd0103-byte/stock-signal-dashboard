import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./fonts.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quant Insight",
  description: "단일 페이지 주식 분석 도구. 외부 매매 앱 보조용 참고 정보.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        {/* @font-face 선언은 app/fonts.css 로 내려와 앱 CSS 번들에 들어간다.
            여기서 렌더를 막는 외부 스타일시트를 기다리지 않는다. woff2 조각만
            아래 출처에서 오므로 연결(DNS + TLS)은 미리 열어둔다. */}
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />
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
