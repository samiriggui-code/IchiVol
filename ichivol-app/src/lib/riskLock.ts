/** T13c — kill switch / daily loss lock client. */

export type RiskLockState = {
  portfolio_code?: string
  kill_switch_armed: boolean
  kill_switch_armed_at: string | null
  daily_loss_locked: boolean
  daily_loss_locked_at: string | null
  entries_blocked: boolean
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

const CODE = 'ICHIVOL_BASELINE_V1'

export async function getRiskLock(code = CODE): Promise<RiskLockState> {
  const res = await fetch(`/api/engine/paper/portfolios/${encodeURIComponent(code)}/risk-lock`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as RiskLockState
}

export async function armKillSwitch(code = CODE): Promise<RiskLockState> {
  const res = await fetch(
    `/api/engine/paper/portfolios/${encodeURIComponent(code)}/kill-switch/arm`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: true }),
    },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as RiskLockState
}

export async function disarmKillSwitch(code = CODE): Promise<RiskLockState> {
  const res = await fetch(
    `/api/engine/paper/portfolios/${encodeURIComponent(code)}/kill-switch/disarm`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: true }),
    },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as RiskLockState
}

export async function unlockDailyLoss(code = CODE): Promise<RiskLockState> {
  const res = await fetch(
    `/api/engine/paper/portfolios/${encodeURIComponent(code)}/daily-loss/unlock`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: true }),
    },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as RiskLockState
}
