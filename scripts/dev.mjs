#!/usr/bin/env node
/**
 * Launches the three dev processes IchiVol needs (Vite SPA, Express server,
 * Python engine) from one command, with prefixed/colored output, and kills
 * all three on Ctrl+C. No new npm dependency (no concurrently/turborepo) --
 * just node:child_process, since this is one fixed set of long-running
 * processes, not a build graph.
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const IS_WIN = process.platform === 'win32'

const ENGINE_DIR = path.join(ROOT, 'ichivol-app', 'engine')
const ENGINE_PYTHON = path.join(
  ENGINE_DIR,
  '.venv',
  IS_WIN ? 'Scripts' : 'bin',
  IS_WIN ? 'python.exe' : 'python',
)

const COLORS = { vite: '\x1b[36m', server: '\x1b[35m', engine: '\x1b[33m', reset: '\x1b[0m' }

const PROCESSES = [
  {
    name: 'vite',
    cwd: path.join(ROOT, 'ichivol-app'),
    command: IS_WIN ? 'npm.cmd' : 'npm',
    args: ['run', 'dev'],
  },
  {
    name: 'server',
    cwd: path.join(ROOT, 'ichivol-app', 'server'),
    command: IS_WIN ? 'npm.cmd' : 'npm',
    args: ['run', 'dev'],
  },
  {
    name: 'engine',
    cwd: ENGINE_DIR,
    command: ENGINE_PYTHON,
    args: ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'],
    check: () => {
      if (!existsSync(ENGINE_PYTHON)) {
        console.error(
          `[engine] venv not found at ${ENGINE_PYTHON}\n` +
            `[engine] run: cd ichivol-app/engine && python -m venv .venv && ` +
            `.venv/${IS_WIN ? 'Scripts' : 'bin'}/pip install -r requirements.txt`,
        )
        return false
      }
      return true
    },
  },
]

function prefixed(name, chunk) {
  const color = COLORS[name] ?? ''
  const lines = chunk.toString().split('\n').filter(Boolean)
  for (const line of lines) {
    process.stdout.write(`${color}[${name}]${COLORS.reset} ${line}\n`)
  }
}

const children = []

for (const proc of PROCESSES) {
  if (proc.check && !proc.check()) continue

  const child = spawn(proc.command, proc.args, { cwd: proc.cwd, shell: IS_WIN })
  children.push(child)

  child.stdout?.on('data', (d) => prefixed(proc.name, d))
  child.stderr?.on('data', (d) => prefixed(proc.name, d))
  child.on('exit', (code) => {
    prefixed(proc.name, `exited with code ${code}`)
  })
}

function shutdown() {
  for (const child of children) {
    if (!child.killed) child.kill()
  }
  process.exit(0)
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
