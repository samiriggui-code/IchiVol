# Handoff — Copilot deep-link + prompts (front only)

> **Pour :** Claude — **rien à faire engine** pour ce lot  
> **De :** Cursor  
> **Date :** 2026-09-16

## Décision UX

Les CTA « Expliquer » / « Écart portes » **ne ouvrent plus la bulle**.  
Ils **redirigent vers `/app/agent`** avec un **prompt métier déjà formulé** + auto-send.

## Front livré

- `src/lib/copilotPrompts.ts` — templates `explain_decision`, `compare_gates`, `explain_signal`, `trade_idea`, `research`
- `src/lib/useCopilotNav.ts` — `queueLaunch` + `navigate('/app/agent')`
- `agentSession.queueLaunch` / `launch`
- Pages : Décisions, Journal, Watchlist
- Bulle = raccourci vers `/app/agent` uniquement

## Pas de tuyauterie Claude

Pas de nouvel endpoint. Le Copilot serveur consomme déjà `decision` / `live` dans `POST /api/agent/chat`.

## Suite possible (Claude plus tard, si besoin)

- Persister le « launch prompt » dans `agent_threads` (titre = 1ʳᵉ question)
- Skill `compare_gates` côté server si on veut un mode dédié (aujourd’hui = `explain_decision` + prompt)

Sinon Cursor suffit.
