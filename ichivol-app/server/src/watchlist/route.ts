import type { Request, Response } from 'express'
import { writeAuditLog } from '../audit/log.js'
import { db } from '../db.js'

/** GET /api/watchlist */
export async function handleListWatchlist(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const rows = await db.watchlistItem.findMany({
    where: { userId: req.user.id },
    orderBy: { updatedAt: 'desc' },
  })
  res.json({ rows })
}

/** DELETE /api/watchlist/:symbol */
export async function handleDeleteWatchlistItem(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const symbol = (req.params.symbol ?? '').trim().toUpperCase()
  if (!symbol) {
    res.status(400).json({ error: 'symbol requis' })
    return
  }
  const existing = await db.watchlistItem.findFirst({
    where: { userId: req.user.id, symbol },
  })
  if (!existing) {
    res.status(404).json({ error: 'Symbole absent de la watchlist' })
    return
  }
  await db.watchlistItem.delete({ where: { id: existing.id } })
  await writeAuditLog({
    userId: req.user.id,
    action: 'watchlist.remove',
    meta: { symbol },
  })
  res.json({ ok: true, symbol })
}
