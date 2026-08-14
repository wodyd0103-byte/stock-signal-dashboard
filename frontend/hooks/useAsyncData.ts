"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "./errorMessage";

export interface AsyncData<T> {
  data: T | null;
  error: string | null;
  /** 이 요청의 응답이 아직 없다는 뜻. 이전 키의 데이터는 보여주지 않는다. */
  loading: boolean;
  /** 같은 인자로 서버에 다시 물어본다. 캐시를 건너뛴다. */
  refetch: () => void;
}

interface Options {
  /** false면 요청을 보내지 않는다. 접힌 패널을 펼 때 처음 부르는 용도. */
  enabled?: boolean;
  /** Error가 아닌 것이 던져졌을 때 쓸 메시지. */
  fallbackMessage?: string;
}

interface Settled<T> {
  data: T | null;
  error: string | null;
}

/**
 * 화면에 필요한 값을 선언적으로 가져온다.
 *
 * 컴포넌트마다 `loading`/`error`/`data` 세 state와 try-catch-finally를 복사해
 * 쓰고 있었는데, 그 방식에는 세 가지 문제가 있었다.
 *
 * 1. **늦게 온 응답이 최신 응답을 덮어썼다.** 탭이나 기간을 빠르게 바꾸면
 *    먼저 보낸 요청이 나중에 도착해 화면이 과거 값으로 되돌아간다. 여기서는
 *    응답을 요청 키에 저장하고, 화면은 *현재* 키의 값만 읽으므로 늦게 온
 *    응답은 화면을 건드릴 수 없다.
 * 2. **이펙트 안에서 곧바로 `setLoading(true)`를 불렀다.** `react-hooks/
 *    set-state-in-effect`에 걸려 억제 주석을 달고 다녔다. 여기서는 loading이
 *    state가 아니라 "현재 키의 응답이 아직 없음"으로 계산되므로 setState 자체가
 *    없다.
 * 3. 이미 받아온 값을 다시 요청했다. 같은 키는 캐시에서 즉시 나온다.
 *
 * `fetcher`는 재요청 횟수를 인자로 받는다. 새로고침 버튼처럼 서버 캐시까지
 * 무시해야 하는 경우 `attempt > 0`으로 `forceRefresh`를 켜면 된다.
 *
 * 캐시는 이 컴포넌트가 살아 있는 동안만 유지된다(언마운트되면 사라진다).
 * 서버 상태를 앱 전역에서 공유·무효화하려면 TanStack Query가 필요하고,
 * 이 훅은 거기까지 가지 않는다.
 */
export function useAsyncData<T>(
  fetcher: (attempt: number) => Promise<T>,
  deps: readonly unknown[],
  { enabled = true, fallbackMessage = "불러오기 실패" }: Options = {},
): AsyncData<T> {
  const [attempt, setAttempt] = useState(0);
  // 정체성이 안정돼야 ref 핸들이나 자식 props로 넘겨도 매 렌더 갱신되지 않는다.
  const refetch = useCallback(() => setAttempt((n) => n + 1), []);
  const [cache, setCache] = useState<ReadonlyMap<string, Settled<T>>>(() => new Map());

  const key = `${attempt}|${JSON.stringify(deps)}`;
  const settled = cache.get(key);

  // fetcher는 렌더마다 새로 만들어지는 익명 함수라 이펙트 의존성에 넣을 수 없다.
  // 최신 것을 ref에 담아두고 이펙트는 키만 본다. 아래 이펙트보다 먼저 선언해야
  // 요청이 나가기 전에 갱신된다.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (!enabled || cache.has(key)) return;

    let active = true;
    const settle = (result: Settled<T>) => {
      if (!active) return;
      setCache((prev) => new Map(prev).set(key, result));
    };

    void fetcherRef
      .current(attempt)
      .then((data) => settle({ data, error: null }))
      .catch((error: unknown) =>
        settle({ data: null, error: errorMessage(error, fallbackMessage) }),
      );

    return () => {
      active = false;
    };
    // cache가 의존성에 있어서 응답이 저장될 때마다 이펙트가 다시 돈다. 그때는
    // 첫 줄의 `cache.has(key)`에서 바로 빠져나오므로 요청은 나가지 않는다.
    // 억제 주석을 쓰지 않으려고 감수하는 비용이고, 실제 비용은 Map 조회 한 번이다.
  }, [key, enabled, attempt, fallbackMessage, cache]);

  return {
    data: settled?.data ?? null,
    error: settled?.error ?? null,
    loading: enabled && settled === undefined,
    refetch,
  };
}
