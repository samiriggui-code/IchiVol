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
import {
  armKillSwitch,
  disarmKillSwitch,
  getRiskLock,
  unlockDailyLoss,
  type RiskLockState,
} from '../lib/riskLock'

type KillCtx = {
  lock: RiskLockState | null
  refresh: () => void
  requestArm: () => void
  requestDisarm: () => void
  requestUnlockDaily: () => void
}

const Ctx = createContext<KillCtx | null>(null)

export function KillSwitchProvider({ children }: { children: ReactNode }) {
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
      let next: RiskLockState
      if (pending === 'arm') next = await armKillSwitch()
      else if (pending === 'disarm') next = await disarmKillSwitch()
      else next = await unlockDailyLoss()
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
              ? 'Armer le kill switch ?'
              : pending === 'disarm'
                ? 'Rouvrir les entrées paper ?'
                : 'Déverrouiller la perte journalière ?'
          }
          body={
            pending === 'arm'
              ? 'Aucune nouvelle position paper ne pourra s’ouvrir tant que tu n’auras pas désarmé manuellement. Les sorties restent possibles.'
              : pending === 'disarm'
                ? 'Réautorise les ouvertures paper. Action humaine uniquement — aucun auto-lift.'
                : 'Le verrou perte jour ne se lève pas à minuit. Confirme pour réautoriser les entrées.'
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
      className={`dash-kill${armed ? ' is-armed' : ''}`}
      title={
        armed
          ? 'Kill switch armé — cliquer pour rouvrir (confirmation)'
          : 'Arrêt d’urgence — bloque les nouvelles entrées paper'
      }
      onClick={() => (armed ? requestDisarm() : requestArm())}
    >
      {armed ? 'Verrouillé' : 'Arrêt d’urgence'}
    </button>
  )
}

export function KillLockBanner() {
  const { lock, requestUnlockDaily } = useKill()
  if (!lock?.entries_blocked) return null
  const armed = lock.kill_switch_armed
  const dailyLocked = lock.daily_loss_locked
  return (
    <div className="dash-lock-banner" role="status">
      <strong>Paper verrouillé</strong>
      <span>
        {armed && dailyLocked
          ? ' — kill switch + perte journalière'
          : armed
            ? ' — kill switch (entrées bloquées)'
            : ' — perte journalière (entrées bloquées)'}
      </span>
      {dailyLocked && (
        <button type="button" className="ghost" onClick={requestUnlockDaily}>
          Déverrouiller perte jour
        </button>
      )}
    </div>
  )
}
