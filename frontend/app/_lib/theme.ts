import { useSyncExternalStore } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "fairhire:theme";
const listeners = new Set<() => void>();

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
}

export function setTheme(t: Theme) {
  try {
    if (t === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, t);
  } catch { /* private mode */ }
  if (t === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = t;
  listeners.forEach(l => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => { listeners.delete(cb); window.removeEventListener("storage", cb); };
}

/** The saved choice. "system" means no override: the page follows the OS setting. */
export const useTheme = (): Theme => useSyncExternalStore(subscribe, read, () => "system");
