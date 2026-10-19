import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { ConfirmDialog } from './ConfirmDialog'
import { armKillSwitch, disarmKillSwitch, unlockDailyLoss } from '../lib/riskLock'
import { combineLocks, listActiveBooks, type CombinedLock } from '../lib/allBooks'
import type { PaperPortfolioRow } from '../lib/paper'

type KillCtx = {
  lock: CombinedLock | null
  refresh: () => void
  requestArm: () => void
  requestDisarm: () => void
  requestUnlockDaily: () => void
}

const Ctx = createContext<KillCtx | null>(null)

export function KillSwitchProvider({ children }: { children: ReactNode }) {
  // L'arrêt d'urgence vaut pour TOUS les portefeuilles paper actifs, pas seulement la baseline.
  const [lock, setLock] = useState<CombinedLock | null>(null)
  const [rows, setRows] = useState<PaperPortfolioRow[]>([])
  const [pending, setPending] = useState<'arm' | 'disarm' | 'unlock' | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    listActiveBooks()
      .then((list) => {
        setRows(list)
        setLock(combineLocks(list))
      })
      .catch(() => {
        /* engine offline */
      })
  }, [])

  useEffect(() => {
    refresh()
    const t = window.setInterval(refresh, 30_000)
    return () => window.clearInterval(t)
  }, [refresh])

  async function runConfirm() {
    if (!pending) return
    setBusy(true)
    setError(null)
    try {
      const list = rows.length > 0 ? rows : await listActiveBooks()
      const targets =
        pending === 'arm'
          ? list.filter((r) => !r.kill_switch_armed)
          : pending === 'disarm'
            ? list.filter((r) => r.kill_switch_armed)
            : list.filter((r) => r.daily_loss_locked)
      const results = await Promise.allSettled(
        targets.map((r) =>
          pending === 'arm'
            ? armKillSwitch(r.code)
            : pending === 'disarm'
              ? disarmKillSwitch(r.code)
              : unlockDailyLoss(r.code),
        ),
      )
      const failed = results
        .map((res, i) => (res.status === 'rejected' ? targets[i]!.label || targets[i]!.code : null))
        .filter((x): x is string => x != null)
      const fresh = await listActiveBooks().catch(() => list)
      setRows(fresh)
      setLock(combineLocks(fresh))
      if (failed.length > 0) throw new Error(`Échec sur : ${failed.join(', ')}`)
      setPending(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Échec')
    } finally {
      setBusy(false)
    }
  }

  const value = useMemo<KillCtx>(
    () => ({
      lock,
      refresh,
      requestArm: () => setPending('arm'),
      requestDisarm: () => setPending('disarm'),
      requestUnlockDaily: () => setPending('unlock'),
    }),
    [lock, refresh],
  )

  return (
    <Ctx.Provider value={value}>
      {children}
      {pending && (
        <ConfirmDialog
          title={
            pending === 'arm'
              ? 'Armer l’arrêt d’urgence ?'
              : pending === 'disarm'
                ? 'Rouvrir les entrées paper ?'
                : 'Déverrouiller la perte journalière ?'
          }
          body={
            pending === 'arm'
              ? `Aucune nouvelle position paper ne pourra s’ouvrir, sur aucun des ${lock?.book_count ?? ''} portefeuilles, tant que tu n’auras pas rouvert manuellement. Les sorties restent possibles.`.replace('des  ', 'des ')
              : pending === 'disarm'
                ? 'Réautorise les ouvertures paper sur tous les portefeuilles. Action humaine uniquement, rien ne se rouvre tout seul.'
                : 'Le verrou de perte du jour ne se lève pas à minuit. Confirme pour réautoriser les entrées sur les portefeuilles concernés.'
          }
          confirmLabel={
            pending === 'arm' ? 'Armer' : pending === 'disarm' ? 'Rouvrir' : 'Déverrouiller'
          }
          danger={pending === 'arm'}
          confirming={busy}
          error={error}
          onConfirm={() => void runConfirm()}
          onCancel={() => {
            if (!busy) {
              setPending(null)
              setError(null)
            }
          }}
        />
      )}
    </Ctx.Provider>
  )
}

function useKill() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('KillSwitchProvider missing')
  return ctx
}

export function KillSwitchButton() {
  const { lock, requestArm, requestDisarm } = useKill()
  const armed = Boolean(lock?.kill_switch_armed)
  return (
    <button
      type="button"
      className={`iv-estop dash-kill${armed ? ' is-armed' : ''}`}
      title={
        armed
          ? 'Arrêt d’urgence armé : cliquer pour rouvrir les entrées (confirmation)'
          : 'Arrêt d’urgence : bloque toute nouvelle entrée paper sur tous les portefeuilles. Les sorties restent possibles.'
      }
      onClick={() => (armed ? requestDisarm() : requestArm())}
    >
      <i aria-hidden />
      <span className="dash-kill-text">{armed ? 'Verrouillé' : 'Arrêt d’urgence'}</span>
    </button>
  )
}

export function KillLockBanner() {
  const { lock, requestUnlockDaily } = useKill()
  if (!lock?.entries_blocked) return null
  const dailyLocked = lock.daily_loss_locked
  const all = lock.blocked.length === lock.book_count
  return (
    <div className="dash-lock-banner" role="status">
      {/* Titre et liste dans le même bloc : sinon la liste passe à la ligne et commence par « : ». */}
      <span>
        <strong>{all ? 'Paper verrouillé' : 'Entrées bloquées sur une partie des portefeuilles'}</strong>
        {' : '}
        {lock.blocked
          .map(
            (b) =>
              `${b.label} (${b.kill && b.daily ? 'arrêt d’urgence + perte du jour' : b.kill ? 'arrêt d’urgence' : 'perte du jour'})`,
          )
          .join(', ')}
      </span>
      {dailyLocked && (
        <button type="button" className="iv-btn iv-btn--ghost iv-btn--sm" onClick={requestUnlockDaily}>
          Déverrouiller perte jour
        </button>
      )}
    </div>
  )
}
