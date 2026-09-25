/** T0-NOTIF — browser Web Push helpers (front). */

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

export type PushSupportStatus =
  | { ok: true }
  | {
      ok: false
      reason: 'unsupported' | 'denied' | 'not_standalone' | 'server' | 'error'
      message: string
    }

export function detectPushSupport(): PushSupportStatus {
  if (typeof window === 'undefined') {
    return { ok: false, reason: 'unsupported', message: 'Environnement hors navigateur.' }
  }
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    return {
      ok: false,
      reason: 'unsupported',
      message:
        'Ce navigateur ne supporte pas le Web Push. Sur iPhone : Safari 16.4+ et « Ajouter à l’écran d’accueil » (PWA).',
    }
  }
  // iOS only allows push in standalone PWA
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
  const standalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Boolean((navigator as any).standalone)
  if (isIOS && !standalone) {
    return {
      ok: false,
      reason: 'not_standalone',
      message:
        'Sur iOS, ouvre IchiVol via « Ajouter à l’écran d’accueil » (PWA) pour activer les alertes push.',
    }
  }
  if (Notification.permission === 'denied') {
    return {
      ok: false,
      reason: 'denied',
      message: 'Permission notifications refusée — réactive-la dans les réglages du navigateur.',
    }
  }
  return { ok: true }
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { error?: string; message?: string } | null
  return body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export async function fetchVapidPublicKey(): Promise<string> {
  const res = await fetch('/api/notifications/push-vapid-public', {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { publicKey: string }
  return body.publicKey
}

export async function enablePushAlerts(): Promise<PushSupportStatus> {
  const support = detectPushSupport()
  if (!support.ok) return support

  try {
    const reg = await navigator.serviceWorker.register('/sw.js')
    await navigator.serviceWorker.ready

    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      return {
        ok: false,
        reason: 'denied',
        message: 'Permission notifications refusée.',
      }
    }

    const publicKey = await fetchVapidPublicKey()
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
    })
    const json = sub.toJSON()
    const res = await fetch('/api/notifications/push-subscribe', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint: json.endpoint,
        keys: json.keys,
      }),
    })
    if (!res.ok) throw new Error(await parseError(res))
    return { ok: true }
  } catch (err: unknown) {
    return {
      ok: false,
      reason: 'error',
      message: err instanceof Error ? err.message : String(err),
    }
  }
}

export async function disablePushAlerts(): Promise<void> {
  if (!('serviceWorker' in navigator)) return
  const reg = await navigator.serviceWorker.getRegistration()
  const sub = await reg?.pushManager.getSubscription()
  if (sub) {
    const endpoint = sub.endpoint
    await sub.unsubscribe().catch(() => undefined)
    await fetch('/api/notifications/push-subscribe', {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint }),
    }).catch(() => undefined)
  }
}
