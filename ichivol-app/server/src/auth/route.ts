import type { Request, Response } from 'express'
import { db } from '../db.js'
import { clearSessionCookie, setSessionCookie } from './cookie.js'
import { verifyPassword } from './hash.js'
import { signSession } from './jwt.js'

export async function handleLogin(req: Request, res: Response): Promise<void> {
  const { email, password } = req.body as { email?: unknown; password?: unknown }
  if (typeof email !== 'string' || typeof password !== 'string') {
    res.status(400).json({ error: 'email/password requis' })
    return
  }

  const user = await db.user.findUnique({ where: { email: email.trim().toLowerCase() } })
  if (!user || !(await verifyPassword(password, user.passwordHash))) {
    res.status(401).json({ error: 'Identifiants incorrects' })
    return
  }

  const token = signSession({ sub: user.id, email: user.email })
  setSessionCookie(res, token)
  res.json({ id: user.id, email: user.email })
}

export function handleLogout(_req: Request, res: Response): void {
  clearSessionCookie(res)
  res.json({ ok: true })
}

export function handleMe(req: Request, res: Response): void {
  // 200 + null = pas de 401 rouge dans la console navigateur quand anonyme
  res.status(200).json(req.user ?? null)
}
