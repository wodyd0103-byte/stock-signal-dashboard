/**
 * GitHub Pages 배포는 `PAGES_BASE_PATH`를 넣고 빌드한다(워크플로 참고).
 * 그때만 정적 export로 바뀌며, 프로젝트 페이지가 하위 경로에 서빙되므로
 * basePath도 같이 붙는다. 기본 빌드는 그대로 서버 렌더용이라 `next start`와
 * CI의 e2e가 영향을 받지 않는다.
 */
const basePath = process.env.PAGES_BASE_PATH ?? "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  ...(basePath
    ? {
        output: "export",
        basePath,
        // 정적 서버는 `/foo`를 `/foo/index.html`로 찾아준다.
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
