import { describe, expect, it } from "vitest";
import { arcColor, textColor, textTint } from "./sentimentColor";

/**
 * 계조(장식)와 대비(글씨)가 서로 다른 경계를 쓰면 게이지 바늘이 가리키는 칸과
 * 옆의 숫자 색이 어긋난다. 두 함수의 경계를 같은 파일에서 나란히 고정한다.
 */

describe("arcColor — 장식용 5단 계조", () => {
  it.each([
    [0, "#3182F6"],
    [24, "#3182F6"],
    [25, "#84B6FC"],
    [44, "#84B6FC"],
    [45, "#8B95A1"],
    [55, "#8B95A1"],
    [56, "#FF7B82"],
    [74, "#FF7B82"],
    [75, "#F04452"],
    [100, "#F04452"],
  ])("점수 %i은 %s", (score, hex) => {
    expect(arcColor(score)).toBe(hex);
  });
});

describe("textColor — 글씨용 3단", () => {
  it.each([
    [0, "--c-down"],
    [44, "--c-down"],
    [45, "--c-muted"],
    [55, "--c-muted"],
    [56, "--c-up"],
    [100, "--c-up"],
  ])("점수 %i은 %s 토큰", (score, token) => {
    // hex 를 직접 돌려주면 다크 테마에서 그대로 쓰여 대비가 무너진다.
    expect(textColor(score)).toBe(`rgb(var(${token}))`);
  });

  it("글씨 색은 hex 를 돌려주지 않는다", () => {
    for (const score of [0, 30, 50, 70, 100]) {
      expect(textColor(score)).not.toMatch(/#[0-9a-f]{6}/i);
    }
  });
});

describe("textTint — 글씨 뒤 배경", () => {
  it.each([
    [0, "--c-down"],
    [50, "--c-muted"],
    [100, "--c-up"],
  ])("점수 %i의 배경은 글씨와 같은 토큰의 10%%", (score, token) => {
    // 글씨와 배경이 다른 토큰이면 대비 계산이 어긋난다.
    expect(textTint(score)).toBe(`rgb(var(${token}) / 0.1)`);
    expect(textColor(score)).toContain(token);
  });
});

describe("두 스케일의 경계", () => {
  it("중립 구간은 45~55로 같다", () => {
    // 아크가 회색인데 숫자가 빨강이면 같은 점수를 두 가지로 말하는 셈이다.
    for (const score of [45, 50, 55]) {
      expect(arcColor(score)).toBe("#8B95A1");
      expect(textColor(score)).toContain("--c-muted");
    }
  });

  it("공포·탐욕 방향이 서로 어긋나지 않는다", () => {
    const cool = new Set(["#3182F6", "#84B6FC"]);
    const warm = new Set(["#FF7B82", "#F04452"]);
    for (let score = 0; score <= 100; score += 1) {
      const arc = arcColor(score);
      const text = textColor(score);
      if (cool.has(arc)) expect(text).toContain("--c-down");
      else if (warm.has(arc)) expect(text).toContain("--c-up");
      else expect(text).toContain("--c-muted");
    }
  });
});
