"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

/**
 * html.dark 클래스가 곧 소스 오브 트루스다. layout.tsx의 인라인 스크립트가 하이드레이션
 * 전에 클래스를 붙이므로, 컴포넌트는 그 클래스를 구독하기만 하면 된다. 별도 state를 두고
 * 이펙트에서 맞추면 하이드레이션 직후 한 프레임 동안 아이콘이 어긋난다.
 */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

function getSnapshot() {
  return document.documentElement.classList.contains("dark");
}

/** 서버 렌더 시점에는 DOM이 없다. 라이트로 그린 뒤 클래스가 있으면 곧바로 갱신된다. */
function getServerSnapshot() {
  return false;
}

/** 라이트/다크 토글. localStorage 저장, html.dark 클래스 제어. */
export default function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* noop */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-xl p-2.5 text-muted transition-colors hover:bg-surface hover:text-ink"
      aria-label={dark ? "라이트 모드" : "다크 모드"}
      title={dark ? "라이트 모드" : "다크 모드"}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
