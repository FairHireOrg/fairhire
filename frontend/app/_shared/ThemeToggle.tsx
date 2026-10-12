"use client";
import { Desktop, Moon, Sun } from "@phosphor-icons/react";
import { setTheme, useTheme, type Theme } from "../_lib/theme";

const OPTIONS: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "system", label: "System theme", Icon: Desktop },
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "dark", label: "Dark theme", Icon: Moon },
];

export function ThemeToggle() {
  const theme = useTheme();
  return (
    <div className="theme-toggle" role="radiogroup" aria-label="Theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value} type="button" role="radio" aria-checked={theme === value} aria-label={label} title={label}
          onClick={() => setTheme(value)}
        >
          <Icon size={16} weight={theme === value ? "fill" : "regular"} />
        </button>
      ))}
    </div>
  );
}
