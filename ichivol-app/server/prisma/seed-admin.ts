import { randomBytes } from 'node:crypto'
import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcrypt'

const db = new PrismaClient()

function generatePassword(): string {
  return randomBytes(18).toString('base64url')
}

async function main() {
  const email = process.argv[2]?.trim().toLowerCase()
  if (!email || !email.includes('@')) {
    console.error('Usage: npm run create-admin -- <email>')
    process.exit(1)
  }

  const password = generatePassword()
  const passwordHash = await bcrypt.hash(password, 12)

  const user = await db.user.upsert({
    where: { email },
    update: { passwordHash },
    create: { email, passwordHash, role: 'admin' },
  })

  console.log(`Admin prêt : ${user.email}`)
  console.log(`Mot de passe (affiché une seule fois) : ${password}`)
}

main()
  .catch((err) => {
    console.error(err)
    process.exit(1)
  })
  .finally(() => db.$disconnect())
