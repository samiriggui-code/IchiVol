import { type FormEvent, useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { IchimokuMockChart } from '../components/IchimokuMockChart'
import { ThemeToggle } from '../components/ThemeToggle'
import { getMe, login } from '../lib/auth'
import './landing.css'

const DEV_EMAIL = import.meta.env.VITE_DEV_ADMIN_EMAIL as string | undefined
const DEV_PASSWORD = import.meta.env.VITE_DEV_ADMIN_PASSWORD as string | undefined
const HAS_DEV_HINT = Boolean(DEV_EMAIL && DEV_PASSWORD)

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState(DEV_EMAIL ?? '')
  const [password, setPassword] = useState(DEV_PASSWORD ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [checked, setChecked] = useState(false)
  const [alreadyIn, setAlreadyIn] = useState(false)

  useEffect(() => {
    getMe().then((user) => {
      setAlreadyIn(user != null)
      setChecked(true)
    })
  }, [])

  if (alreadyIn) {
    return <Navigate to="/app" replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    const res = await login(email, password)
    setSubmitting(false)
    if (!res.ok) {
      setError(res.error)
      return
    }
    navigate('/app', { replace: true })
  }

  return (
    <div className="lp-page lg-page">
      <aside className="lg-brand" aria-label="Présentation IchiVol">
        <div className="lg-brand-top">
          <Link to="/" className="lp-brand" aria-label="IchiVol — accueil">
            <BrandMark className="lp-brand-mark" />
            <span>IchiVol</span>
          </Link>
          <span className="iv-pill is-amber">PAPER</span>
          <span className="lg-brand-toggle">
            <ThemeToggle />
          </span>
        </div>
        <div className="lg-brand-mid">
          <div className="iv-label">Principe IchiVol</div>
          <p className="lg-quote">
            «{'\u00a0'}Un signal Ichimoku ne compte que s’il est confirmé par le{' '}
            <span className="iv-kw">volume relatif</span>.{'\u00a0'}»
          </p>
          <div className="lp-chart lg-chart">
            <IchimokuMockChart />
          </div>
        </div>
        <div className="lg-brand-foot iv-cap">
          <span>Tenkan · Kijun · nuage · volume</span>
          <span className="lg-sig">◆ ichivol</span>
        </div>
      </aside>

      <div className="lg-form-side">
        <form className="lg-form" onSubmit={onSubmit}>
          <div className="iv-meta">Accès admin unique</div>
          <h1>Connexion</h1>

          {HAS_DEV_HINT && (
            <div className="lg-dev-hint">
              <span className="iv-tag is-amber">Dev</span>
              <div>
                <code>{DEV_EMAIL}</code>
                <code>{DEV_PASSWORD}</code>
              </div>
            </div>
          )}

          <div className="iv-field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              className="iv-input lg-input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="iv-field">
            <label htmlFor="login-password">Mot de passe</label>
            <input
              id="login-password"
              className="iv-input lg-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="lg-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="iv-btn iv-btn--primary lg-submit"
            disabled={submitting || !checked}
          >
            {submitting ? 'Connexion…' : 'Se connecter'}
          </button>
          <p className="iv-note lg-foot-note">
            Paper uniquement : aucun ordre n’est envoyé à l’extérieur.
          </p>
          <Link to="/" className="lg-back">
            ← Retour à l’accueil
          </Link>
        </form>
      </div>
    </div>
  )
}
