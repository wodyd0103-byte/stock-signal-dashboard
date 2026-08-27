# Quant Insight Frontend

Next.js 16 (App Router) · React 18 · TypeScript · Tailwind CSS · Recharts · lucide-react

제품 설명, API 목록, 신호 엔진 동작은 [루트 README](../README.md)에 있습니다. 이 문서는 프론트엔드 코드를 고칠 때 필요한 것만 다룹니다.

> 왜 이런 구조인지(훅 분리 이유, 테스트 세 층의 분업, 색 토큰의 역할 분리)는
> [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)에 있습니다.

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
hooks/       데이터 페칭 훅 (useAsyncData / useAsyncAction / queries)
lib/api.ts   백엔드 호출 전부
lib/types/   API 응답 타입. 도메인별 9개 파일 + 배럴(`@/lib/types`로 가져다 쓴다)
demo-data/   캡처해둔 실제 백엔드 응답. 테스트와 데모 배포가 같이 쓴다
scripts/     demo-data를 정적 API로 펼치는 빌드 스크립트
tests/       Playwright 스펙
```

`app/`에는 `error.tsx`, `not-found.tsx`, `global-error.tsx`가 있습니다. `global-error.tsx`는 루트 레이아웃을 **대체**하므로 `<html>`/`<body>`, `globals.css` import, 테마 스크립트를 자체적으로 들고 있어야 합니다.

## 데이터 흐름

백엔드 호출은 전부 `lib/api.ts`를 지납니다. `request()`가 두 가지를 정규화합니다.

- 네트워크 실패 → "백엔드 서버에 연결할 수 없습니다" + 현재 API 주소
- HTTP 오류 → FastAPI의 `detail`, 또는 `detail.provider_error`를 꺼내 메시지로

컴포넌트는 `lib/api.ts`를 직접 부르지 않고 `hooks/`를 지납니다.

- **`useAsyncData(fetcher, deps)`** — 화면이 그리는 데 필요한 조회. 응답을 **요청 키**에 저장하고 화면은 현재 키만 읽습니다. 그래서 탭이나 기간을 빠르게 바꿔도 늦게 도착한 응답이 새 값을 덮어쓰지 못합니다. 같은 키는 다시 요청하지 않고, `refetch()`는 키를 새로 만들어 서버 캐시까지 무시합니다. `loading`은 state가 아니라 "현재 키의 응답이 아직 없음"으로 계산됩니다.
- **`useAsyncAction(fn)`** — 클릭이 시작하는 요청(추가·삭제·비교·백테스트·리밸런싱). 캐시하지 않고, `run()`이 값 또는 `null`을 돌려주며 실패 메시지는 `error`에 담습니다. 언마운트 뒤에는 state를 건드리지 않습니다.
- **`hooks/queries.ts`** — 앱이 하는 조회를 이름으로 제공합니다. 엔드포인트 파라미터가 컴포넌트로 새지 않게 하는 층입니다.

전역 상태나 앱 단위 캐시 계층은 없습니다. 서버 상태를 화면 간에 공유·무효화해야 할 때가 TanStack Query를 들일 시점이고, 훅 인터페이스(`data`/`error`/`loading`/`refetch`)를 거기에 맞춰 두었습니다. 지금은 관심종목 추가처럼 다른 화면을 갱신해야 하는 경우 `page.tsx`가 ref로 `WatchlistRail`의 새로고침을 부릅니다.

## 스타일

- 색은 `globals.css`의 CSS 변수(`--c-bg`, `--c-ink` …)로 정의하고 Tailwind 토큰이 이를 참조합니다. 다크 모드는 `html.dark` 클래스 하나로 전환됩니다(`darkMode: "class"`).
- **한국 주식 색 컨벤션**: `up`은 빨강(#F04452), `down`은 파랑(#3182F6). 서구권 관례와 반대이므로 새 카드를 만들 때 주의하세요.
- 반복되는 조합은 `globals.css`의 `@layer components`에 있습니다 — `.card`, `.chip`, `.btn-primary/secondary/ghost`, `.field`, `.metric-label/value`.
- 숫자에는 `.tabular`(tabular-nums)를 붙입니다. 가격과 등락률이 갱신될 때 폭이 흔들리지 않습니다.
- `prefers-reduced-motion`에서 애니메이션을 전부 끕니다.
- 테마 깜빡임(FOUC)은 `layout.tsx`의 인라인 스크립트가 렌더 전에 저장된 테마를 적용해 막습니다. `ThemeToggle`은 `useSyncExternalStore`로 `html.dark`를 직접 구독하므로 테마 상태의 복사본을 들고 있지 않습니다.

## 배포 (GitHub Pages) 와 데모 모드

<https://wodyd0103-byte.github.io/stock-signal-dashboard/>

배포되는 것은 이 Next.js 앱뿐입니다. FastAPI 백엔드는 pykrx·yfinance로 외부 시세를 받아오고 SQLite에 쓰기 때문에 정적 호스팅에 올릴 수 없습니다. 그렇다고 프론트만 올리면 링크를 연 사람은 카드마다 "백엔드 서버에 연결할 수 없습니다"만 보게 됩니다.

그래서 **데모 모드**가 있습니다. `scripts/build-demo-api.mjs`가 `demo-data/`의 실제 백엔드 응답을 `public/api/demo/` 아래에 **백엔드와 같은 경로 모양의 정적 파일**로 펼쳐 놓고, 앱은 그것을 API로 읽습니다. 서버가 필요 없으므로 GitHub Pages에 그대로 올라갑니다.

숫자와 해석 문장이 진짜라 화면이 제대로 채워집니다. 진짜가 아닌 것은 값이 고정이라는 점이고, 그건 세 군데서 알립니다 — 닫을 수 없는 상단 배너, "실시간 데이터" 대신 "미리 받아둔 응답"으로 바뀌는 출처 줄, 그리고 데모에 없는 종목을 고르면 나오는 안내입니다.

`.github/workflows/pages.yml`이 `main`에 머지될 때마다 배포합니다. 빌드에 세 값을 넣습니다.

| 환경변수                | 값                        | 이유                                          |
| ----------------------- | ------------------------- | --------------------------------------------- |
| `PAGES_BASE_PATH`       | `/stock-signal-dashboard` | 정적 export로 전환하고 basePath를 붙인다      |
| `NEXT_PUBLIC_BASE_PATH` | `/stock-signal-dashboard` | fetch 경로에는 basePath가 자동으로 안 붙는다  |
| `NEXT_PUBLIC_DEMO`      | `1`                       | 배너를 켜고 API 기본값을 `/api/demo`로 돌린다 |

`PAGES_BASE_PATH`가 없으면 평소대로 서버 렌더 빌드라서 `npm run dev`, `next start`, CI e2e는 그대로 동작합니다. `NEXT_PUBLIC_API_BASE_URL`을 주면 그쪽이 항상 우선하므로, 백엔드를 어딘가에 띄웠다면 그 주소를 넣으면 됩니다.

로컬에서 배포본과 같은 것을 확인하려면:

```powershell
cd frontend
$env:PAGES_BASE_PATH="/stock-signal-dashboard"; $env:NEXT_PUBLIC_BASE_PATH="/stock-signal-dashboard"; $env:NEXT_PUBLIC_DEMO="1"
npm run build
# out/ 을 <아무 폴더>/stock-signal-dashboard 로 복사한 뒤 그 상위 폴더를 정적 서버로 연다
npx serve <아무 폴더>
```

## 품질 검사

CI가 도는 순서 그대로입니다.

```bash
npm run format:check   # Prettier. 고칠 때는 npm run format
npm run lint           # ESLint (flat config, eslint-config-next)
npm test               # Vitest 단위 테스트 (jsdom, 약 2초)
npm run build          # 타입 체크 포함
npx playwright test    # 백엔드 없이 돈다
```

`npm install`이 `.githooks`를 커밋 훅으로 등록하므로 포맷이 어긋난 커밋은 로컬에서 막힙니다. 우회는 `git commit --no-verify`입니다.

## 테스트

두 층으로 나뉩니다. **Vitest**(`hooks/*.test.ts`, `vitest.config.mts`)는 브라우저가 필요 없는 것을 2초 안에 돌리고, **Playwright**(`tests/`)는 진짜 브라우저가 있어야만 의미가 있는 것을 봅니다. 확장자가 겹치면 vitest가 Playwright 스펙을 집어 들고 `test.describe`에서 터지므로, vitest는 `*.test.ts`만 보고 `tests/`는 통째로 제외합니다.

`hooks/useAsyncData.test.ts`와 `useAsyncAction.test.ts`는 응답 시점을 직접 쥐고 캐시 키, 늦게 온 응답, `enabled`, 실패 시 `null` 반환을 확인합니다. 언마운트 뒤 setState는 **일부러 단언하지 않습니다** — React 18에서 그 시점 setState는 조용한 no-op이라 가드를 지워도 밖에서 보이는 차이가 없고, `console.error`가 비었는지 보는 식의 검사는 무조건 통과하기 때문입니다.

`tests/horizontal-overflow.spec.ts`가 375 / 768 / 1024 / 1440px에서 탭 3개를 모두 눌러가며 `document.documentElement.scrollWidth === clientWidth`를 확인합니다. 좁은 화면 가로 스크롤이 세 번 재발한 적이 있어 자동으로 막습니다. jsdom에는 레이아웃 엔진이 없어 이 검사는 진짜 브라우저에서만 의미가 있습니다.

`tests/data-fetching.spec.ts`는 요청 수를 세서 훅의 약속을 확인합니다 — 탭에 돌아올 때 재요청하지 않는지, 새로고침이 `force_refresh=true`를 보내는지, 늦게 온 응답이 그 사이 고른 값을 덮지 않는지, 실패가 조용히 삼켜지지 않는지. `tests/demo-api.spec.ts`는 배포용 데모 API의 경로 모양을 확인합니다.

API 응답은 `demo-data/`에 실제 백엔드 응답을 떠둔 것을 `tests/mock-api.ts`가 가로채 돌려줍니다. 파이썬도 네트워크도 필요 없습니다. 데모 배포도 같은 파일을 쓰므로, 테스트가 통과한 화면과 링크로 보이는 화면이 갈라지지 않습니다. 라우트 매칭은 부분 문자열이 아니라 정규식으로 합니다 — `/analysis`는 `/stocks/{ticker}/analysis`와 `/portfolio/analysis` 양쪽에 걸립니다.

`demo-data/*.json`은 Prettier 대상에서 제외돼 있습니다. 다시 캡처했을 때 진짜 변경분만 보이게 하려는 것입니다.

## 알려진 한계

- 단위 테스트는 훅 두 개뿐입니다. 컴포넌트 렌더 단위 테스트는 아직 없습니다.
- 캐시는 컴포넌트 단위입니다. 언마운트되면 사라지고 화면 간에 공유되지 않습니다.
- 검색에 디바운스가 없고, `DiscoveryRail`은 `limit: 30` 고정이라 페이지네이션이 없습니다.
- 응답 런타임 검증이 없습니다. 타입은 컴파일 타임 선언일 뿐입니다.
- 접근성 속성이 최소한만 붙어 있습니다.
