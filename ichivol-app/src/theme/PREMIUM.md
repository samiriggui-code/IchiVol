# IchiVol premium : guide pour refaire une page

Source de vérité visuelle : la maquette « poste de trading » validée.
Le socle est dans `src/theme/premium.css` (importé en premier dans `Root.tsx`).
La coquille (barre latérale, bandeau, barre mobile) est dans `layouts/DashboardShell.tsx`
et le début de `src/index.css`. Ne pas y toucher depuis une page.

## Jetons (toujours `var(--…)`)

| Rôle | Jetons |
|---|---|
| Fonds | `--bg0` (page), `--bg1` (halo), `--panel`, `--panel-h`, `--panel-2`, `--raise` |
| Bordures 1px | `--line` (cartes), `--line-2` (champs, en-têtes de tableau), `--line-3` (survol) |
| Texte | `--text`, `--text-2`, `--muted`, `--dim` |
| Accents | `--cyan`, `--amber`, `--mint`, `--violet`, chacun avec `-soft` (fond) et `-line` (bordure) sauf violet |
| Achat / vente, P&L | `--buy`, `--sell` (+ `-soft`, `-line`) ; alias `--pos`, `--neg` |
| Surfaces composées | `--page-bg`, `--panel-bg`, `--panel-head-bg`, `--th-bg`, `--row-line`, `--row-alt`, `--row-hover`, `--row-sel`, `--input-bg`, `--ghost-bg`, `--hover-bg`, `--track-bg`, `--sheet-bg`, `--apex-bg`, `--shadow-pop` |
| Typo | `--sans` (Inter), `--mono` (JetBrains Mono) |
| Formes | `--r-s` 6px, `--r` 10px, `--r-l` 24px, `--gap` 8px |

Les deux thèmes (sombre par défaut, clair via le bouton soleil/lune) définissent les mêmes noms :
une page qui n'utilise que des jetons marche dans les deux.

Alias historiques encore lus par l'ancien code : `--background`, `--foreground`, `--card`,
`--primary`, `--border`, `--muted-foreground`, `--ink`, `--blue`, `--green`, `--red`, `--bull`,
`--bear`… Ne pas les utiliser dans du code neuf.

## Primitives (classes globales, préfixe `iv-`)

| Besoin | Classes |
|---|---|
| En-tête de page | `.iv-ph` > `div` (`.iv-meta` + `h1` + `p`) + `.iv-ph-act` |
| Grille | `.iv-grid` + `.iv-s2` … `.iv-s12` ; `.iv-m-s12` / `.iv-m-s6` sous 1100px ; une colonne sous 760px |
| Carte station | `.iv-card` > `.iv-card-head` (> `.iv-card-tabs` > `.iv-card-tab.is-on`, puis `.iv-card-tools`) > `.iv-card-body` (`.is-flush` pour un tableau) > `.iv-card-foot` |
| Ligne cyan en haut d'une carte | ajouter `.iv-glow` sur `.iv-card` |
| Carte signature APEX | `.apex-card` (coins 24px, ligne cyan lumineuse) ; libellé `.iv-label` (ambre ◆) ; pied `.apex-card-foot` > `.apex-card-sig` |
| Bandeau de KPI | `.iv-kpis` > `.iv-kpi` > `.iv-kpi-k`, `.iv-kpi-v` (`small` pour les décimales), `.iv-kpi-s` |
| Tableau dense | `.iv-table-wrap` > `table.iv-table` (`.is-compact`) ; `th.n` / `td.n` = chiffres alignés à droite ; `tr.is-selected` = ligne sélectionnée bleue ; `.sym` pour le symbole |
| Boutons | `.iv-btn` (fantôme par défaut), `--primary` (cyan), `--buy` (Acheter, bleu), `--sell` (Vendre, rouge), `--ghost`, `--sm` |
| Arrêt d'urgence | `.iv-estop` avec `<i />` en tête (déjà dans le bandeau, ne pas le recréer) |
| Champs | `.iv-field` > `label` + `.iv-input` (input, select, textarea) |
| Pastilles | `.iv-chip`, `.iv-tag`, `.iv-pill` + ton `.is-cyan`, `.is-amber`, `.is-mint`, `.is-buy`, `.is-sell`, `.is-muted` |
| Sens | `.iv-side.is-long` / `.is-short` |
| Point d'état | `.iv-dot` (+ `.is-amber`, `.is-sell`, `.is-off`) |
| Décideur | `.iv-decider` > `<i />` + texte ; `.is-eve`, `.is-manual`, `.is-vs` (Moteur contre Ève) ; sans modificateur = Moteur seul |
| Filtres segmentés | `.iv-seg` > `button.is-on` (ou `aria-pressed`) |
| Jauge | `.iv-bar` > `<i style={{ width }} />` + `.is-amber`, `.is-mint`, `.is-buy`, `.is-sell` |
| Ligne clé / valeur | `.iv-row` > texte + `.iv-row-v` |
| Métadonnées | `.iv-meta` (mono cyan, petites capitales), `.iv-cap` (mono gris), `.iv-kw` (mot clé ambre), `.iv-note` |
| Vide / erreur de chargement | `.iv-empty`, `.iv-empty.is-error` |
| Couleurs de valeur | `.up` / `.pos` (bleu), `.down` / `.neg` (rouge), `.ok` (menthe), `.warn` (ambre), `.cy`, `.dim`, `.muted` |
| Chiffres | `.mono` ou `.iv-num` (mono + tabular-nums), `.tn` (tabular-nums seul) |

Icônes au trait : `components/NavIcons.tsx` (`IconOverview`, `IconAgents`…, taille par CSS, couleur = `currentColor`).

## Règles

1. Aucune couleur codée en dur (`#…`, `rgb(…)`) dans une page : toujours `var(--…)`.
2. Bleu et rouge sont réservés au P&L et à achat / vente. Pas de bouton bleu « pour faire joli ».
3. Cyan et ambre pour les accents, sélections, onglets actifs et métadonnées ; menthe pour « OK / passe / connecté ».
4. Chiffres en `--mono` avec `tabular-nums`. Une donnée absente s'affiche « — », jamais un chiffre inventé.
5. Vocabulaire inchangé, tout en français : portefeuille, arrêt d'urgence, Ève, JEV (jamais de nom de fournisseur), Moteur seul / Ève / Moteur contre Ève / Manuel, pas de « V4 ».
6. Aucune logique métier ni appel d'API modifié pour du visuel.
7. Pas de `!important`, pas de sélecteur global hors de la racine de la page (`.desk-page …`).

## Le pont des pages (à retirer en refaisant une page)

`premium.css`, section 5, raccorde les anciennes pages aux jetons (`html .agents-page { --ink: … }`,
`.card`, `th`, `.tag`, `.primary`, `.up` / `.down`…). Quand une page est refaite sur les primitives `iv-` :

- supprimer le bloc de jetons figés en tête de son CSS (`--bg`, `--card`, `--line`, `--ink`, `--muted`, `--blue`, `--green`, `--red`, `--amber`) ;
- les règles du pont ne visent que des classes historiques ; une page qui n'en utilise plus n'est plus concernée. Ne pas retirer sa racine de la liste du pont tant qu'une autre page partage le même fichier ou les mêmes classes.

Piège : dans une racine de page, le pont restyle tout `button`, `input`, `select`, `textarea`
qui n'a pas de classe contenant `iv-` (spécificité élevée). Pour un bouton ou un champ neuf,
utiliser `.iv-btn…` / `.iv-input`, sinon votre style local sera écrasé.

## Vérifier une page

```bash
cd ichivol-app
npx tsc -p tsconfig.app.json --noEmit
npm run lint      # aucune nouvelle erreur
npm run build
npx vite --port 5199
chromium --headless --screenshot=/tmp/page-1440.png --window-size=1440,900 http://localhost:5199/app/<page>
chromium --headless --screenshot=/tmp/page-390.png --window-size=390,844 http://localhost:5199/app/<page>
```

Sans API, `/app/*` renvoie vers `/login` : il faut un `/api/auth/me` qui répond (API locale, ou petit
serveur bouchon pointé par `AGENT_SERVER=http://localhost:<port> npx vite`). Les états vides et
erreurs de chargement sont normaux sans moteur ; le cadre et les cartes doivent rester propres.
Regarder aussi le thème clair (bouton lune en bas de la barre latérale ; sur mobile, dans « Plus »)
et la largeur 390px (pas de défilement horizontal, rien sous la barre du bas).
