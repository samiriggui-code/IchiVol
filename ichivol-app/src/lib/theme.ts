const THEME_KEY = 'ichivol_theme'
export const THEME_CHANGE_EVENT = 'ichivol:theme'

export type ThemeMode = 'light' | 'dark'

/**
 * Défaut = light (maquette). Ne pas suivre prefers-color-scheme :
 * sinon iOS sombre → shell dark + cartes maquette claires = thème farci.
 */
export function getStoredTheme(): ThemeMode {
  const raw = localStorage.getItem(THEME_KEY)
  if (raw === 'light' || raw === 'dark') return raw
  return 'light'
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle('dark', mode === 'dark')
  localStorage.setItem(THEME_KEY, mode)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', mode === 'dark' ? '#12151a' : '#faf8f5')
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
