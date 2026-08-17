import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useAsyncAction } from "./useAsyncAction";

/**
 * 클릭이 시작하는 요청. 조회 훅과 달리 캐시가 없어야 하고, 호출부가 결과를 받아
 * 이어서 처리해야 한다(예: 성공했을 때만 목록을 다시 읽는다).
 */
describe("useAsyncAction", () => {
  it("성공하면 결과를 그대로 돌려주고 pending이 내려간다", async () => {
    const { result } = renderHook(() => useAsyncAction(async (n: number) => n * 2));

    expect(result.current.pending).toBe(false);

    let returned: number | null = null;
    await act(async () => {
      returned = await result.current.run(21);
    });

    expect(returned).toBe(42);
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("실패하면 null을 돌려주고 error에 메시지를 담는다 — 예외는 던지지 않는다", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async () => {
        throw new Error("추가 실패");
      }),
    );

    let returned: unknown = "touched";
    await act(async () => {
      // 여기서 throw하면 호출부(폼 submit 핸들러)가 전부 try/catch를 다시 갖게 된다.
      returned = await result.current.run();
    });

    expect(returned).toBeNull();
    expect(result.current.error).toBe("추가 실패");
    expect(result.current.pending).toBe(false);
  });

  it("Error가 아닌 것이 던져지면 fallbackMessage를 쓴다", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(() => Promise.reject("문자열"), { fallbackMessage: "요청 실패" }),
    );

    await act(async () => {
      await result.current.run();
    });

    expect(result.current.error).toBe("요청 실패");
  });

  it("같은 버튼을 두 번 누르면 두 번 실행한다 — 캐시하지 않는다", async () => {
    const action = vi.fn(async () => "ok");
    const { result } = renderHook(() => useAsyncAction(action));

    await act(async () => {
      await result.current.run();
      await result.current.run();
    });

    expect(action).toHaveBeenCalledTimes(2);
  });

  it("다음 실행은 이전 실패 메시지를 지우고 시작한다", async () => {
    let shouldFail = true;
    const { result } = renderHook(() =>
      useAsyncAction(async () => {
        if (shouldFail) throw new Error("첫 시도 실패");
        return "ok";
      }),
    );

    await act(async () => {
      await result.current.run();
    });
    expect(result.current.error).toBe("첫 시도 실패");

    shouldFail = false;
    await act(async () => {
      await result.current.run();
    });
    expect(result.current.error).toBeNull();
  });

  it("clearError로 직접 지울 수 있다", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async () => {
        throw new Error("실패");
      }),
    );

    await act(async () => {
      await result.current.run();
    });
    await waitFor(() => expect(result.current.error).toBe("실패"));

    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
  });

  it("run의 정체성은 렌더가 바뀌어도 유지된다", () => {
    const { result, rerender } = renderHook(({ n }) => useAsyncAction(async () => n), {
      initialProps: { n: 1 },
    });

    const first = result.current.run;
    rerender({ n: 2 });

    // props로 넘겨도 자식이 매 렌더 다시 그려지지 않게 하려는 것.
    expect(result.current.run).toBe(first);
  });

  it("언마운트 뒤에 실패가 도착해도 예외가 새어 나오지 않는다", async () => {
    let settle!: () => void;
    const gate = new Promise<void>((res) => {
      settle = res;
    });

    const { result, unmount } = renderHook(() =>
      useAsyncAction(async () => {
        await gate;
        throw new Error("늦은 실패");
      }),
    );

    let pendingRun!: Promise<unknown>;
    act(() => {
      pendingRun = result.current.run();
    });
    unmount();

    settle();

    // 훅 안의 mountedRef 가드가 하는 일(언마운트 뒤 setState 생략)은 React 18에서
    // 밖으로 관측되지 않는다 — 그 시점 setState는 조용한 no-op이라 가드를 지워도
    // 동작이 같다. 그래서 여기서는 관측 가능한 것만 단언한다: run()이 reject되지
    // 않고 null로 끝난다.
    await expect(pendingRun).resolves.toBeNull();
  });
});
