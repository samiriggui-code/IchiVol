/**
 * Barre sous un tableau : « 11–20 sur 143 », lignes par page (5, 10, 20, 50), page précédente / suivante.
 * À utiliser avec `usePaged`. Rien ne s'affiche quand la liste est vide.
 */

import { PAGE_SIZES, type PageSize, type Paged } from './usePaged'
import './TablePager.css'

export function TablePager<T>({ paged, label = 'lignes' }: { paged: Paged<T>; label?: string }) {
  const { page, pageCount, pageSize, total, start, setPage, setPageSize } = paged
  if (total === 0) return null
  const end = Math.min(start + pageSize, total)
  return (
    <div className="iv-pager" role="navigation" aria-label={`Pagination des ${label}`}>
      <span className="iv-pager-range">
        <b>
          {start + 1}–{end}
        </b>{' '}
        sur <b>{total}</b> {label}
      </span>
      <label className="iv-pager-size">
        <span>Par page</span>
        <select
          className="iv-input"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value) as PageSize)}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <div className="iv-pager-nav">
        <button
          type="button"
          className="iv-btn iv-btn--ghost iv-btn--sm"
          onClick={() => setPage(1)}
          disabled={page <= 1}
          aria-label="Première page"
        >
          «
        </button>
        <button
          type="button"
          className="iv-btn iv-btn--ghost iv-btn--sm"
          onClick={() => setPage(page - 1)}
          disabled={page <= 1}
          aria-label="Page précédente"
        >
          ‹
        </button>
        <span className="iv-pager-page">
          {page} / {pageCount}
        </span>
        <button
          type="button"
          className="iv-btn iv-btn--ghost iv-btn--sm"
          onClick={() => setPage(page + 1)}
          disabled={page >= pageCount}
          aria-label="Page suivante"
        >
          ›
        </button>
        <button
          type="button"
          className="iv-btn iv-btn--ghost iv-btn--sm"
          onClick={() => setPage(pageCount)}
          disabled={page >= pageCount}
          aria-label="Dernière page"
        >
          »
        </button>
      </div>
    </div>
  )
}
