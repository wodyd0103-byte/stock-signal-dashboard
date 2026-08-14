# Quant Insight Frontend

Next.js 16 (App Router) · React 18 · TypeScript · Tailwind CSS · Recharts · lucide-react

제품 설명, API 목록, 신호 엔진 동작은 [루트 README](../README.md)에 있습니다. 이 문서는 프론트엔드 코드를 고칠 때 필요한 것만 다룹니다.

## 실행

```bash
cd frontend
npm install
npm run dev
```

백엔드가 떠 있어야 화면에 데이터가 나옵니다(`cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`). 백엔드가 없으면 각 카드가 "백엔드 서버에 연결할 수 없습니다" 오류 상태로 그려집니다.

API 주소 기본값은 `http://127.0.0.1:8000/api`입니다. 바꾸려면 `.env.local`에:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
```

## 화면 구조

라우트는 `/` **하나뿐**입니다. 화면 전환은 라우팅이 아니라 `page.tsx`의 `mainTab` 상태로 합니다.

```
app/page.tsx  (유일한 라우트, 클라이언트 컴포넌트)
├── header
│   ├── StockSearch      종목 + 기간(1개월~3년) 검색
│   ├── MiniSentiment    시장 심리 요약
│   ├── ThemeToggle      다크 모드
│   └── SettingsModal    설정
├── aside (lg 이상에서 320px 고정 레일)
│   ├── DiscoveryRail    매수 신호 / 급등 탐색
│   └── WatchlistRail    관심종목 (ref로 외부에서 reload 호출)
└── section (탭 3개)
    ├── 분석      AnalysisView + ComparePanel
    ├── 포트폴리오 PortfolioPanel
    └── 리서치    RetrospectivePanel + ICPanel
```

`AnalysisView`가 가장 큰 조립부입니다. 응답 필드가 있을 때만 그리는 카드가 많습니다 — 수급·뉴스·펀더멘털·공시는 국내 종목에서만 내려오고, 시장 심리와 학습 신호도 선택적입니다.

비활성 탭은 언마운트하지 않고 `hidden` 클래스로 숨깁니다. 즉 `display: none`이라 **레이아웃이 없습니다**. 숨은 탭의 크기를 재려는 코드나 테스트는 전부 0을 보게 되므로, 탭을 눌러 활성화한 뒤에 측정해야 합니다.

## 디렉터리

```
app/         라우트, 레이아웃, 전역 CSS, 에러 바운더리
components/  화면 컴포넌트 (전부 이 한 층, 하위 폴더 없음)
lib/api.ts   백엔드 호출 전부
lib/types.ts API 응답 타입
tests/       Playwright 스펙과 캡처해둔 응답 픽스처
```

`app/`에는 `error.tsx`, `not-found.tsx`, `global-error.tsx`가 있습니다. `global-error.tsx`는 루트 레이아웃을 **대체**하므로 `<html>`/`<body>`, `globals.css` import, 테마 스크립트를 자체적으로 들고 있어야 합니다.

## 데이터 흐름

백엔드 호출은 전부 `lib/api.ts`를 지납니다. `request()`가 두 가지를 정규화합니다.

- 네트워크 실패 → "백엔드 서버에 연결할 수 없습니다" + 현재 API 주소
- HTTP 오류 → FastAPI의 `detail`, 또는 `detail.provider_error`를 꺼내 메시지로

컴포넌트는 각자 마운트 시점에 `useEffect`로 자기 데이터를 가져옵니다. 전역 상태나 캐시 계층은 없습니다. `page.tsx`, `DiscoveryRail`, `PortfolioPanel`에 `react-hooks/set-state-in-effect` 억제 주석이 있는 것도 이 구조 때문입니다 — 이펙트 안에서 곧바로 `setLoading(true)`를 부릅니다. TanStack Query로 옮기면 이펙트째 사라집니다.

억제 주석은 규칙이 보고하는 **호출 줄 바로 위**에 둡니다. 한 줄짜리 문장 위에 두면 포맷터가 문장을 여러 줄로 펴는 순간 덮지 못합니다.

## 스타일

- 색은 `globals.css`의 CSS 변수(`--c-bg`, `--c-ink` …)로 정의하고 Tailwind 토큰이 이를 참조합니다. 다크 모드는 `html.dark` 클래스 하나로 전환됩니다(`darkMode: "class"`).
- **한국 주식 색 컨벤션**: `up`은 빨강(#F04452), `down`은 파랑(#3182F6). 서구권 관례와 반대이므로 새 카드를 만들 때 주의하세요.
- 반복되는 조합은 `globals.css`의 `@layer components`에 있습니다 — `.card`, `.chip`, `.btn-primary/secondary/ghost`, `.field`, `.metric-label/value`.
- 숫자에는 `.tabular`(tabular-nums)를 붙입니다. 가격과 등락률이 갱신될 때 폭이 흔들리지 않습니다.
- `prefers-reduced-motion`에서 애니메이션을 전부 끕니다.
- 테마 깜빡임(FOUC)은 `layout.tsx`의 인라인 스크립트가 렌더 전에 저장된 테마를 적용해 막습니다. `ThemeToggle`은 `useSyncExternalStore`로 `html.dark`를 직접 구독하므로 테마 상태의 복사본을 들고 있지 않습니다.

## 품질 검사

CI가 도는 순서 그대로입니다.

```bash
npm run format:check   # Prettier. 고칠 때는 npm run format
npm run lint           # ESLint (flat config, eslint-config-next)
npm run build          # 타입 체크 포함
npx playwright test    # 백엔드 없이 돈다
```

`npm install`이 `.githooks`를 커밋 훅으로 등록하므로 포맷이 어긋난 커밋은 로컬에서 막힙니다. 우회는 `git commit --no-verify`입니다.

## 테스트

`tests/horizontal-overflow.spec.ts`가 375 / 768 / 1024 / 1440px에서 탭 3개를 모두 눌러가며 `document.documentElement.scrollWidth === clientWidth`를 확인합니다. 좁은 화면 가로 스크롤이 세 번 재발한 적이 있어 자동으로 막습니다. jsdom에는 레이아웃 엔진이 없어 이 검사는 진짜 브라우저에서만 의미가 있습니다.

API 응답은 `tests/fixtures`에 실제 백엔드 응답을 떠둔 것을 `tests/mock-api.ts`가 가로채 돌려줍니다. 파이썬도 네트워크도 필요 없습니다. 라우트 매칭은 부분 문자열이 아니라 정규식으로 합니다 — `/analysis`는 `/stocks/{ticker}/analysis`와 `/portfolio/analysis` 양쪽에 걸립니다.

픽스처는 Prettier 대상에서 제외돼 있습니다. 다시 캡처했을 때 진짜 변경분만 보이게 하려는 것입니다.

## 알려진 한계

- 컴포넌트 단위 테스트가 없습니다. Playwright 스펙은 레이아웃 회귀 전용입니다.
- API 훅 계층이 없습니다(`lib/api.ts` 하나). 서버 상태 캐싱·재시도·중복 제거도 없습니다.
- 검색에 디바운스가 없고, `DiscoveryRail`은 `limit: 30` 고정이라 페이지네이션이 없습니다.
- 응답 런타임 검증이 없습니다. 타입은 컴파일 타임 선언일 뿐입니다.
- 접근성 속성이 최소한만 붙어 있습니다.
