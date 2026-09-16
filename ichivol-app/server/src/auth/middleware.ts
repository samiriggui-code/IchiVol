import type { NextFunction, Request, Response } from 'express'
import { SESSION_COOKIE } from './cookie.js'
import { verifySession } from './jwt.js'

export interface AuthUser {
  id: string
  email: string
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: AuthUser | null
    }
  }
}

export function attachSession(req: Request, _res: Response, next: NextFunction): void {
  const token = req.cookies?.[SESSION_COOKIE] as string | undefined
  if (!token) {
    req.user = null
    next()
    return
  }
  const session = verifySession(token)
  req.user = session ? { id: session.sub, email: session.email } : null
  next()
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  next()
}
