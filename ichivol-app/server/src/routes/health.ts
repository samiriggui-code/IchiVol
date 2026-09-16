import type { Request, Response } from 'express'
import { config } from '../config.js'

export function handleHealth(_req: Request, res: Response): void {
  res.json({ ok: true, provider: config.llmProvider, model: config.llmModel })
}
