import { Link } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { KeenIcon } from '../components/KeenIcon'
import { ThemeToggle } from '../components/ThemeToggle'

const FEATURES = [
  {
    icon: 'abstract-39',
    title: 'Ève — IA qui trade paper',
    body: 'Une IA, quatre modes. Autonomie on = elle trade sur tous tes portefeuilles virtuels — Risk Kernel en garde-fou.',
  },
  {
    icon: 'kanban',
    title: 'Decision Engine · 5 portes',
    body: 'Direction → Participation → Structure → Location → Régime. Les portes alimentent la décision d’Ève — pas un chat qui invente un BUY.',
  },
  {
    icon: 'shield-tick',
    title: 'Autonomie bornée',
    body: 'Entry gate, signal rules, late→HOLD, kill-switch. Ève trade ; le Risk Kernel peut couper. Pas de live.',
  },
  {
    icon: 'notification-status',
    title: 'Event Radar',
    body: 'News et événements dans le dossier avant d’agir. Enrichit la décision de trade, ne remplace pas les portes.',
  },
  {
    icon: 'chart-simple',
    title: 'Strategy Lab',
    body: 'Event study, ablation, walk-forward, Monte Carlo — affûter les règles hors capital avant de laisser Ève trader paper.',
  },
  {
    icon: 'message-text-2',
    title: 'Preuves + timeline',
    body: 'Chaque trade paper a un dossier : modes JEV, gate, dégradation, Risk. Tu vois pourquoi Ève a agi.',
  },
]

const EVE_MODES = [
  {
    id: 'analyst',
    icon: '◇',
    name: 'Analyst',
    tag: 'NOUL · CHOICE · SCORE',
    body: 'Lit le setup et pose le scénario d’engagement.',
  },
  {
    id: 'challenger',
    icon: '↺',
    name: 'Challenger',
    tag: 'NOUL · CHOICE · SCORE',
    body: 'Contre-attaque — alternatives et fragilités avant d’ouvrir.',
  },
  {
    id: 'guardian',
    icon: '◈',
    name: 'Guardian',
    tag: 'NOUL · CHOICE · SCORE',
    body: 'Anomalies et risque. Le Risk Kernel peut bloquer.',
  },
  {
    id: 'shadow',
    icon: '◉',
    name: 'Shadow',
    tag: 'NOUL · CHOICE · SCORE',
    body: 'Contre-évaluation JEV API indépendante avant d’exécuter.',
  },
]

const ENGINE_STACK = [
  { code: 'CORE', label: 'Ichimoku × RVOL + Decision Engine (5 portes)' },
  { code: 'EVE', label: 'Ève — IA trading paper · 4 modes · dossiers JEV' },
  { code: 'GATE', label: 'Entry gate · signal rules · dégradation late→HOLD' },
  { code: 'RADAR', label: 'Event Radar — contexte avant d’agir' },
  { code: 'RISK', label: 'Risk Kernel — autorise / bloque l’exécution paper' },
  { code: 'LAB', label: 'Strategy Lab — affûter hors capital' },
]

const TRUST = [
  'IchiVol V4 : Ève trade le paper — autonomie on = elle ouvre',
  'Quatre modes JEV · Decision Engine · Event Radar',
  'Risk Kernel + kill-switch : elle trade, le risk peut couper',
  'Paper only — pas de live, pas de conseil financier',
]

const STEPS = [
  {
    n: '01',
    icon: 'filter-search',
    title: 'Mesurer',
    body: 'Cinq portes + structure. Le marché est lu avant toute action.',
  },
  {
    n: '02',
    icon: 'abstract-39',
    title: 'Décider',
    body: 'Ève en 4 modes + Event Radar. Dossier JEV, gate, signal rules.',
  },
  {
    n: '03',
    icon: 'verify',
    title: 'Exécuter',
    body: 'Autonomie on → Ève ouvre / gère paper. Risk Kernel peut refuser.',
  },
]

const COMPARE = {
  without: [
    'Un chat qui « conseillerait » d’acheter sans exécuter',
    'Pas de modes, pas de gate, pas de contre-lecture',
    'Trade possible sur signal pourri ou JEV down',
  ],
  with: [
    'Ève décide et trade paper sur tes portefeuilles',
    '4 modes + entry gate + late→HOLD avant d’ouvrir',
    'Risk Kernel / kill-switch peuvent bloquer l’exécution',
  ],
}

const STATS = [
  { value: 'V4', label: 'Workspace' },
  { value: '4', label: 'Modes Ève' },
  { value: '1', label: 'IA qui trade paper' },
  { value: '0', label: 'Live brokers' },
]

const FAQ = [
  {
    q: 'Qu’est-ce qu’IchiVol V4 ?',
    a: 'Un desk où Ève, l’IA décisionnelle, trade en paper : Decision Engine, 4 modes JEV, entry gate, Event Radar, Risk Kernel, Lab. Pas de live.',
  },
  {
    q: 'Ève trade vraiment ?',
    a: 'Oui — en paper. Autonomie on = elle ouvre et gère sur tous les portefeuilles virtuels actifs. Le Risk Kernel autorise ou bloque par livre ; kill-switch = plus d’entrées. Pas de broker live.',
  },
  {
    q: 'Qu’est-ce qu’Ève Intelligence ?',
    a: 'Une seule IA trading avec quatre modes actifs : Analyst, Challenger, Guardian, Shadow — chacun en NOUL / CHOICE / SCORE via JEV API (jevos en fallback crédit). Pas quatre LLM concurrents.',
  },
  {
    q: 'Que se passe-t-il si JEV est late ou down ?',
    a: 'Dégradation : late → HOLD, low confidence → ABSTAIN. Ève n’ouvre pas sur un état périmé.',
  },
  {
    q: 'Les cartes Agents sont-elles plusieurs LLM ?',
    a: 'Non. Ève est l’unique IA qui trade. Observateur, Risque, Exécution, Position, Session sont des rôles code autour d’elle.',
  },
  {
    q: 'Le Risk Kernel peut-il être contourné ?',
    a: 'Non. Toute ouverture paper passe le risk_kernel. Kill-switch armé = Ève ne peut plus ouvrir.',
  },
]

function CheckIcon() {
  return <KeenIcon icon="check-circle" style="outline" className="camap-check-icon" />
}

const CANDLES = [
  { bull: true, top: 118, bottom: 104, wickTop: 122, wickBottom: 98 },
  { bull: false, top: 108, bottom: 116, wickTop: 104, wickBottom: 120 },
  { bull: true, top: 102, bottom: 112, wickTop: 116, wickBottom: 96 },
  { bull: true, top: 92, bottom: 104, wickTop: 108, wickBottom: 86 },
  { bull: false, top: 90, bottom: 98, wickTop: 84, wickBottom: 102 },
  { bull: true, top: 78, bottom: 92, wickTop: 96, wickBottom: 72 },
  { bull: true, top: 68, bottom: 80, wickTop: 84, wickBottom: 62 },
  { bull: true, top: 58, bottom: 70, wickTop: 74, wickBottom: 52 },
  { bull: false, top: 56, bottom: 64, wickTop: 50, wickBottom: 68 },
  { bull: true, top: 44, bottom: 58, wickTop: 62, wickBottom: 38 },
  { bull: true, top: 34, bottom: 46, wickTop: 50, wickBottom: 28 },
  { bull: true, top: 26, bottom: 38, wickTop: 42, wickBottom: 20 },
]

function MockChart() {
  const step = 320 / (CANDLES.length + 1)
  return (
    <svg
      viewBox="0 0 320 150"
      className="camap-mock-chart"
      role="img"
      aria-label="Aperçu schématique d’un nuage Ichimoku en cassure haussière"
    >
      <defs>
        <linearGradient id="camapCloudFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.32" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <path
        d="M0,100 C50,94 70,78 110,80 C150,82 170,66 210,62 C250,58 290,48 320,44 L320,86 C290,92 250,102 210,104 C170,106 150,118 110,116 C70,114 50,106 0,110 Z"
        fill="url(#camapCloudFill)"
      />
      <path
        d="M0,100 C50,94 70,78 110,80 C150,82 170,66 210,62 C250,58 290,48 320,44"
        fill="none"
        stroke="var(--primary)"
        strokeOpacity="0.6"
        strokeWidth="1.4"
      />
      <path
        d="M0,110 C50,106 70,114 110,116 C150,118 170,106 210,104 C250,102 290,92 320,86"
        fill="none"
        stroke="var(--primary)"
        strokeOpacity="0.32"
        strokeWidth="1.4"
      />
      <line
        x1="40"
        x2="300"
        y1="72"
        y2="72"
        stroke="var(--primary)"
        strokeOpacity="0.35"
        strokeWidth="1"
        strokeDasharray="4 3"
      />
      <text x="42" y="68" fill="var(--primary)" fillOpacity="0.55" fontSize="8" fontFamily="var(--font-mono)">
        Fib 61.8
      </text>
      {CANDLES.map((c, i) => {
        const x = step * (i + 1)
        const color = c.bull ? 'var(--primary)' : 'var(--destructive)'
        return (
          <g key={i}>
            <line
              x1={x}
              x2={x}
              y1={c.wickTop}
              y2={c.wickBottom}
              stroke={color}
              strokeOpacity="0.6"
              strokeWidth="1"
            />
            <rect
              x={x - 4}
              y={Math.min(c.top, c.bottom)}
              width="8"
              height={Math.max(2, Math.abs(c.bottom - c.top))}
              fill={color}
              fillOpacity="0.85"
              rx="1.5"
            />
          </g>
        )
      })}
    </svg>
  )
}

export function LandingPage() {
  return (
    <div className="camap-shell">
      <header className="camap-nav-wrap">
        <nav className="camap-nav" aria-label="Navigation principale">
          <Link to="/" className="camap-brand" aria-label="IchiVol — accueil">
            <BrandMark className="camap-mark" />
            <span className="camap-word">IchiVol</span>
          </Link>
          <div className="camap-nav-links">
            <a href="#moteur">Moteur V4</a>
            <a href="#eve">Ève</a>
            <a href="#methode">Décision</a>
            <a href="#capacites">Capacités</a>
            <a href="#comparatif">Comparatif</a>
            <a href="#faq">FAQ</a>
          </div>
          <div className="camap-nav-actions">
            <ThemeToggle />
            <Link to="/login" className="camap-btn camap-btn-primary">
              Se connecter
            </Link>
          </div>
        </nav>
      </header>

      <main>
        <section className="camap-hero">
          <div className="camap-hero-glow" aria-hidden />
          <div className="camap-hero-grid">
            <div className="camap-hero-copy camap-reveal">
              <p className="camap-brand-lockup">IchiVol V4</p>
              <h1 className="camap-hero-title">
                Ève trade. <em>Le risk borne.</em>
              </h1>
              <p className="camap-hero-lede">
                IA décisionnelle paper : quatre modes JEV, Decision Engine,
                entry gate, Event Radar. Autonomie on — elle ouvre. Risk Kernel
                peut couper. Pas de live.
              </p>
              <div className="camap-hero-cta">
                <Link to="/login" className="camap-btn camap-btn-primary camap-btn-lg">
                  Lancer le Desk V4
                </Link>
              </div>
            </div>

            <div className="camap-hero-visual-wrap camap-reveal camap-reveal-delay">
              <div className="camap-hero-visual">
                <span className="camap-hero-visual-badge">
                  <span className="camap-dot camap-dot-live" aria-hidden />
                  V4 · Ève trading paper
                </span>
                <MockChart />
                <div className="camap-hero-visual-footer">
                  <span>BTCUSDT · 1h</span>
                  <span className="camap-chip camap-chip-bull">paper open</span>
                </div>
                <div className="camap-hero-gates" aria-hidden>
                  <span className="is-pass">Portes</span>
                  <span className="is-pass">Gate</span>
                  <span className="is-pass">Risk</span>
                  <span className="is-watch">Ève trade</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="camap-trust" aria-label="Points clés">
          <ul className="camap-checklist camap-checklist-inline">
            {TRUST.map((item) => (
              <li key={item}>
                <CheckIcon />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="moteur" className="camap-section">
          <h2 className="camap-section-title">Stack IchiVol V4</h2>
          <p className="camap-section-lede">
            Du signal à l’exécution paper : Core → Ève → gate → radar → Risk →
            Lab.
          </p>
          <ol className="camap-engine-stack">
            {ENGINE_STACK.map((row) => (
              <li key={row.code}>
                <span className="camap-engine-code">{row.code}</span>
                <span>{row.label}</span>
              </li>
            ))}
          </ol>
        </section>

        <section id="eve" className="camap-section">
          <h2 className="camap-section-title">Ève — l’IA qui trade</h2>
          <p className="camap-section-lede">
            Quatre modes avant d’ouvrir. Autonomie on = exécution paper sur tes
            portefeuilles.
          </p>
          <div className="camap-eve-modes">
            {EVE_MODES.map((m) => (
              <article key={m.id} className="camap-eve-mode">
                <span className="camap-eve-mode-icon" aria-hidden>
                  {m.icon}
                </span>
                <div className="camap-eve-mode-head">
                  <h3>{m.name}</h3>
                  <span className="camap-eve-mode-tag">{m.tag}</span>
                </div>
                <p>{m.body}</p>
              </article>
            ))}
          </div>
          <p className="camap-eve-footnote">
            Hub dossiers → modes → entry gate → Risk Kernel → ouverture paper.
            Elle trade ; le Risk Kernel peut refuser.
          </p>
        </section>

        <section id="methode" className="camap-section">
          <h2 className="camap-section-title">Chaîne de trade V4</h2>
          <p className="camap-section-lede">
            Mesurer → décider (Ève) → exécuter paper (Risk peut couper).
          </p>
          <ol className="camap-steps camap-steps-numbered">
            {STEPS.map((step) => (
              <li key={step.n}>
                <span className="camap-step-number" aria-hidden>
                  {step.n}
                </span>
                <span className="camap-icon-box camap-icon-box-sm" aria-hidden>
                  <KeenIcon icon={step.icon} style="duotone" />
                </span>
                <strong>{step.title}</strong>
                <span>{step.body}</span>
              </li>
            ))}
          </ol>
          <blockquote className="camap-inline-quote">
            <p>
              « Ève n’est pas un copilote qui te demande permission à chaque
              bougie — c’est une IA qui trade paper, bornée par le Risk Kernel. »
            </p>
            <cite>Principe IchiVol V4</cite>
          </blockquote>
        </section>

        <section id="capacites" className="camap-section">
          <h2 className="camap-section-title">Capacités V4</h2>
          <p className="camap-section-lede">
            Trading paper autonome, portes, gate, radar, Risk, Lab — dans le
            Desk.
          </p>
          <div className="camap-bento">
            {FEATURES.map((f) => (
              <article key={f.title} className="camap-card">
                <span className="camap-icon-box" aria-hidden>
                  <KeenIcon icon={f.icon} style="duotone" />
                </span>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="comparatif" className="camap-section">
          <h2 className="camap-section-title">Ce que change la V4</h2>
          <p className="camap-section-lede">
            Pas un chatbot. Une IA qui décide et exécute paper, avec garde-fous.
          </p>
          <div className="camap-compare">
            <div className="camap-compare-col">
              <span className="camap-compare-label">Chat IA classique</span>
              <ul>
                {COMPARE.without.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="camap-compare-col camap-compare-col-highlight">
              <span className="camap-compare-label">IchiVol V4 · Ève</span>
              <ul>
                {COMPARE.with.map((item) => (
                  <li key={item}>
                    <CheckIcon />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="camap-stats">
          {STATS.map((s) => (
            <div key={s.label} className="camap-stat">
              <span className="camap-stat-value">{s.value}</span>
              <span className="camap-stat-label">{s.label}</span>
            </div>
          ))}
        </section>

        <section id="faq" className="camap-section">
          <h2 className="camap-section-title">Avant de lancer Ève</h2>
          <div className="camap-faq">
            {FAQ.map((item) => (
              <details key={item.q} className="camap-faq-item">
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="camap-closing">
          <h2>Laisse Ève trader le paper</h2>
          <p>
            IchiVol V4 · autonomie paper · 4 modes · Decision Engine · Risk
            Kernel. Pas de live.
          </p>
          <Link to="/login" className="camap-btn camap-btn-primary camap-btn-lg">
            Se connecter
          </Link>
        </section>
      </main>

      <footer className="camap-footer">
        <div className="camap-footer-inner">
          <div className="camap-footer-brand">
            <Link to="/" className="camap-brand" aria-label="IchiVol — accueil">
              <BrandMark className="camap-mark" />
              <span className="camap-word">IchiVol</span>
            </Link>
            <p>
              IchiVol V4 — Ève trade le paper sur Ichimoku × RVOL. Decision
              Engine, modes JEV, Risk Kernel. Autonomie bornée, pas de live.
            </p>
          </div>

          <div className="camap-footer-cols">
            <div className="camap-footer-col">
              <h3>Produit V4</h3>
              <a href="#moteur">Moteur</a>
              <a href="#eve">Ève</a>
              <a href="#methode">Décision</a>
              <a href="#capacites">Capacités</a>
              <a href="#comparatif">Comparatif</a>
              <a href="#faq">FAQ</a>
            </div>
            <div className="camap-footer-col">
              <h3>Workspace</h3>
              <Link to="/login">Desk V4</Link>
              <Link to="/login">Agents / Ève</Link>
              <Link to="/login">Portefeuille</Link>
              <Link to="/login">Strategy Lab</Link>
              <Link to="/login">Copilot</Link>
            </div>
            <div className="camap-footer-col">
              <h3>Compte</h3>
              <Link to="/login">Se connecter</Link>
              <Link to="/login">Paramètres</Link>
            </div>
          </div>
        </div>

        <div className="camap-footer-bar">
          <span className="camap-footer-muted">
            © {new Date().getFullYear()} IchiVol V4 — trading paper autonome, pas un conseil financier.
          </span>
          <span className="camap-footer-muted">
            Ève trade · Risk borne · paper only
          </span>
        </div>
      </footer>
    </div>
  )
}
