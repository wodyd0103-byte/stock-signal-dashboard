import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

/**
 * 훅과 컴포넌트 단위 테스트.
 *
 * Playwright(`tests/`)와 역할이 다르다. 저쪽은 진짜 브라우저가 필요한 것 —
 * 레이아웃 넘침, 실제 요청 수, 배포본 —을 보고, 이쪽은 브라우저 없이 빨리 돌려야
 * 하는 것 — 캐시 키, 경쟁 조건, 언마운트 뒤 setState —을 본다. 그래서 include를
 * `*.test.*`로 한정하고 `tests/`는 통째로 제외한다. 확장자가 겹치면 vitest가
 * Playwright 스펙을 집어 들고 `test.describe`에서 터진다.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["{app,components,hooks,lib}/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", "tests/**", ".next/**", "out/**"],
    restoreMocks: true,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
});
