# Audit — quoi ajouter à IchiVol (brief Claude)

> **Projet séparé de GSMS.** Pas de fusion de bases. Pas d’import monorepo `@crm/*`.  
> On s’inspire / on recopie des **fichiers auth utiles**, puis on les adapte dans `ichivol-app/server`.  
> La DB CRM (deals, Slack, companies) est **hors-sujet**.

> **MàJ 2026-09-15** — P1/P2 largement livrés (Prisma `users`/`settings`/`decisions`, auth JWT cookie, front branché).  
> Settings UI + clés LLM : livré (Cursor) — [`HANDOFF-SETTINGS-API-KEYS.md`](./HANDOFF-SETTINGS-API-KEYS.md).  
> **Concept agents (StrategyAgents ≠ Copilot)** — lire avant tout travail agents : [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md).

**État actuel (à ne pas refaire)**  
- Chart + screener + multi-source (Binance / Bybit / OKX)  
- Agent server Express + providers LLM + KB Academy (markdown) + citations  
- Landing + login UI — **auth réelle** (cookie httpOnly, plus de sessionStorage fake)  
- Postgres `ichivol_*` + tables `users` / `settings` / `decisions` — agent encore **stateless** (pas de mémoire décisions)  
- Shell UI densifié (Cursor) — Settings / Decisions / Backtests encore placeholders

---

## Règle non négociable

IchiVol ≠ GSMS.

- Pas de `DATABASE_URL` partagée avec GSMS/CRM  
- Pas de branchement `tenant-core` GSMS  
- Pas de copy-paste du `schema.prisma` CRM (1500+ lignes)  
- UI tokens GSMS = **style seulement** (déjà sur la landing)

---

## 1. Auth — quoi recopier depuis GSMS CRM

### Pattern à reprendre
- Credentials email + password  
- Pas de sign-up public  
- Allowlist admin (un seul user)  
- Session JWT / cookie httpOnly  
- Hash password (bcrypt)  
- Script seed `create-admin`

### Références lecture seule (GSMS)
- `gsms-platform/apps/crm/packages/auth/README.md`  
- `packages/auth/src/{cookies,next-auth-session,signed-in,env}.ts`  
- `packages/auth/scripts/create-user.ts`  
- Sign-in réel dans `apps/app` (NextAuth v4 credentials)  
- `@crm/auth` **vérifie** la session ; il ne la mint pas

### À NE PAS copier
- Slack / Gmail / Outlook OAuth  
- SSO SAML  
- Organization / Member multi-workspace CRM  
- API keys marketing  
- Tout couplage deals / companies / mailbox

### Adaptation IchiVol
- Auth sur le **server Express existant** (`ichivol-app/server`, port 8787)  
- Front Vite : `/login` → API ; remplacer `src/lib/auth.ts` (sessionStorage)  
- Routes cibles :
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Cookie httpOnly + même secret côté server ; `/app` refuse sans session

### Liste minimale à extraire / réécrire
1. Vérif JWT session + cookie name / secure flags  
2. Hash bcrypt + script create-admin  
3. Allowlist email (un seul admin)  
4. Routes login / logout / me  
5. Front branché sur l’API  

---

## 2. Base de données — Postgres / « Tenant DB » séparé

### Décisions
| Point | Décision |
|-------|----------|
| Principe | Base PostgreSQL **dédiée** `ichivol_*` — zéro partage avec GSMS |
| Connexion | `DATABASE_URL` propre (Docker local ou Hostinger Postgres). Prisma ou Drizzle **dans** `ichivol-app/server` uniquement |
| Tenant | IchiVol = **1 tenant / 1 admin** (singleton workspace). Pas le schéma Organization CRM |
| ORM | **Nouveau** schema IchiVol — pas le schema CRM |

### Clarification « Tenant DB »
Pour IchiVol : un Postgres isolé (ex. instance Hostinger / Docker nommé `ichivol`).  
Le « tenant » = workspace singleton admin.  
**Ne pas** brancher tenant-core GSMS ni la DB CRM Prisma existante.

### Tables à créer (schéma IchiVol)

| Table | Rôle |
|-------|------|
| `users` | Admin unique (email, passwordHash, role=admin) |
| `sessions` | Si sessions DB ; sinon JWT cookie suffit |
| `settings` | Prefs UI, sources actives, params Ichimoku/RVOL, thème |
| `watchlists` / symbols | Paires suivies, alertes futures |
| `market_snapshots` | Optionnel : cache klines/ticker (pas obligatoire MVP) |
| `decisions` | Décision user (symbol, tf, biais, RVOL, signal, note, statut) |
| `actions` | Actions orchestrées (journal, ignore, alerte, rescan…) + statut |
| `agent_threads` | Conversations agent liées à une décision / symbole |
| `agent_messages` | Messages + citations + mode (explain / research / trade_idea) |
| `agent_memory` | Faits persistés (préférences, leçons, « ne plus proposer X ») |
| `knowledge_docs` | Meta docs Academy (ou garder fichiers + table index) |
| `audit_log` | Qui a fait quoi (login, décision, action agent) |

---

## 3. Agent IA — mémoire & orchestration (exclusif IchiVol)

| Thème | Travail à faire |
|-------|-----------------|
| Aujourd’hui | Chat stateless : contexte live injecté par le front, KB markdown TF-IDF, pas de mémoire user |
| Mémoire décisions | À chaque « décider », écrire `decisions` + lier `agent_thread_id` ; rappeler les N dernières au prompt |
| Orchestration | Agent propose → user confirme → server exécute action **allowlistée** → `actions.status` |
| Scope exclusif | System prompt + tools : Ichimoku×RVOL, screener, Binance/Bybit/OKX, KB Academy — **refuser** CRM/GSMS/hors trading |
| Anti-hallu (garder) | Chiffres marché = payload front / fetch server ; citations = chunks KB uniquement |

### Boucle produit
1. **Comprendre** → signal + contexte marché + KB  
2. **Décider** → row `decisions` (+ note user)  
3. **Agir** → `actions` allowlist confirmées  
4. **Mémoriser** → `agent_memory` + historique threads  

### Actions allowlist (exemples)
- `save_decision` / `update_decision_status`  
- `pin_symbol` / `update_watchlist`  
- `set_alert_rule` (plus tard)  
- `refresh_screener` / `change_source`  

**Interdit MVP :** ordre broker, retrait fonds, appels GSMS.

Inspiration mémoire (lecture seule, **ne pas importer**) : modèles `AgentConversation*` dans le schema CRM GSMS.

---

## 4. Phases (ordre)

| Phase | Livrable | Statut |
|-------|----------|--------|
| **P0** | SPEC IchiVol Auth + DB + Agent mémoire (hors GSMS) — figer ce doc | ✅ |
| **P1** | Postgres dédié + schema minimal `users` / `settings` / `decisions` | ✅ |
| **P2** | Auth cookie serveur (pattern GSMS credentials, code adapté Express) | ✅ |
| **P6** | Settings UI + clés LLM (provider / model / key) — voir handoff | ✅ livré Cursor |
| **P3** | Persister threads/messages agent + brancher login réel | todo |
| **P4** | Tables `decisions` / `actions` + rappel mémoire dans `/api/agent/chat` | todo |
| **P5** | Orchestrateur d’actions allowlist + `audit_log` | todo |

---

## 5. Critères « terminé » (preuves)

- [ ] Login admin → cookie httpOnly ; `/app` refuse sans session  
- [ ] Postgres `ichivol_*` avec migrations ; seed admin  
- [ ] POST décision persistée ; reload page → historique visible  
- [ ] Agent chat rattache `thread_id` ; prompt voit décisions passées  
- [ ] Action proposée → confirm → row `actions` + `audit_log`  
- [ ] **Aucune** connexion réseau/DB vers GSMS  

---

## 6. Hors-scope de ce chantier

- Courtage / ordres réels  
- Multi-users / multi-tenant SaaS  
- Intégration monorepo GSMS  
- Refonte UI cockpit (tokens landing déjà OK)  

---

*Doc générée pour Claude — source unique de vérité pour le chantier Auth/DB/Agent. Le canvas Cursor n’est pas requis.*
