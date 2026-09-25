/**
 * Chantier 2 E1 — markdown skills loaded on demand (Eve pattern).
 * Procedural context only — never live market numbers.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const SKILLS_DIR = dirname(fileURLToPath(import.meta.url))

/** Soft cap so skills never blow the system prompt. */
export const MAX_SKILLS_CHARS = 8_000

const CACHE = new Map<string, string>()

export const KNOWN_SKILLS = [
  'ichimoku',
  'rvol',
  'structure',
  'risk',
  'mtf',
  'mission',
] as const

export type SkillName = (typeof KNOWN_SKILLS)[number]

export function listSkillFiles(): string[] {
  return readdirSync(SKILLS_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.replace(/\.md$/, ''))
}

function readSkillFile(name: string): string | null {
  const key = name.trim().toLowerCase()
  if (CACHE.has(key)) return CACHE.get(key)!
  try {
    const text = readFileSync(join(SKILLS_DIR, `${key}.md`), 'utf8').trim()
    CACHE.set(key, text)
    return text
  } catch {
    return null
  }
}

/**
 * Load named skills; unknown names skipped. Total text truncated to MAX_SKILLS_CHARS.
 */
export function loadSkills(names: string[]): { names: string[]; block: string | null } {
  const loaded: string[] = []
  const parts: string[] = []
  let used = 0

  for (const raw of names) {
    const name = raw.trim().toLowerCase()
    if (!name || loaded.includes(name)) continue
    const body = readSkillFile(name)
    if (!body) continue
    const chunk = `### skill:${name}\n${body}`
    if (used + chunk.length + 2 > MAX_SKILLS_CHARS) break
    loaded.push(name)
    parts.push(chunk)
    used += chunk.length + 2
  }

  if (parts.length === 0) return { names: [], block: null }
  return {
    names: loaded,
    block: `--- SKILLS (procédures on-demand ; pas de chiffres live) ---\n${parts.join('\n\n')}`,
  }
}

/** Default skill set for a 1-symbol watch / recheck mission. */
export function defaultMissionSkills(kind: string): string[] {
  if (kind === 'recheck' || kind === 'mission') {
    return ['mission', 'ichimoku', 'rvol', 'risk']
  }
  return ['mission']
}

/** Resolve skills from task payload.skills or defaults for kind. */
export function resolveSkillsForTask(
  kind: string,
  payload: Record<string, unknown> | null | undefined,
): string[] {
  const fromPayload = payload?.skills
  if (Array.isArray(fromPayload)) {
    const names = fromPayload.filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
    if (names.length > 0) return names.map((s) => s.trim().toLowerCase())
  }
  return defaultMissionSkills(kind)
}
