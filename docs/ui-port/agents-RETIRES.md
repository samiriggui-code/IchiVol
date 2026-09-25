# Agents — éléments retirés (port maquette)

## UI retirée vs ancienne page

- KeenIcon / cartes panel custom
- Lien Copilot LLM status strip
- Details/summary périmètre
- Badge figé `APERÇU` / notice « illustratifs · aucun agent en exécution »

## Notes

- Permissions / modes = taxonomie maquette (lecture seule paper, pas d’ordres réels)
- Chantier 2b : page branchée sur `GET /api/agents` (6 rôles) + `POST /api/agents/missions`
- FicheAgent / FicheHost : absent sur main → deep-link `?fiche=agent:id` ouvre dialog permissions (stub)
- AgentLog → journal Opérations : follow-up (pas d’injection ActivityPage ici — compare)
