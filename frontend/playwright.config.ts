import { defineConfig, devices } from "@playwright/test";

/**
 * 레이아웃 회귀만 확인하는 설정. 백엔드는 띄우지 않고 tests/fixtures 의 응답을
 * 라우트 가로채기로 돌려주므로, 실행에 필요한 건 프론트엔드 프로덕션 서버뿐이다.
 * dev 서버 대신 build + start 를 쓰는 이유는 CI 와 로컬이 같은 산출물을 보게
 * 하기 위해서다.
 */
// PW_BASE_URL 이 있으면 이미 떠 있는 서버를 그대로 쓴다. 프로덕션 번들은 스택이
// 압축돼 있어 원인 추적이 어려우므로, 실패를 파고들 때는 dev 서버를 켜 두고
// PW_BASE_URL=http://127.0.0.1:3000 으로 붙이면 된다.
const externalBaseUrl = process.env.PW_BASE_URL;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // CI 에서는 실패 시 리포트를 아티팩트로 올리므로 html 도 같이 낸다.
  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: externalBaseUrl ?? "http://127.0.0.1:3100",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: externalBaseUrl
    ? undefined
    : {
        command: "npm run build && npx next start --port 3100",
        url: "http://127.0.0.1:3100",
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
      },
});
