import { Link } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { KeenIcon } from '../components/KeenIcon'
import { ThemeToggle } from '../components/ThemeToggle'

const FEATURES = [
  {
    icon: 'element-11',
    title: 'Desk workspace V3',
    body: '11 pages alignées maquette : Desk, Marché, Opportunités, Portefeuille, Lab, Journal, Contexte, Copilot, Agents, Opérations, Paramètres.',
  },
  {
    icon: 'abstract-39',
    title: 'Eve — agent de surveillance',
    body: 'File AgentTask type Comp AI : mission 1 symbole, réveil à la bougie fermée, réponse dans Copilot. Paper only · confirm humaine.',
  },
  {
    icon: 'shield-tick',
    title: 'Risk Kernel + kill-switch',
    body: 'Toute ouverture paper passe le risk_kernel. Kill-switch et pertes journalières bloquent les entrées — le LLM ne bypass jamais.',
  },
  {
    icon: 'kanban',
    title: 'Decision Engine · 5 portes',
    body: 'Direction → Participation → Structure → Location → Régime. Portes = action ; badge combiner = diagnostic. Le LLM ne décide pas.',
  },
  {
    icon: 'chart-simple',
    title: 'Strategy Lab',
    body: 'Event study, rulesets, ablation, walk-forward, Monte Carlo — recherche hors capital, sans promotion auto vers le live.',
  },
  {
    icon: 'message-text-2',
    title: 'Copilot + preuves moteur',
    body: 'Tools allowlistés, DECISION_DATA, evidence et qualité. Explication ancrée — pas d’invention de BUY.',
  },
]

const ENGINE_STACK = [
  { code: 'CORE', label: 'Ichimoku × RVOL + Decision Engine' },
  { code: 'MS', label: 'Market Structure · swings · FVG · Fib' },
  { code: 'RISK', label: 'Risk Kernel · kill-switch · paper gateway' },
  { code: 'EVE', label: 'AgentTask · schedule_recheck · Copilot thread' },
  { code: 'LAB', label: 'Strategy Lab — recherche hors capital' },
  { code: 'CYCLE', label: 'CycleState V0 — observation seule (FFT / Hilbert)' },
]

const TRUST = [
  'Moteur Python = vérité · Eve explique, ne décide pas',
  'Paper only · confirm humaine par défaut · pas d’auto-open',
  'Risk Kernel obligatoire avant toute entrée paper',
  'Lab et expériences hors capital — pas de promo live auto',
]

const STEPS = [
  {
    n: '01',
    icon: 'filter-search',
    title: 'Lire',
    body: 'Desk et Marché : régime, sessions, screener, preuves pipeline.',
  },
  {
    n: '02',
    icon: 'verify',
    title: 'Qualifier',
    body: 'Portes Decision Engine + Risk Kernel. Shadow journal si blocage.',
  },
  {
    n: '03',
    icon: 'abstract-39',
    title: 'Surveiller',
    body: 'Mission Eve sur un symbole · réveil à la bougie · rapport dans Copilot.',
  },
]

const COMPARE = {
  without: [
    'Un croisement Tenkan/Kijun sans volume = faux départ',
    'Un chat IA invente un BUY hors du moteur',
    'Aucune surveillance durable entre deux sessions',
  ],
  with: [
    'Signal + participation + structure mesurés hors échantillon',
    'Eve dort / se réveille (file Postgres) — reply dans Copilot',
    'Risk Kernel + kill-switch avant paper · toi confirmes',
  ],
}

const STATS = [
  { value: '11', label: 'Pages workspace' },
  { value: '5', label: 'Portes Decision Engine' },
  { value: '1', label: 'Agent LLM (Eve)' },
  { value: '0', label: 'Votes LONG/SHORT par le LLM' },
]

const FAQ = [
  {
    q: 'IchiVol donne-t-il un conseil financier ?',
    a: 'Non. Le moteur produit une lecture structurée ; Eve / Copilot l’expliquent. La décision de trade reste la vôtre.',
  },
  {
    q: 'Que fait Eve quand je « Surveille BTC » ?',
    a: 'Une mission AgentTask est planifiée à la prochaine bougie fermée. Eve se réveille, lit le moteur via tools, écrit dans le thread Copilot, et peut se reprogrammer. Paper only, confirm humaine.',
  },
  {
    q: 'Les 6 cartes Agents sont-elles 6 LLM ?',
    a: 'Non. Un seul LLM (Eve / Opportunités). Les cinq autres sont des rôles code (observateur, risque, exécution, position, session) déjà dans le moteur — la page affiche leur état.',
  },
  {
    q: 'Qu’est-ce que le Strategy Lab ?',
    a: 'Un banc de recherche : event study, ablation, walk-forward, Monte Carlo. Aucune promotion automatique vers le trading live.',
  },
  {
    q: 'Le Risk Kernel peut-il être contourné par l’agent ?',
    a: 'Non. Toute ouverture paper passe le risk_kernel et le paper gateway. Kill-switch armé = entrées bloquées.',
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
            <a href="#moteur">Moteur</a>
            <a href="#methode">Méthode</a>
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
              <p className="camap-brand-lockup">IchiVol</p>
              <h1 className="camap-hero-title">
                Observer. Qualifier. <em>Surveiller.</em>
              </h1>
              <p className="camap-hero-lede">
                Workspace V3 : le moteur tranche, le Risk Kernel borne, Eve
                surveille — Claude explique, sans jamais inventer le BUY.
              </p>
              <div className="camap-hero-cta">
                <Link to="/login" className="camap-btn camap-btn-primary camap-btn-lg">
                  Entrer dans le Desk
                </Link>
              </div>
            </div>

            <div className="camap-hero-visual-wrap camap-reveal camap-reveal-delay">
              <div className="camap-hero-visual">
                <span className="camap-hero-visual-badge">
                  <span className="camap-dot camap-dot-live" aria-hidden />
                  Eve · mission · paper
                </span>
                <MockChart />
                <div className="camap-hero-visual-footer">
                  <span>BTCUSDT · 1h</span>
                  <span className="camap-chip camap-chip-bull">recheck due</span>
                </div>
                <div className="camap-hero-gates" aria-hidden>
                  <span className="is-pass">Direction</span>
                  <span className="is-pass">Participation</span>
                  <span className="is-pass">Risk</span>
                  <span className="is-watch">Eve veille</span>
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
          <h2 className="camap-section-title">Stack moteur V3</h2>
          <p className="camap-section-lede">
            Core Ichimoku×RVOL, structure, risk, agent Eve, Lab — Cycle en
            observation seule.
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

        <section id="methode" className="camap-section">
          <h2 className="camap-section-title">Ce que l’app traite</h2>
          <p className="camap-section-lede">
            Live → portes → risk → Lab / Paper → Eve / Copilot.
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
              « Ne demande pas à Claude s’il faut acheter — demande au moteur
              ce qu’il a mesuré, puis laisse Eve te le rappeler à la bougie. »
            </p>
            <cite>Principe IchiVol V3</cite>
          </blockquote>
        </section>

        <section id="capacites" className="camap-section">
          <h2 className="camap-section-title">Capacités</h2>
          <p className="camap-section-lede">
            Livré dans le workspace — Desk, Eve, Risk Kernel, Lab, preuves.
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
          <h2 className="camap-section-title">Ce que ça change</h2>
          <p className="camap-section-lede">
            Même Ichimoku. La différence : risk borné + Eve qui survit au restart.
          </p>
          <div className="camap-compare">
            <div className="camap-compare-col">
              <span className="camap-compare-label">Sans IchiVol</span>
              <ul>
                {COMPARE.without.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="camap-compare-col camap-compare-col-highlight">
              <span className="camap-compare-label">Avec IchiVol V3</span>
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
          <h2 className="camap-section-title">Avant de décider</h2>
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
          <h2>Prêt à entrer dans le Desk</h2>
          <p>Workspace V3 · Eve · Risk Kernel · Lab · Copilot — session sécurisée.</p>
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
              Cockpit Ichimoku × RVOL V3 : Desk, Eve, Risk Kernel, Lab —
              le moteur tranche, toi confirmes.
            </p>
          </div>

          <div className="camap-footer-cols">
            <div className="camap-footer-col">
              <h3>Produit</h3>
              <a href="#moteur">Moteur</a>
              <a href="#methode">Méthode</a>
              <a href="#capacites">Capacités</a>
              <a href="#comparatif">Comparatif</a>
              <a href="#faq">FAQ</a>
            </div>
            <div className="camap-footer-col">
              <h3>Workspace</h3>
              <Link to="/login">Desk</Link>
              <Link to="/login">Agents / Eve</Link>
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
            © {new Date().getFullYear()} IchiVol — lecture structurée, pas un conseil financier.
          </span>
          <span className="camap-footer-muted">
            Eve surveille · Risk borne · toi confirmes
          </span>
        </div>
      </footer>
    </div>
  )
}
