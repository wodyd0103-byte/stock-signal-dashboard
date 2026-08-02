"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

/** 라이트/다크 토글. localStorage 저장, html.dark 클래스 제어. */
export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
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
