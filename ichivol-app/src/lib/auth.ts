export interface AuthUser {
  id: string
  email: string
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { error?: string } | null
  return body?.error ?? `Erreur ${res.status}`
}

let meInflight: Promise<AuthUser | null> | null = null
let meCache: { user: AuthUser | null; at: number } | null = null
const ME_CACHE_MS = 5_000

export async function login(email: string, password: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) return { ok: false, error: await parseError(res) }
  meCache = null
  meInflight = null
  return { ok: true }
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  meCache = null
  meInflight = null
}

/** Session courante. Anonyme → `null` (HTTP 200, pas 401). */
export async function getMe(): Promise<AuthUser | null> {
  if (meCache && Date.now() - meCache.at < ME_CACHE_MS) return meCache.user
  if (meInflight) return meInflight

  meInflight = (async () => {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' })
      if (!res.ok) {
        meCache = { user: null, at: Date.now() }
        return null
      }
      const body = (await res.json()) as AuthUser | null
      const user = body && typeof body.id === 'string' ? body : null
      meCache = { user, at: Date.now() }
      return user
    } catch {
      meCache = { user: null, at: Date.now() }
      return null
    } finally {
      meInflight = null
    }
  })()

  return meInflight
}
