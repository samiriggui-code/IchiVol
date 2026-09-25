const THEME_KEY = 'ichivol_theme'
export const THEME_CHANGE_EVENT = 'ichivol:theme'

export type ThemeMode = 'light' | 'dark'

export function getStoredTheme(): ThemeMode {
  const raw = localStorage.getItem(THEME_KEY)
  if (raw === 'light' || raw === 'dark') return raw
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle('dark', mode === 'dark')
  localStorage.setItem(THEME_KEY, mode)
  window.dispatchEvent(new Event(THEME_CHANGE_EVENT))
}

export function initTheme() {
  applyTheme(getStoredTheme())
}

export function toggleTheme(): ThemeMode {
  const next: ThemeMode = document.documentElement.classList.contains('dark') ? 'light' : 'dark'
  applyTheme(next)
  return next
}
