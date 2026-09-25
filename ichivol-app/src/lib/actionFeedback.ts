/**
 * Feedback commun après register / open / close / archive.
 * Notice maquette vert/rouge + événement de refresh Portfolio / Journal / Opérations.
 */

export type DataRefreshScope = 'portfolio' | 'journal' | 'operations' | 'screener' | 'all'

export type ActionNotice = {
  ok: boolean
  text: string
  at: number
}

export const DATA_REFRESH_EVENT = 'ichivol:data-refresh'
export const ACTION_NOTICE_EVENT = 'ichivol:action-notice'

/** Couleurs notice alignées Opportunités (#109) — maquette green/red. */
export function actionNoticeStyle(ok: boolean): Record<string, string> {
  return ok
    ? {
        background: '#e7f3ee',
        borderColor: '#c5ddd4',
        color: '#168579',
      }
    : {
        background: '#f8ecea',
        borderColor: '#e8cfc9',
        color: '#c8412f',
      }
}

export function pushActionNotice(ok: boolean, text: string): ActionNotice {
  const notice: ActionNotice = { ok, text, at: Date.now() }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(ACTION_NOTICE_EVENT, { detail: notice }))
  }
  return notice
}

export function emitDataRefresh(scopes: DataRefreshScope[] = ['all']): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(DATA_REFRESH_EVENT, { detail: { scopes } }))
}

export function afterPaperOrJournalAction(
  ok: boolean,
  text: string,
  scopes: DataRefreshScope[] = ['portfolio', 'journal', 'operations', 'screener'],
): void {
  pushActionNotice(ok, text)
  if (ok) emitDataRefresh(scopes)
}
