/**
 * 공포·탐욕 색.
 *
 * 한 스케일을 텍스트와 그래픽에 같이 쓸 수 없다는 것이 이 파일이 있는 이유다.
 * 5단 계조는 중간 두 칸(연한 파랑·연한 빨강)이 밝아야 계조로 보이는데, 그 밝기로는
 * 라이트 테마에서 글씨가 4.5:1 을 못 넘는다. 그래서 나눴다.
 *
 * - `arcColor`  : 게이지 아크·막대 같은 **장식**. 5단 계조를 유지한다.
 *                 (WCAG 는 장식 그래픽에 4.5:1 을 요구하지 않는다)
 * - `textColor` : 숫자·라벨 같은 **글씨**. 하락파랑 / 중립회색 / 상승빨강 3단으로
 *                 줄이고 테마 토큰을 그대로 쓴다. 계조는 옆의 게이지가 보여준다.
 */

/** 장식용 5단 계조 (공포 → 탐욕). 텍스트에 쓰지 말 것. */
export function arcColor(score: number): string {
  if (score <= 24) return "#3182F6";
  if (score <= 44) return "#84B6FC";
  if (score <= 55) return "#8B95A1";
  if (score <= 74) return "#FF7B82";
  return "#F04452";
}

/** 글씨용 3단. 테마에 따라 값이 바뀌는 CSS 변수를 돌려준다. */
export function textColor(score: number): string {
  if (score <= 44) return "rgb(var(--c-down))";
  if (score <= 55) return "rgb(var(--c-muted))";
  return "rgb(var(--c-up))";
}

/** 글씨 뒤에 까는 옅은 배경. 같은 색의 10% 라 위의 textColor 와 짝이 맞는다. */
export function textTint(score: number): string {
  if (score <= 44) return "rgb(var(--c-down) / 0.1)";
  if (score <= 55) return "rgb(var(--c-muted) / 0.1)";
  return "rgb(var(--c-up) / 0.1)";
}
