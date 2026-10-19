/**
 * Pagination des tableaux : jamais 200 lignes d'un coup. 5, 10, 20 ou 50 lignes par page, 10 par défaut.
 * Le choix de taille est retenu par tableau (clé `id`) dans le navigateur ; la page revient à 1 quand la liste change
 * de taille (filtre, recherche, rechargement).
 */

import { useEffect, useMemo, useState } from 'react'

export const PAGE_SIZES = [5, 10, 20, 50] as const
export type PageSize = (typeof PAGE_SIZES)[number]

const DEFAULT_SIZE: PageSize = 10
const STORAGE_PREFIX = 'ichivol_page_size:'

function readSize(id: string, fallback: PageSize): PageSize {
  try {
    const v = Number(localStorage.getItem(STORAGE_PREFIX + id))
    return (PAGE_SIZES as readonly number[]).includes(v) ? (v as PageSize) : fallback
  } catch {
    return fallback
  }
}

export type Paged<T> = {
  /** Les lignes de la page affichée. */
  rows: T[]
  page: number
  pageCount: number
  pageSize: PageSize
  total: number
  /** Index (base 0) de la première ligne affichée. */
  start: number
  setPage: (page: number) => void
  setPageSize: (size: PageSize) => void
}

export function usePaged<T>(all: readonly T[], id: string, initialSize: PageSize = DEFAULT_SIZE): Paged<T> {
  const [pageSize, setSize] = useState<PageSize>(() => readSize(id, initialSize))
  const [page, setPageState] = useState(1)
  const total = all.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  // Nouvelle liste (filtre, recherche…) : retour à la première page.
  useEffect(() => {
    setPageState(1)
  }, [total])

  const current = Math.min(page, pageCount)
  const start = (current - 1) * pageSize
  const rows = useMemo(() => all.slice(start, start + pageSize), [all, start, pageSize])

  return {
    rows,
    page: current,
    pageCount,
    pageSize,
    total,
    start,
    setPage: (p) => setPageState(Math.min(Math.max(1, p), pageCount)),
    setPageSize: (size) => {
      setSize(size)
      setPageState(1)
      try {
        localStorage.setItem(STORAGE_PREFIX + id, String(size))
      } catch {
        /* stockage indisponible : le choix vaut pour la session */
      }
    },
  }
}
