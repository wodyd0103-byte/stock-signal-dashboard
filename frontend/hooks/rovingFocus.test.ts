import { describe, expect, it } from "vitest";
import { nextRovingIndex } from "./rovingFocus";

/**
 * 탭 묶음과 라디오 묶음이 공유하는 계산이라 여기서 한 번에 고정한다.
 * 화면에서 보면 "화살표를 눌렀는데 한 칸 더 갔다" 정도로만 드러나서
 * 어느 쪽 버그인지 짚기 어렵다.
 */

const N = 3; // [0, 1, 2]

describe("nextRovingIndex", () => {
  it.each([
    ["ArrowRight", 0, 1],
    ["ArrowRight", 1, 2],
    ["ArrowLeft", 2, 1],
    ["ArrowLeft", 1, 0],
  ])("%s 는 %i → %i", (key, index, expected) => {
    expect(nextRovingIndex(key, index, N, "horizontal")).toBe(expected);
  });

  it("양 끝에서 감는다", () => {
    // 끝에서 멈추면 마지막에서 첫 항목으로 가려고 반대 방향을 N-1 번 눌러야 한다.
    expect(nextRovingIndex("ArrowRight", 2, N, "horizontal")).toBe(0);
    expect(nextRovingIndex("ArrowLeft", 0, N, "horizontal")).toBe(2);
  });

  it("Home / End 는 양 끝으로 건너뛴다", () => {
    expect(nextRovingIndex("Home", 2, N, "horizontal")).toBe(0);
    expect(nextRovingIndex("End", 0, N, "horizontal")).toBe(2);
  });

  it("가로 묶음은 위아래를 흘려보낸다", () => {
    // null 을 돌려줘야 부르는 쪽이 preventDefault 를 안 하고 페이지가 스크롤된다.
    expect(nextRovingIndex("ArrowUp", 1, N, "horizontal")).toBeNull();
    expect(nextRovingIndex("ArrowDown", 1, N, "horizontal")).toBeNull();
  });

  it("라디오 묶음은 위아래도 받는다", () => {
    expect(nextRovingIndex("ArrowDown", 0, N, "both")).toBe(1);
    expect(nextRovingIndex("ArrowUp", 0, N, "both")).toBe(2);
  });

  it("아래/오른쪽, 위/왼쪽은 같은 방향이다", () => {
    expect(nextRovingIndex("ArrowDown", 1, N, "both")).toBe(
      nextRovingIndex("ArrowRight", 1, N, "both"),
    );
    expect(nextRovingIndex("ArrowUp", 1, N, "both")).toBe(
      nextRovingIndex("ArrowLeft", 1, N, "both"),
    );
  });

  it.each(["Tab", "Enter", " ", "Escape", "a", "PageDown"])("%j 는 무시한다", (key) => {
    expect(nextRovingIndex(key, 1, N, "both")).toBeNull();
  });

  it("항목이 하나뿐이면 제자리", () => {
    expect(nextRovingIndex("ArrowRight", 0, 1, "both")).toBe(0);
    expect(nextRovingIndex("ArrowLeft", 0, 1, "both")).toBe(0);
  });

  it("빈 묶음이나 못 찾은 항목에는 아무것도 안 한다", () => {
    // indexOf 가 -1 을 준 경우. 그대로 계산하면 음수 인덱스가 나온다.
    expect(nextRovingIndex("ArrowRight", -1, N, "both")).toBeNull();
    expect(nextRovingIndex("ArrowRight", 0, 0, "both")).toBeNull();
  });
});
