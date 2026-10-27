# Binance en direct — ajout volontaire goldens (documenté)

Route ajoutée : `GET /api/engine/health/live` (état du flux direct Binance et de la surveillance temps réel des
stops). `GET /api/engine/health` renvoie en plus la clé `live_feed` (schéma de réponse libre, inchangé).

OpenAPI + `route_order_golden.json` régénérés : ajouts seulement, aucune route existante modifiée ni réordonnée.
