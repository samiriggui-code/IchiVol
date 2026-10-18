/** Clé renouvelée avec le thème premium : l'ancienne mémorisait « light » par défaut pour tout le monde. */
const THEME_KEY = 'ichivol_theme_premium'
export const THEME_CHANGE_EVENT = 'ichivol:theme'

export type ThemeMode = 'light' | 'dark'

/**
 * Défaut = sombre (thème premium). Le clair reste disponible via le ThemeToggle.
 * Ne pas suivre prefers-color-scheme : le poste de trading est pensé sombre.
 */
export function getStoredTheme(): ThemeMode {
  const raw = localStorage.getItem(THEME_KEY)
  if (raw === 'light' || raw === 'dark') return raw
  return 'dark'
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle('dark', mode === 'dark')
  localStorage.setItem(THEME_KEY, mode)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', mode === 'dark' ? '#05080c' : '#f3f5f8')
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
