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
import { armKillSwitch, disarmKillSwitch, getRiskLock, unlockDailyLoss, type RiskLockState } from '../lib/riskLock'

type KillCtx = {
  lock: RiskLockState | null
  refresh: () => void
  requestArm: () => void
  requestDisarm: () => void
  requestUnlockDaily: () => void
}

const Ctx = createContext<KillCtx | null>(null)

export function KillSwitchProvider({ children }: { children: ReactNode }) {
  // Un seul portefeuille paper (ICHIVOL_MAIN_V1) : l'arrêt d'urgence porte sur lui.
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [pending, setPending] = useState<'arm' | 'disarm' | 'unlock' | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    getRiskLock()
      .then(setLock)
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
      const next =
        pending === 'arm' ? await armKillSwitch() : pending === 'disarm' ? await disarmKillSwitch() : await unlockDailyLoss()
      setLock(next)
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
              ? 'Aucune nouvelle position paper ne pourra s’ouvrir tant que tu n’auras pas rouvert manuellement. Les sorties restent possibles.'
              : pending === 'disarm'
                ? 'Réautorise les ouvertures paper. Action humaine uniquement, rien ne se rouvre tout seul.'
                : 'Le verrou de perte du jour ne se lève pas à minuit. Confirme pour réautoriser les entrées.'
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
          : 'Arrêt d’urgence : bloque toute nouvelle entrée paper. Les sorties restent possibles.'
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
  const why =
    lock.kill_switch_armed && dailyLocked
      ? 'arrêt d’urgence + perte du jour'
      : lock.kill_switch_armed
        ? 'arrêt d’urgence'
        : dailyLocked
          ? 'perte du jour'
          : 'entrées bloquées par le moteur'
  return (
    <div className="dash-lock-banner" role="status">
      {/* Titre et motif dans le même bloc : sinon le motif passe à la ligne et commence par « : ». */}
      <span>
        <strong>Paper verrouillé</strong>
        {` : ${why}`}
      </span>
      {dailyLocked && (
        <button type="button" className="iv-btn iv-btn--ghost iv-btn--sm" onClick={requestUnlockDaily}>
          Déverrouiller perte jour
        </button>
      )}
    </div>
  )
}
