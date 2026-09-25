import { Link } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { KeenIcon } from '../components/KeenIcon'
import { ThemeToggle } from '../components/ThemeToggle'

const FEATURES = [
  {
    icon: 'kanban',
    title: 'Decision Engine · 5 portes',
    body: 'Direction → Participation → Structure → Location → Régime. Portes = action ; badge combiner = diagnostic. Le LLM ne décide pas.',
  },
  {
    icon: 'chart-simple',
    title: 'Strategy Lab',
    body: 'Event study, rulesets IV_EXP A–G, ablation Kijun, walk-forward et optimisation IS→OOS — sans promotion auto vers le live.',
  },
  {
    icon: 'abstract-26',
    title: 'Market Structure + Fibonacci',
    body: 'Zones MVPP / trendln / consensus, puis Fib 23.6–78.6 sur les swings. Portfolio ICHIVOL_MS_FIB : confluence requise, baseline intact.',
  },
  {
    icon: 'dollar',
    title: 'PaperBroker multi-portfolio',
    body: '5 000 € / profil, SL/TP ATR, fees. Expériences STRUCTURE_*, CTX_*, MS_FIB en parallèle — jamais d’écrasement du baseline.',
  },
  {
    icon: 'message-text-2',
    title: 'Copilot atelier + canal agent',
    body: 'Tools déterministes (scan, Lab, walk-forward…). Chat à gauche, outils moteur à droite — explication ancrée, pas d’invention de BUY.',
  },
  {
    icon: 'chart-pie-4',
    title: 'Contexte & corrélations',
    body: 'RSI / CMF / OBV / régime ATR en filtres optionnels. Climat crypto, news, heatmap — lecture seule, jamais un vote LONG/SHORT.',
  },
]

const ENGINE_STACK = [
  { code: 'CORE', label: 'Ichimoku × RVOL + Analytics Kijun/Kumo' },
  { code: 'MS', label: 'Market Structure (MVPP · trendln · consensus)' },
  { code: 'FIB', label: 'FibonacciContext — Phase 4 confluence' },
  { code: 'CTX', label: 'Context gates RSI · CMF/OBV · régime' },
  { code: 'PAPER', label: 'PaperBroker A/B — 12 profils syncables' },
  { code: 'LAB', label: 'Strategy Lab — recherche hors capital' },
]

const TRUST = [
  'Moteur Python = vérité mathématique · Copilot = explication',
  'Strategy Lab avant live — pas de promotion automatique',
  'Baseline ICHIVOL_BASELINE_V1 gelé · expériences en parallèle',
  'Fibonacci hors géométrie Structure — retracement sur swings',
]

const STEPS = [
  {
    n: '01',
    icon: 'filter-search',
    title: 'Scanner',
    body: 'Screener multi-classes : biais Ichimoku, RVOL, portes Decision Engine.',
  },
  {
    n: '02',
    icon: 'verify',
    title: 'Filtrer',
    body: 'Structure, Fib confluence, contexte — downgrade only. Shadow journal si blocage.',
  },
  {
    n: '03',
    icon: 'flask',
    title: 'Mesurer',
    body: 'Lab (event study / WF / ablation) + Paper multi-portfolio. Les données décident.',
  },
]

const COMPARE = {
  without: [
    'Un croisement Tenkan/Kijun sans volume = faux départ',
    'Un filtre Structure / Fib « au feeling » sans A/B capitalisé',
    'Un chat IA invente un BUY hors du moteur',
  ],
  with: [
    'Signal + participation + structure + Fib mesurés hors échantillon',
    'Paper 5 000 € / profil · Lab walk-forward avant toute promo live',
    'Copilot ancré sur DECISION_DATA et tools allowlistés',
  ],
}

const STATS = [
  { value: '5', label: 'Portes Decision Engine' },
  { value: '12', label: 'Profils Paper syncables' },
  { value: '8', label: 'Phases Strategy Lab' },
  { value: '0', label: 'Votes LONG/SHORT par le LLM' },
]

const FAQ = [
  {
    q: 'IchiVol donne-t-il un conseil financier ?',
    a: 'Non. Le moteur produit une lecture structurée ; le Copilot l’explique. La décision de trade reste la vôtre.',
  },
  {
    q: 'Qu’est-ce que le Strategy Lab ?',
    a: 'Un banc de recherche sur le moteur : event study, rulesets Ichimoku Analytics (EXP A–G), ablation, régimes, walk-forward et optimisation. Aucune promotion automatique vers le trading live.',
  },
  {
    q: 'Fibonacci est-il dans le Market Structure ?',
    a: 'Non. La Structure trouve les swings ; FibonacciContext mesure le retracement (23.6–78.6) à l’intérieur. Le profil ICHIVOL_MS_FIB exige la confluence — le baseline ne l’utilise pas.',
  },
  {
    q: 'À quoi servent les multi-portfolios Paper ?',
    a: 'Comparer en parallèle Ichimoku×RVOL (baseline), Structure, Context, Fib… avec le même capital fictif 5 000 €, mêmes frais et risque. Les données disent quelle brique aide vraiment.',
  },
  {
    q: 'L’agent peut-il changer le verdict du moteur ?',
    a: 'Non. Il interroge le moteur (scan, Lab, context…) et explique. Il n’invente pas de chiffres et ne propose pas un LONG/SHORT contraire.',
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
      {/* Fib 61.8 schematic line */}
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
                Observer. Qualifier. <em>Décider.</em>
              </h1>
              <p className="camap-hero-lede">
                Ichimoku trouve la direction. RVOL exige la participation. Le moteur tranche —
                Claude explique, sans jamais inventer le BUY.
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
                  Pipeline · BUY · Fib OK
                </span>
                <MockChart />
                <div className="camap-hero-visual-footer">
                  <span>BTCUSDT · 1h</span>
                  <span className="camap-chip camap-chip-bull">RVOL 1.8×</span>
                </div>
                <div className="camap-hero-gates" aria-hidden>
                  <span className="is-pass">Direction</span>
                  <span className="is-pass">Participation</span>
                  <span className="is-pass">Structure</span>
                  <span className="is-watch">Fib 61.8</span>
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
          <h2 className="camap-section-title">Stack moteur Grand V2</h2>
          <p className="camap-section-lede">
            Chaque brique est optionnelle, mesurée hors échantillon. Phase 4 :
            FibonacciContext sur swings Structure — baseline inchangé.
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
            Live → portes → filtres expérimentaux → Lab / Paper → Copilot.
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
              « Ne demande pas si Fibonacci est bon — demande aux données s’il
              améliore l’expectancy hors échantillon. »
            </p>
            <cite>Principe IchiVol Grand V2</cite>
          </blockquote>
        </section>

        <section id="capacites" className="camap-section">
          <h2 className="camap-section-title">Capacités</h2>
          <p className="camap-section-lede">
            Livré dans le cockpit — Lab, Paper A/B, Structure, Fib Phase 4.
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
            Même Ichimoku. La différence : briques mesurées + Lab avant live.
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
              <span className="camap-compare-label">Avec IchiVol V2</span>
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
          <h2>Prêt à entrer dans le cockpit</h2>
          <p>Décisions, Strategy Lab, Paper multi-portfolio, Copilot — session sécurisée.</p>
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
              Cockpit Ichimoku × RVOL Grand V2 : Structure, Fib, Lab, Paper A/B —
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
              <h3>Cockpit</h3>
              <Link to="/login">Décisions</Link>
              <Link to="/login">Backtests / Lab</Link>
              <Link to="/login">Paper</Link>
              <Link to="/login">Copilot</Link>
              <Link to="/login">Contexte</Link>
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
            Lab mesure · Paper compare · toi confirmes
          </span>
        </div>
      </footer>
    </div>
  )
}
