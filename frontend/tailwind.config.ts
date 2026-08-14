import type { Config } from "tailwindcss";

/**
 * 토스증권 스타일 디자인 토큰
 * - 흰색 베이스 + 부드러운 회색 surface
 * - 한국 주식 색 컨벤션: 빨강 = 상승, 파랑 = 하락
 * - Toss Blue #3182F6 primary
 * - 큰 타이포그래피, 무경계 카드 + 부드러운 그림자
 */
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // 베이스 (CSS 변수 → 다크모드 자동 전환, alpha 지원)
        bg: "rgb(var(--c-bg) / <alpha-value>)",
        card: "rgb(var(--c-card) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        surface2: "rgb(var(--c-surface2) / <alpha-value>)",

        // 텍스트
        ink: "rgb(var(--c-ink) / <alpha-value>)",
        sub: "rgb(var(--c-sub) / <alpha-value>)",
        muted: "rgb(var(--c-muted) / <alpha-value>)",
        faint: "rgb(var(--c-faint) / <alpha-value>)",
        line: "rgb(var(--c-line) / <alpha-value>)",

        // 토스 블루 (primary) — 양 테마 공통
        toss: {
          DEFAULT: "#3182F6",
          50: "rgb(var(--c-toss-50) / <alpha-value>)",
          100: "#DEEBFF",
          200: "#B6D4FE",
          300: "#84B6FC",
          400: "#4A90E2",
          500: "#3182F6",
          600: "#1A6CE0",
          700: "rgb(var(--c-toss-700) / <alpha-value>)",
        },

        // 한국 주식 컨벤션 (양 테마 공통 비비드)
        up: "#F04452", // 상승 빨강
        upBg: "#FEF2F2",
        down: "#3182F6", // 하락 파랑
        downBg: "#EEF5FF",

        // 신호 컬러 (기존 호환)
        buy: "#F04452",
        weakBuy: "#FF7B82",
        hold: "#8B95A1",
        weakSell: "#84B6FC",
        sell: "#3182F6",

        // 노란/주황 보조
        warn: "#F59F00",
        warnBg: "rgb(var(--c-warnBg) / <alpha-value>)",
      },
      fontFamily: {
        sans: [
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "Helvetica Neue",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Noto Sans KR",
          "Malgun Gothic",
          "sans-serif",
        ],
      },
      fontSize: {
        // Toss-like 큰 타이포
        "display-xl": [
          "48px",
          { lineHeight: "56px", letterSpacing: "-0.025em", fontWeight: "800" },
        ],
        display: ["36px", { lineHeight: "44px", letterSpacing: "-0.02em", fontWeight: "700" }],
        title: ["24px", { lineHeight: "32px", letterSpacing: "-0.01em", fontWeight: "700" }],
        heading: ["20px", { lineHeight: "28px", fontWeight: "700" }],
      },
      borderRadius: {
        xl2: "20px",
        card: "16px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0, 27, 55, 0.04), 0 4px 16px rgba(0, 27, 55, 0.04)",
        cardHover: "0 4px 12px rgba(0, 27, 55, 0.06), 0 12px 32px rgba(0, 27, 55, 0.08)",
        float: "0 8px 24px rgba(49, 130, 246, 0.18)",
        panel: "0 1px 2px rgba(0, 27, 55, 0.04), 0 4px 16px rgba(0, 27, 55, 0.04)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out",
        "slide-up": "slide-up 320ms cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
