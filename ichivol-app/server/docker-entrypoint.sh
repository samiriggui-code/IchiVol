#!/bin/sh
set -eu
echo "[server] prisma migrate deploy"
npx prisma migrate deploy
if [ -n "${ADMIN_EMAIL:-}" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
  echo "[server] upsert admin ${ADMIN_EMAIL}"
  node -e "
const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcrypt');
const db = new PrismaClient();
(async () => {
  const email = process.env.ADMIN_EMAIL.trim().toLowerCase();
  const passwordHash = await bcrypt.hash(process.env.ADMIN_PASSWORD, 12);
  await db.user.upsert({
    where: { email },
    update: { passwordHash, role: 'admin' },
    create: { email, passwordHash, role: 'admin' },
  });
  console.log('[server] admin ready:', email);
  await db.\$disconnect();
})().catch(async (e) => { console.error(e); await db.\$disconnect(); process.exit(1); });
"
fi
exec "$@"
