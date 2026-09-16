import jwt from 'jsonwebtoken'
import { config } from '../config.js'

const EXPIRES_IN = '7d'

export interface SessionPayload {
  sub: string
  email: string
}

export function signSession(payload: SessionPayload): string {
  return jwt.sign(payload, config.jwtSecret, { algorithm: 'HS256', expiresIn: EXPIRES_IN })
}

export function verifySession(token: string): SessionPayload | null {
  try {
    const decoded = jwt.verify(token, config.jwtSecret, { algorithms: ['HS256'] })
    if (typeof decoded === 'string') return null
    if (typeof decoded.sub !== 'string' || typeof decoded.email !== 'string') return null
    return { sub: decoded.sub, email: decoded.email }
  } catch {
    return null
  }
}
