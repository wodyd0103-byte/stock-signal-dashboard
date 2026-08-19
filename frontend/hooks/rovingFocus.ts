/**
 * 화살표 키를 다음 인덱스로 옮기는 계산. React 와 무관한 순수 함수다.
 *
 * 탭 묶음과 라디오 묶음이 같은 규칙을 쓰는데, 각자 복사해두면 한쪽만 고쳐지는
 * 날이 온다. 실제로 다른 것은 **어떤 키를 받느냐** 하나뿐이라 그것만 인자로 뺐다.
 *
 * - 탭은 가로 배치라 좌우만 받는다(APG: 세로 탭일 때만 위아래).
 * - 라디오 묶음은 배치와 무관하게 네 방향을 다 받는다. 네이티브 라디오가 그렇다.
 */
export type RovingOrientation = "horizontal" | "both";

const PREV = new Set(["ArrowLeft", "ArrowUp"]);
const NEXT = new Set(["ArrowRight", "ArrowDown"]);

export function nextRovingIndex(
  key: string,
  index: number,
  count: number,
  orientation: RovingOrientation,
): number | null {
  if (count <= 0 || index < 0) return null;

  const vertical = key === "ArrowUp" || key === "ArrowDown";
  if (vertical && orientation === "horizontal") return null;

  // 양 끝에서 감는다. 끝에서 멈추면 마지막 항목에서 첫 항목으로 가려고
  // 반대 방향으로 (개수-1)번 눌러야 한다.
  if (NEXT.has(key)) return (index + 1) % count;
  if (PREV.has(key)) return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}
