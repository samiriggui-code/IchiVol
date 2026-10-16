/**
 * Hôte shell des fiches deep-link (`?fiche=`).
 * Back / fermeture → retire le param. Agent = FicheAgent ; decision/position/run = hors scope ici
 * (Opportunités / Portefeuille gardent leurs dialogs page tant que non migrés).
 */

import { useCallback } from 'react'
import { useFicheNav } from '../../lib/useFicheNav'
import { FicheAgent } from './FicheAgent'

export function FicheHost() {
  const { fiche, closeFiche } = useFicheNav()

  const handleClose = useCallback(() => {
    closeFiche({ replace: true })
  }, [closeFiche])

  if (!fiche || fiche.kind !== 'agent') return null

  return <FicheAgent key={fiche.id} agentId={fiche.id} onClose={handleClose} />
}
