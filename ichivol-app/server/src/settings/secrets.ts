import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto'
import { config } from '../config.js'

function getKey(): Buffer {
  const secret = process.env.SETTINGS_SECRET || config.jwtSecret
  return scryptSync(secret, 'ichivol-settings-v1', 32)
}

/** Format: iv.tag.ciphertext (base64url). */
export function encryptSecret(plain: string): string {
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', getKey(), iv)
  const enc = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  return `${iv.toString('base64url')}.${tag.toString('base64url')}.${enc.toString('base64url')}`
}

export function decryptSecret(payload: string): string {
  const [ivB64, tagB64, dataB64] = payload.split('.')
  if (!ivB64 || !tagB64 || !dataB64) {
    throw new Error('Clé chiffrée invalide')
  }
  const decipher = createDecipheriv('aes-256-gcm', getKey(), Buffer.from(ivB64, 'base64url'))
  decipher.setAuthTag(Buffer.from(tagB64, 'base64url'))
  const dec = Buffer.concat([
    decipher.update(Buffer.from(dataB64, 'base64url')),
    decipher.final(),
  ])
  return dec.toString('utf8')
}
