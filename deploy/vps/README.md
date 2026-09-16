# IchiVol — déploiement VPS (Docker + Traefik)

**FQDN :** https://ichivol.global-it-ss.com  
**Smoke :** http://187.77.166.124:3060  
**Repo :** https://github.com/samiriggui-code/IchiVol

## Stack

| Service | Rôle | Port interne |
|---------|------|--------------|
| `postgres` | DB app (`ichivol`) + engine (`ichivol_engine`) | 5432 |
| `engine` | FastAPI Ichimoku×RVOL | 8000 |
| `server` | Express API / auth / agent | 8787 |
| `web` | Nginx (SPA + proxies marché) | 80 → host **3060** |

Traefik (déjà sur le VPS) termine TLS via labels `Host(\`ichivol.global-it-ss.com\`)`.

## Prérequis VPS

- Docker + Compose
- Traefik avec `letsencrypt` (comme `grace.global-it-ss.com`)
- DNS A `ichivol` → `187.77.166.124` (déjà en place)

## Lancer

```bash
git clone https://github.com/samiriggui-code/IchiVol.git /opt/ichivol
cd /opt/ichivol
cp deploy/vps/.env.example deploy/vps/.env
# éditer JWT_SECRET, POSTGRES_PASSWORD, ADMIN_*, clés LLM
docker compose --env-file deploy/vps/.env up -d --build
```

Via Hostinger Docker Manager : projet `ichivol`, compose = racine du repo GitHub, variables = contenu de `.env`.

## Admin

Au premier boot, si `ADMIN_EMAIL` + `ADMIN_PASSWORD` sont définis, le serveur upsert l’admin.

## Santé

- Front : `/`
- API : `/api/health`
- Engine (via API auth) : `/api/engine/health`
