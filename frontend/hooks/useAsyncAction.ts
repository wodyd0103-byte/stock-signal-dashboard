"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "./errorMessage";

export interface AsyncAction<A extends unknown[], T> {
  /** 실패하면 null을 돌려주고 error에 메시지를 담는다. 예외를 다시 던지지 않는다. */
  run: (...args: A) => Promise<T | null>;
  pending: boolean;
  error: string | null;
  clearError: () => void;
}

/**
 * 사용자가 눌러서 시작하는 요청. 관심종목 추가, 리밸런싱 계산, 종목 비교처럼
 * 렌더가 아니라 이벤트가 촉발하는 것들이다.
 *
 * 가져오기(useAsyncData)와 나눠 둔 이유는 필요한 게 다르기 때문이다. 이쪽은
 * 캐시가 없어야 하고(같은 버튼을 두 번 누르면 두 번 실행돼야 한다), 호출부가
 * 결과를 받아 이어서 처리해야 하는 경우가 많다.
 *
 * 언마운트 뒤에는 state를 건드리지 않는다. 응답이 오기 전에 탭이 바뀌는 일이
 * 실제로 생긴다.
 */
export function useAsyncAction<A extends unknown[], T>(
  action: (...args: A) => Promise<T>,
  { fallbackMessage = "요청 실패" }: { fallbackMessage?: string } = {},
): AsyncAction<A, T> {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // action은 렌더마다 새로 만들어지는 익명 함수인 경우가 많다. ref에 담아두면
  // run의 정체성이 안정되어 자식 컴포넌트 props로 넘겨도 렌더가 늘지 않는다.
  const actionRef = useRef(action);
  useEffect(() => {
    actionRef.current = action;
  });

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const run = useCallback(
    async (...args: A) => {
      setPending(true);
      setError(null);
      try {
        return await actionRef.current(...args);
      } catch (e) {
        if (mountedRef.current) setError(errorMessage(e, fallbackMessage));
        return null;
      } finally {
        if (mountedRef.current) setPending(false);
      }
    },
    [fallbackMessage],
  );

  return { run, pending, error, clearError: useCallback(() => setError(null), []) };
}
