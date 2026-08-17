import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useAsyncData } from "./useAsyncData";

/**
 * 이 훅이 존재하는 이유는 컴포넌트마다 복사돼 있던 fetch 패턴을 줄이는 것보다,
 * 그 패턴이 공통으로 갖고 있던 결함을 없애는 데 있다. 그래서 테스트도 결함 중심이다.
 *
 * Playwright에도 겹치는 검사가 있지만(`tests/data-fetching.spec.ts`) 저기서는 요청 수와
 * 화면으로만 볼 수 있어서 조건을 만들기 번거롭다. 여기서는 응답 시점을 직접 쥐고
 * 캐시 키·경쟁 조건·enabled 같은 경계를 몇 밀리초 만에 돌린다.
 */

/** 원하는 시점에 응답을 주기 위한 수동 제어 promise. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useAsyncData", () => {
  it("응답이 오기 전에는 loading이고, 오면 data가 채워진다", async () => {
    const { promise, resolve } = deferred<string>();
    const { result } = renderHook(() => useAsyncData(() => promise, ["k"]));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    await act(async () => {
      resolve("값");
      await promise;
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBe("값");
    expect(result.current.error).toBeNull();
  });

  it("deps가 같으면 다시 요청하지 않고, 바뀌면 그 키로 새로 요청한다", async () => {
    const fetcher = vi.fn(async (_attempt: number) => "값");
    const { result, rerender } = renderHook(({ id }) => useAsyncData(fetcher, [id]), {
      initialProps: { id: 1 },
    });

    await waitFor(() => expect(result.current.data).toBe("값"));
    expect(fetcher).toHaveBeenCalledTimes(1);

    // 같은 deps로 다시 렌더해도 요청은 늘지 않는다.
    rerender({ id: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);

    rerender({ id: 2 });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it("한 번 본 deps로 돌아오면 캐시에서 즉시 나온다", async () => {
    const fetcher = vi.fn(async (_attempt: number) => "값");
    const { result, rerender } = renderHook(({ id }) => useAsyncData(fetcher, [id]), {
      initialProps: { id: 1 },
    });

    await waitFor(() => expect(result.current.data).toBe("값"));
    rerender({ id: 2 });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    rerender({ id: 1 });

    // 로딩 상태를 거치지 않고 곧바로 값이 있어야 한다.
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBe("값");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("refetch는 캐시를 건너뛰고, fetcher에 늘어난 attempt를 넘긴다", async () => {
    const attempts: number[] = [];
    const fetcher = vi.fn(async (attempt: number) => {
      attempts.push(attempt);
      return "값";
    });
    const { result } = renderHook(() => useAsyncData(fetcher, ["k"]));

    await waitFor(() => expect(result.current.data).toBe("값"));
    act(() => result.current.refetch());
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    // 새로고침 버튼이 forceRefresh를 켤 수 있는 근거가 이 값이다.
    expect(attempts).toEqual([0, 1]);
  });

  it("enabled가 false면 요청하지 않고 loading도 아니다", async () => {
    const fetcher = vi.fn(async (_attempt: number) => "값");
    const { result, rerender } = renderHook(
      ({ on }) => useAsyncData(fetcher, ["k"], { enabled: on }),
      { initialProps: { on: false } },
    );

    expect(result.current.loading).toBe(false);
    expect(fetcher).not.toHaveBeenCalled();

    rerender({ on: true });
    await waitFor(() => expect(result.current.data).toBe("값"));
  });

  it("실패하면 error에 메시지가 담기고 예외는 새어 나가지 않는다", async () => {
    const { result } = renderHook(() =>
      useAsyncData(() => Promise.reject(new Error("백엔드 없음")), ["k"]),
    );

    await waitFor(() => expect(result.current.error).toBe("백엔드 없음"));
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("Error가 아닌 것이 던져지면 fallbackMessage를 쓴다", async () => {
    const { result } = renderHook(() =>
      useAsyncData(() => Promise.reject("문자열"), ["k"], { fallbackMessage: "불러오기 실패" }),
    );

    await waitFor(() => expect(result.current.error).toBe("불러오기 실패"));
  });

  it("늦게 온 응답은 그 사이 바뀐 deps의 화면을 덮지 않는다", async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const fetcher = vi.fn(async (_attempt: number) =>
      fetcher.mock.calls.length === 1 ? first.promise : second.promise,
    );

    const { result, rerender } = renderHook(({ id }) => useAsyncData(fetcher, [id]), {
      initialProps: { id: 1 },
    });

    // 1번 응답이 오기 전에 2번으로 넘어간다.
    rerender({ id: 2 });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

    await act(async () => {
      second.resolve("두번째");
      first.resolve("첫번째");
      await Promise.resolve();
    });

    expect(result.current.data).toBe("두번째");
  });

  it("언마운트된 뒤 응답이 와도 조용히 끝난다", async () => {
    const { promise, resolve } = deferred<string>();
    const { unmount } = renderHook(() => useAsyncData(() => promise, ["k"]));
    unmount();

    await act(async () => {
      resolve("값");
      await promise;
    });
    // 여기서 확인하는 것은 "터지지 않는다"까지다. React 18은 언마운트 뒤 setState를
    // 조용한 no-op으로 처리해서 경고를 내지 않으므로, cleanup 가드가 있든 없든
    // 밖에서 보이는 차이가 없다. console.error가 비었는지 보는 식의 검사는 가드를
    // 지워도 통과하므로 쓰지 않는다.
  });
});
