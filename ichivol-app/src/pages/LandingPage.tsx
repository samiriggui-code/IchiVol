import { Link } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { KeenIcon } from '../components/KeenIcon'
import { ThemeToggle } from '../components/ThemeToggle'

const FEATURES = [
  {
    icon: 'kanban',
    title: 'Matrice de portes',
    body: 'Direction → Participation → Structure → Location → Régime. Portes = verdict d’action ; badge combiner = diagnostic. Le LLM ne décide pas.',
  },
  {
    icon: 'message-text-2',
    title: 'Copilot atelier',
    body: 'Depuis Décisions / Journal / Watchlist : tu arrives sur /app/agent avec un prompt déjà prêt. Chat à gauche, outils moteur à droite.',
  },
  {
    icon: 'chart-pie-4',
    title: 'Contexte & corrélations',
    body: 'Climat crypto, news RSS, calendrier macro, heatmap « qui bouge avec qui ». Lecture seule — jamais un vote LONG/SHORT.',
  },
  {
    icon: 'notification-bing',
    title: 'Journal watch + cloche',
    body: 'Confirme une lecture ; le watch poll le pipeline et te notifie si les portes changent. Paper multi-classe quand tu veux tester.',
  },
]

const TRUST = [
  'Moteur Python = vérité mathématique · Copilot = explication',
  'Canal agent : tools déterministes (batch), pas de recalcul LLM',
  'Portes visibles + prompts préremplis vers l’atelier Copilot',
  'Corrélations & macro observent — ils ne tradent pas',
]

const STEPS = [
  {
    n: '01',
    icon: 'filter-search',
    title: 'Scanner',
    body: 'Screener multi-classes : crypto, forex, métaux… biais, RVOL, portes.',
  },
  {
    n: '02',
    icon: 'verify',
    title: 'Lire les portes',
    body: 'Matrice ou sheet : pass / watch / fail, risque ATR, écart éventuel avec le badge.',
  },
  {
    n: '03',
    icon: 'message-programming',
    title: 'Expliquer & agir',
    body: 'Un clic → Copilot avec la question déjà formulée. Journal, watchlist ou paper sous confirmation.',
  },
]

const COMPARE = {
  without: [
    'Un croisement Tenkan/Kijun sur trois est un faux départ',
    'Deux « vérités » mélangées sans hiérarchie (badge vs portes)',
    'Un chat IA invente un BUY sans s’appuyer sur le moteur',
  ],
  with: [
    'Un signal ne compte que si la participation confirme',
    'Portes = action ; combiner = diagnostic — et le Copilot l’explique',
    'Prompts deep-link : tu n’atterris jamais sur un chat vide',
  ],
}

const STATS = [
  { value: '5', label: 'Portes du Decision Engine' },
  { value: '9', label: 'Tools engine (canal agent READ)' },
  { value: '1', label: 'Atelier Copilot plein écran' },
  { value: '0', label: 'Votes LONG/SHORT par le LLM' },
]

const FAQ = [
  {
    q: 'IchiVol donne-t-il un conseil financier ?',
    a: 'Non. Le moteur produit une lecture structurée ; le Copilot l’explique. La décision de trade reste la vôtre.',
  },
  {
    q: 'Pourquoi filtrer par volume relatif et pas juste par Ichimoku ?',
    a: 'Un croisement ou un breakout sans participation réelle est souvent un faux signal. Le RVOL (porte Participation) confirme avant de monter en conviction.',
  },
  {
    q: 'L’agent peut-il changer le verdict du moteur ?',
    a: 'Non. Il interroge le moteur (get_symbol_context, batch…) et explique DECISION_DATA. Il n’invente pas de chiffres et ne propose pas un LONG/SHORT contraire.',
  },
  {
    q: 'À quoi servent les corrélations sur Contexte ?',
    a: 'À voir qui bouge avec qui sur la watchlist (Pearson / log returns). C’est du climat de marché, pas un signal d’entrée.',
  },
  {
    q: 'Que fait « Confirmer » dans le chat ?',
    a: 'Uniquement des actions allowlistées : journal ou watchlist. Aucun ordre broker. Tu valides ou tu annules.',
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
                Voir le signal. <em>Confirmer</em> par le volume. Décider.
              </h1>
              <p className="camap-hero-lede">
                Cockpit Ichimoku × RVOL : le moteur tranche, le Copilot explique
                avec un prompt déjà prêt — journal, watchlist et paper sous ton
                contrôle.
              </p>
              <div className="camap-hero-cta">
                <Link to="/login" className="camap-btn camap-btn-primary camap-btn-lg">
                  Entrer dans le cockpit
                </Link>
                <a href="#methode" className="camap-btn camap-btn-outline camap-btn-lg">
                  Voir la méthode
                </a>
              </div>
            </div>

            <div className="camap-hero-visual-wrap camap-reveal camap-reveal-delay">
              <div className="camap-hero-visual">
                <span className="camap-hero-visual-badge">
                  <span className="camap-dot camap-dot-live" aria-hidden />
                  Pipeline · BUY
                </span>
                <MockChart />
                <div className="camap-hero-visual-footer">
                  <span>NEARUSDT · 1h</span>
                  <span className="camap-chip camap-chip-bull">RVOL 1.4×</span>
                </div>
                <div className="camap-hero-gates" aria-hidden>
                  <span className="is-pass">Direction</span>
                  <span className="is-watch">Participation</span>
                  <span className="is-pass">Location</span>
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

        <section id="methode" className="camap-section">
          <h2 className="camap-section-title">Ce que l’app traite</h2>
          <p className="camap-section-lede">
            Données live → portes → Copilot deep-link → journal / watch / paper.
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
            <p>« Un signal Ichimoku ne compte que s’il est confirmé par le volume relatif. »</p>
            <cite>Principe IchiVol</cite>
          </blockquote>
        </section>

        <section id="capacites" className="camap-section">
          <h2 className="camap-section-title">Capacités</h2>
          <p className="camap-section-lede">
            Ce qui est en place aujourd’hui dans le cockpit — pas une roadmap fantôme.
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
            Même Ichimoku. La différence : portes visibles + Copilot ancré sur le moteur.
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
              <span className="camap-compare-label">Avec IchiVol</span>
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
          <p>Décisions, Copilot atelier, Contexte, Paper — session sécurisée.</p>
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
              Cockpit Ichimoku × RVOL : portes visibles, Copilot atelier,
              corrélations en lecture seule — toi confirmes.
            </p>
          </div>

          <div className="camap-footer-cols">
            <div className="camap-footer-col">
              <h3>Produit</h3>
              <a href="#methode">Méthode</a>
              <a href="#capacites">Capacités</a>
              <a href="#comparatif">Comparatif</a>
              <a href="#faq">FAQ</a>
            </div>
            <div className="camap-footer-col">
              <h3>Cockpit</h3>
              <Link to="/login">Décisions</Link>
              <Link to="/login">Journal</Link>
              <Link to="/login">Watchlist</Link>
              <Link to="/login">Copilot</Link>
              <Link to="/login">Contexte</Link>
              <Link to="/login">Paper</Link>
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
            Moteur décide · Copilot explique · toi confirmes
          </span>
        </div>
      </footer>
    </div>
  )
}
