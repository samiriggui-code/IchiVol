/** Ouvre / ferme une fiche via `?fiche=` (push → back ferme). */

import { useCallback } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  normalizeFicheSymbol,
  parseFicheParam,
  parseFicheTab,
  serializeFicheParam,
  type FicheDecisionTab,
  type FicheRef,
} from './ficheDeepLink'

export function useFicheNav() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const fiche = parseFicheParam(searchParams.get('fiche'))
  const tab = parseFicheTab(searchParams.get('tab'))

  const openFiche = useCallback(
    (
      ref: FicheRef,
      opts?: { tab?: FicheDecisionTab; replace?: boolean; asOf?: string | null },
    ) => {
      const next = new URLSearchParams(location.search)
      next.set('fiche', serializeFicheParam(ref))
      if (opts?.tab && opts.tab !== 'synthese') next.set('tab', opts.tab)
      else next.delete('tab')
      if (opts?.asOf) next.set('asOf', opts.asOf)
      else next.delete('asOf')
      // Compat : retire l’ancien deep-link Opportunités
      next.delete('symbol')
      next.delete('open')
      navigate(
        { pathname: location.pathname, search: `?${next.toString()}` },
        { replace: opts?.replace === true },
      )
    },
    [location.pathname, location.search, navigate],
  )

  const openDecisionFiche = useCallback(
    (
      symbol: string,
      timeframe = '1h',
      opts?: { tab?: FicheDecisionTab; replace?: boolean; asOf?: string | null },
    ) => {
      const sym = normalizeFicheSymbol(symbol)
      if (!sym) return
      openFiche({ kind: 'decision', symbol: sym, timeframe }, opts)
    },
    [openFiche],
  )

  const openPositionFiche = useCallback(
    (id: string, opts?: { replace?: boolean }) => {
      const trimmed = id.trim()
      if (!trimmed) return
      openFiche({ kind: 'position', id: trimmed }, opts)
    },
    [openFiche],
  )

  const closeFiche = useCallback(
    (opts?: { replace?: boolean }) => {
      const next = new URLSearchParams(location.search)
      if (!next.has('fiche') && !next.has('tab') && !next.has('asOf')) return
      next.delete('fiche')
      next.delete('tab')
      next.delete('asOf')
      const search = next.toString()
      navigate(
        { pathname: location.pathname, search: search ? `?${search}` : '' },
        { replace: opts?.replace !== false },
      )
    },
    [location.pathname, location.search, navigate],
  )

  return {
    fiche,
    tab,
    asOf: searchParams.get('asOf'),
    openFiche,
    openDecisionFiche,
    openPositionFiche,
    closeFiche,
  }
}
