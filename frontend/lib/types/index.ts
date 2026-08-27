/**
 * 백엔드 응답의 타입. 예전에는 651줄짜리 파일 하나였고, 어떤 타입이 어느
 * 화면의 것인지 이름으로만 짐작해야 했다.
 *
 * 이 배럴은 지우지 않는다. 화면 31곳이 `@/lib/types` 에서 가져다 쓰는데, 그
 * 임포트를 도메인별로 갈라 적게 하면 타입이 파일을 옮길 때마다 호출부가 같이
 * 깨진다. 안쪽 구성은 여기서 흡수하고 바깥에서 보는 이름은 그대로 둔다.
 */
export * from "./common";
export * from "./signal";
export * from "./prediction";
export * from "./market";
export * from "./analysis";
export * from "./backtest";
export * from "./discovery";
export * from "./portfolio";
export * from "./retrospective";
