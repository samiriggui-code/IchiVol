import { Link } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { IchimokuMockChart } from '../components/IchimokuMockChart'
import { ThemeToggle } from '../components/ThemeToggle'
import { VpValidationBadge } from '../components/VpValidationBadge'
import './landing.css'

const STEPS = [
  { n: '01', title: 'Marché', body: 'Prix et volume, bougie par bougie.' },
  { n: '02', title: 'Portes', body: 'Direction, participation, structure, emplacement, régime.' },
  { n: '03', title: 'Ève juge', body: 'Quatre avis et JEV : elle accepte ou refuse.', current: true },
  { n: '04', title: 'Risk Kernel', body: 'Autorise ou bloque, par portefeuille.' },
  { n: '05', title: 'Portefeuille', body: 'Position paper suivie jusqu’au stop ou à l’objectif.' },
  { n: '06', title: 'Preuves', body: 'Dossier, journal et résultat relisibles.' },
]

const FEATURES = [
  {
    meta: 'Decision Engine',
    title: 'Cinq portes avant toute action',
    body: 'Direction, participation, structure, emplacement, régime. Les portes alimentent la décision d’Ève, pas un chat qui invente un achat.',
  },
  {
    meta: 'Ève',
    title: 'Elle accepte ou refuse',
    body: 'Analyste, contradicteur, gardien du risque, audit indépendant. Si JEV répond trop tard ou sans confiance, elle s’abstient.',
  },
  {
    meta: 'Risk Kernel',
    title: 'Autonomie bornée',
    body: 'Toute ouverture paper passe par le garde-fou. Arrêt d’urgence armé : plus aucune entrée, sur aucun portefeuille.',
  },
  {
    meta: 'Veille d’actualité',
    title: 'Le contexte avant d’agir',
    body: 'Actualités et agenda résumés dans le dossier. Une actualité ne déclenche jamais un trade à elle seule.',
  },
  {
    meta: 'Strategy Lab',
    title: 'De l’idée à la preuve',
    body: 'Backtests, ablations, régimes, walk-forward : affûter les règles hors capital avant de les laisser tourner.',
  },
  {
    meta: 'Journal',
    title: 'Qui a décidé, et avait-il raison',
    body: 'Moteur seul, Ève, Manuel, Moteur contre Ève : chaque trade garde son décideur et son résultat.',
  },
]

const COMPARE: { k: string; without: string; with: string; ok?: boolean }[] = [
  {
    k: 'Qui décide',
    without: 'Un chat qui conseille d’acheter sans exécuter',
    with: 'Le moteur propose, Ève accepte ou refuse, en paper',
  },
  {
    k: 'Contre-lecture',
    without: 'Pas de modes, pas de filtre, pas de second avis',
    with: 'Quatre avis, dont un audit indépendant',
  },
  {
    k: 'Données en retard',
    without: 'Trade possible sur un signal périmé',
    with: 'Abstention si JEV est en retard ou injoignable',
    ok: true,
  },
  {
    k: 'Risque',
    without: 'Aucune borne',
    with: 'Risk Kernel et arrêt d’urgence peuvent tout bloquer',
  },
]

const FAQ = [
  {
    q: 'Ève trade vraiment ?',
    a: 'Oui, en paper, quand le pilote automatique est activé. Chaque portefeuille (IchiVol, Sessions, Futures & Crypto…) applique sa méthode et propose ; Ève accepte ou refuse à chaque nouvelle bougie. Le Risk Kernel autorise ou bloque, l’arrêt d’urgence coupe toute entrée. Aucun courtier réel.',
  },
  {
    q: 'Qu’est-ce qu’IchiVol ?',
    a: 'Un poste de trading paper : le moteur Ichimoku × RVOL calcule, chaque portefeuille propose, Ève juge, le Risk Kernel borne et le Strategy Lab affûte les règles. Jamais d’argent réel.',
  },
  {
    q: 'Le Copilot, c’est une autre IA ?',
    a: 'Le Copilot est le chat d’Ève : il explique les décisions sans jamais passer d’ordre.',
  },
  {
    q: 'Que se passe-t-il si JEV répond trop tard ?',
    a: 'Ève s’abstient : réponse trop tardive, JEV injoignable ou confiance trop faible, elle n’ouvre rien.',
  },
  {
    q: 'Le Risk Kernel peut-il être contourné ?',
    a: 'Non. Toute ouverture paper passe par le Risk Kernel. Arrêt d’urgence armé : Ève ne peut plus ouvrir.',
  },
]

export function LandingPage() {
  return (
    <div className="lp-page">
      <div className="lp-wrap">
        <nav className="lp-nav" aria-label="Navigation principale">
          <Link to="/" className="lp-brand" aria-label="IchiVol — accueil">
            <BrandMark className="lp-brand-mark" />
            <span>IchiVol</span>
          </Link>
          <a className="lp-nav-link" href="#chaine">
            Produit
          </a>
          <a className="lp-nav-link" href="#capacites">
            Ève
          </a>
          <a className="lp-nav-link" href="#faq">
            FAQ
          </a>
          <ThemeToggle />
          <Link to="/login" className="iv-btn iv-btn--primary lp-nav-cta">
            Se connecter
          </Link>
        </nav>

        <main>
          <section className="lp-hero">
            <div className="lp-hero-copy">
              <div className="iv-meta">Paper trading · jamais d’argent réel</div>
              <h1>
                Le moteur propose.
                <br />
                <em>Ève accepte ou refuse.</em>
              </h1>
              <p className="lp-lead">
                Un poste de trading où Ève, l’IA décisionnelle, juge chaque trade proposé par vos
                portefeuilles. Cinq portes, quatre avis, un garde-fou de risque qui a toujours le
                dernier mot.
              </p>
              <div className="lp-row">
                <Link to="/app/desk" className="iv-btn iv-btn--primary lp-btn-lg">
                  Ouvrir le Desk →
                </Link>
                <Link to="/app/agents" className="iv-btn iv-btn--ghost lp-btn-lg">
                  Voir un dossier d’Ève
                </Link>
              </div>
              <div className="lp-row lp-chips">
                <span className="iv-chip">Ichimoku × RVOL</span>
                <span className="iv-chip">5 portes</span>
                <span className="iv-chip">4 avis</span>
                <span className="iv-chip is-amber">Arrêt d’urgence</span>
                <VpValidationBadge />
              </div>
            </div>

            <article className="apex-card lp-dossier" aria-label="Exemple de dossier d’Ève">
              <div className="lp-dossier-head">
                <div className="iv-meta">Exemple de dossier · schéma</div>
                <span className="iv-decider is-eve">
                  <i />
                  Ève
                </span>
              </div>
              <div className="lp-verdict">
                <span className="lp-verdict-box">
                  <span className="lp-verdict-k">Moteur</span>
                  <span className="pos">Acheter</span>
                </span>
                <span className="lp-verdict-ar" aria-hidden>
                  →
                </span>
                <span className="lp-verdict-box is-ok">
                  <span className="lp-verdict-k">Ève</span>
                  <span className="ok">Accepte</span>
                </span>
              </div>
              <div className="lp-chart">
                <IchimokuMockChart />
              </div>
              <p className="iv-note lp-dossier-note">
                Cassure du nuage confirmée par le <span className="iv-kw">volume relatif</span>.{' '}
                <span className="ok">Risk Kernel : passe. Position paper ouverte.</span>
              </p>
              <div className="apex-card-foot">
                <span className="apex-card-sig">ichivol</span>
                <span className="iv-chip is-cyan">JEV</span>
                <span className="iv-chip is-mint">Risk Kernel</span>
                <span className="lp-foot-end">Illustration, aucune donnée réelle</span>
              </div>
            </article>
          </section>

          <section id="chaine" className="lp-sec">
            <div className="lp-sec-h">
              <div className="iv-label">Chaîne de trade</div>
              <h2>Du prix à la position, chaque étape se lit</h2>
            </div>
            <ol className="lp-steps">
              {STEPS.map((s) => (
                <li key={s.n} className={s.current ? 'is-current' : undefined}>
                  <span className="lp-step-n">{s.n}</span>
                  <strong>{s.title}</strong>
                  <span>{s.body}</span>
                </li>
              ))}
            </ol>
          </section>

          <section id="capacites" className="lp-sec">
            <div className="lp-sec-h">
              <div className="iv-label">Capacités</div>
              <h2>Les briques d’IchiVol</h2>
            </div>
            <div className="lp-feat">
              {FEATURES.map((f) => (
                <article key={f.meta} className="apex-card">
                  <div className="iv-meta">{f.meta}</div>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </article>
              ))}
            </div>
          </section>

          <section id="comparatif" className="lp-sec">
            <div className="lp-sec-h">
              <div className="iv-label">Comparatif</div>
              <h2>Ce qui change avec Ève</h2>
            </div>
            <div className="iv-card">
              <div className="iv-table-wrap">
                <table className="iv-table lp-cmp">
                  <thead>
                    <tr>
                      <th scope="col">
                        <span className="lp-sr">Critère</span>
                      </th>
                      <th scope="col">Chat IA classique</th>
                      <th scope="col">IchiVol · Ève</th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMPARE.map((row) => (
                      <tr key={row.k}>
                        <td className="lp-cmp-k">{row.k}</td>
                        <td className="muted" data-label="Chat IA classique">
                          {row.without}
                        </td>
                        <td className={row.ok ? 'ok' : undefined} data-label="IchiVol · Ève">
                          {row.with}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section id="faq" className="lp-sec">
            <div className="lp-sec-h">
              <div className="iv-label">FAQ</div>
              <h2>Questions fréquentes</h2>
            </div>
            <div className="lp-faq">
              {FAQ.map((item, i) => (
                <details key={item.q} open={i === 0}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </section>

          <section className="apex-card lp-closing">
            <div className="iv-label">Paper uniquement</div>
            <p>
              Pas de live, pas de conseil financier.{' '}
              <span className="iv-kw">Ève accepte ou refuse ce que le moteur propose</span>, avec de
              l’argent fictif.
            </p>
            <Link to="/login" className="iv-btn iv-btn--primary lp-btn-lg">
              Se connecter
            </Link>
            <div className="apex-card-foot">
              <span className="apex-card-sig">ichivol</span>
            </div>
          </section>
        </main>

        <footer className="lp-footer">
          <span>
            © {new Date().getFullYear()} IchiVol — trading paper, pas un conseil financier.
          </span>
          <span className="lp-footer-links">
            <a href="#chaine">Produit</a>
            <a href="#faq">FAQ</a>
            <Link to="/login">Se connecter</Link>
          </span>
        </footer>
      </div>
    </div>
  )
}
