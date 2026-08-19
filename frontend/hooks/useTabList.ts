"use client";

import { useId, type KeyboardEvent } from "react";

/**
 * WAI-ARIA 탭 패턴의 배선만 제공한다. 모양은 부르는 쪽이 정한다.
 *
 * 앱에 탭 묶음이 둘 있는데(메인 3탭, 발굴 레일 2탭) 생김새가 완전히 달라서
 * 공용 컴포넌트로 묶으면 스타일 prop 만 늘어난다. 대신 어긋나면 안 되는 것 —
 * role, id 짝, `aria-selected`, roving tabindex, 화살표 이동 — 만 여기서 준다.
 *
 * 지키는 규칙 두 가지:
 *
 * - **탭 묶음은 Tab 키 한 번에 통과한다.** 선택된 탭만 `tabIndex=0`이고 나머지는
 *   -1이다(roving tabindex). 안 그러면 탭이 다섯 개일 때 본문에 닿기까지 Tab 을
 *   다섯 번 눌러야 한다.
 * - **화살표로 이동하면 그 자리에서 선택된다**(automatic activation). 패널이 이미
 *   전부 렌더돼 있어 전환 비용이 없으므로 APG 가 권하는 쪽을 따른다.
 */
export function useTabList<T extends string>({
  ids,
  active,
  onChange,
  label,
}: {
  ids: readonly T[];
  active: T;
  onChange: (id: T) => void;
  /** 탭 묶음의 이름. 화면에 제목이 없으므로 여기서 준다. */
  label: string;
}) {
  const base = useId();
  const tabId = (id: T) => `${base}-tab-${id}`;
  const panelId = (id: T) => `${base}-panel-${id}`;

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    const index = ids.indexOf(active);
    if (index < 0) return;

    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % ids.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + ids.length) % ids.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = ids.length - 1;
    if (next === null) return;

    // 좌우 화살표는 가로 탭 묶음 안에서만 쓰이므로 페이지 스크롤을 막는다.
    event.preventDefault();
    onChange(ids[next]);
    // 선택만 옮기면 포커스는 옛 탭에 남아 다음 화살표가 엉뚱한 곳에서 출발한다.
    document.getElementById(tabId(ids[next]))?.focus();
  }

  return {
    tablistProps: {
      role: "tablist" as const,
      "aria-label": label,
      onKeyDown,
    },
    getTabProps: (id: T) => ({
      id: tabId(id),
      role: "tab" as const,
      "aria-selected": id === active,
      "aria-controls": panelId(id),
      tabIndex: id === active ? 0 : -1,
      onClick: () => onChange(id),
    }),
    getPanelProps: (id: T) => ({
      id: panelId(id),
      role: "tabpanel" as const,
      "aria-labelledby": tabId(id),
      // 패널 안이 스크롤되거나 길 수 있다. 키보드로 초점을 줄 수 있어야 한다.
      tabIndex: 0,
      hidden: id !== active,
    }),
  };
}
