"use client";

import { useId, type KeyboardEvent } from "react";
import { nextRovingIndex } from "./rovingFocus";

/**
 * WAI-ARIA 라디오 묶음의 배선. 모양은 부르는 쪽이 정한다.
 *
 * 앱에 "여럿 중 하나" 버튼 묶음이 다섯 군데 있다 — 조회 기간, 차트 봉 단위,
 * IC 시계, 리밸런싱 전략, 최적화 방식. 전부 선택 상태가 클래스에만 있어서
 * 읽어주는 쪽에는 그냥 버튼 여러 개로 들렸다.
 *
 * **탭이 아니라 라디오인 이유**: 이것들은 패널을 갈아끼우지 않는다. 같은 자리의
 * 데이터를 바꾼다. tablist 로 만들면 있지도 않은 패널을 `aria-controls` 로
 * 가리켜야 하고, 스크린리더는 "탭 3개 중 1번째" 라고 읽어 사용자가 화면이
 * 통째로 바뀔 것을 기대하게 된다.
 *
 * 화살표는 선택과 포커스를 함께 옮긴다(네이티브 라디오와 같은 동작). 그래서
 * IC 시계처럼 선택이 요청을 부르는 자리에서는 훑고 지나가는 동안 요청이
 * 뜨는데, 이는 클릭으로 훑을 때와 같고 `useAsyncData` 가 늦은 응답을 버린다.
 */
export function useRadioGroup<T extends string>({
  values,
  active,
  onChange,
  label,
}: {
  values: readonly T[];
  active: T;
  onChange: (value: T) => void;
  /** 묶음의 이름. 화면에 제목이 없는 곳이 많아 여기서 준다. */
  label: string;
}) {
  const base = useId();
  const optionId = (value: T) => `${base}-${value}`;

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    const next = nextRovingIndex(event.key, values.indexOf(active), values.length, "both");
    if (next === null) return;

    // 위아래까지 받으므로 막지 않으면 페이지가 같이 스크롤된다.
    event.preventDefault();
    onChange(values[next]);
    // 선택만 옮기면 포커스가 옛 항목에 남아 다음 화살표가 엉뚱한 데서 출발한다.
    document.getElementById(optionId(values[next]))?.focus();
  }

  return {
    groupProps: {
      role: "radiogroup" as const,
      "aria-label": label,
      onKeyDown,
    },
    getRadioProps: (value: T) => ({
      id: optionId(value),
      role: "radio" as const,
      "aria-checked": value === active,
      // roving tabindex — 묶음 전체를 Tab 한 번에 지나간다.
      tabIndex: value === active ? 0 : -1,
      onClick: () => onChange(value),
    }),
  };
}
