# mt5-bridge — MT5 comme labo, jamais comme cœur

Service Docker **isolé**, jamais démarré par un `docker compose up -d` normal
(`profiles: ["mt5"]` dans le `docker-compose.yml` racine). Contient tout ce
qui dépend de Wine/Windows/MetaTrader5 — l'engine IchiVol (Linux, FastAPI)
ne parle qu'à ce service via HTTP (`app/market_data/mt5.py`) et ne sait
jamais que Wine existe derrière.

```
engine (Linux)  --HTTP-->  mt5-bridge (ce service)
                              ├── bridge_server.py (FastAPI, Linux natif)
                              ├── mt5linux (client RPyC, Linux natif)
                              └── Wine
                                   ├── Python Windows (pip: MetaTrader5, mt5linux server)
                                   └── terminal MetaTrader 5 (connecté au broker)
```

## ⚠️ Statut honnête

Ce service a été écrit sans pouvoir être **buildé ni lancé** dans l'environnement
où il a été rédigé (pas de sandbox Windows/Wine disponible). L'architecture
(Wine + Python Windows + `MetaTrader5` + `mt5linux` + wrapper FastAPI) est
l'approche standard documentée pour faire tourner `MetaTrader5` hors Windows —
mais les commandes exactes de bootstrap Wine (`docker-entrypoint.sh`) sont le
point le plus fragile de tout ce plan MT5 et **doivent être vérifiées en
conditions réelles sur le VPS**, pas supposées correctes. Voir la checklist
de vérification plus bas.

## Pourquoi un service à part (jamais fusionné avec `engine`)

- L'engine (`ichivol-app/engine`) tourne sous Python Linux slim — le paquet
  `MetaTrader5` n'existe que pour Windows, il ne s'installe même pas ici.
- Isolation panne : si Wine plante, boucle, ou perd la connexion broker, ça
  ne touche à rien côté Postgres/engine/server/autres containers du VPS
  (réseau Docker `ichivol_mt5_bridge` séparé, jamais partagé avec `ichivol`
  ni avec les autres projets du VPS — `gsms-crm`, `pizzeria`, `qatrial`,
  `grace`, etc.).
- Limites dures (`mem_limit: 3g`, `cpus: 1.5` dans le compose racine) : ce
  VPS héberge d'autres clients, ce container ne doit jamais pouvoir les
  affamer même en cas de fuite mémoire Wine.

## Secrets

`MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` dans `deploy/vps/.env` (jamais
commités — voir `.env.example`). Compte **démo** uniquement pour l'instant ;
`MT5_MODE=READ_ONLY` côté engine (`app/config.py`) tant qu'aucune exécution
n'a été explicitement approuvée.

## Démarrer (une fois les credentials en place)

```bash
cd /opt/ichivol
docker compose --env-file deploy/vps/.env --profile mt5 up -d --build mt5-bridge
```

Ne démarre QUE ce service — jamais un `docker compose up -d` normal (sans
`--profile mt5`) ne le touchera, intentionnellement.

## Checklist de vérification (à faire à la main sur le VPS, dans l'ordre)

1. `docker compose --profile mt5 up -d --build mt5-bridge` puis
   `docker logs -f ichivol-mt5-bridge` — regarder si le bootstrap Wine
   (installation Python Windows, `pip install MetaTrader5 mt5linux`,
   installation du terminal) se termine sans erreur. **C'est l'étape la
   plus probable à casser** — ajuster `docker-entrypoint.sh` selon les
   messages d'erreur réels de `wine`/`winetricks`, pas en devinant.
2. `curl http://<vps-ip-interne-ou-tunnel>:8000/health` (depuis l'intérieur
   du réseau `ichivol_mt5_bridge`, ex. `docker exec ichivol-engine curl
   http://mt5-bridge:8000/health`) — doit répondre `connected: true` avec le
   nom du broker une fois `MT5_LOGIN/PASSWORD/SERVER` corrects.
3. Si le terminal a besoin d'un premier login manuel / 2FA / acceptation
   d'accord broker : ouvrir un tunnel SSH vers le port VNC du container
   (jamais un port public) et se connecter une fois à la main.
4. `MT5_ENABLED=true` dans `deploy/vps/.env`, redéployer l'engine seul
   (`docker compose up -d engine`), puis :
   ```bash
   docker exec ichivol-engine python -m app.market_data.cli XAUUSD 1h --limit 50 --exchange mt5
   docker exec ichivol-engine python -m app.market_data.cli EURUSD 1h --limit 50 --exchange mt5
   ```
5. Vérifier dans la réponse que `volume_type` est bien `tick` (ou `real` si
   le broker le confirme) — jamais mélangé silencieusement avec le volume
   Binance dans les mêmes stats RVOL.

## Ce qui n'existe volontairement pas encore

Aucune route d'exécution (ordres, positions). Lecture seule uniquement —
l'exécution démo (`app/execution/mt5_demo.py`, encore à écrire) est une
phase séparée, explicitement approuvée, après preuve sur la donnée seule.
