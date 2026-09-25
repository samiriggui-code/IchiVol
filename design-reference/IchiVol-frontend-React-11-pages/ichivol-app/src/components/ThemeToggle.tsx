import { useEffect, useState } from 'react'
import { KeenIcon } from './KeenIcon'
import { getStoredTheme, toggleTheme, type ThemeMode } from '../lib/theme'

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>('light')

  useEffect(() => {
    setMode(getStoredTheme())
  }, [])

  return (
    <button
      type="button"
      className="camap-icon-btn"
      aria-label={mode === 'dark' ? 'Passer en thème clair' : 'Passer en thème sombre'}
      onClick={() => setMode(toggleTheme())}
    >
      <KeenIcon icon={mode === 'dark' ? 'sun' : 'moon'} style="outline" />
    </button>
  )
}
