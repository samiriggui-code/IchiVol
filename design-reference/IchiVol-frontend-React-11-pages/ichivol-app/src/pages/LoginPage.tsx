import { type FormEvent, useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'
import { IchimokuMockChart } from '../components/IchimokuMockChart'
import { KeenIcon } from '../components/KeenIcon'
import { ThemeToggle } from '../components/ThemeToggle'
import { getMe, login } from '../lib/auth'

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
    <div className="camap-shell camap-login-page">
      {/* Metronic branded: form column (left on desktop) */}
      <div className="camap-login-form-side">
        <div className="camap-login-form-wrap">
          <div className="camap-login-top">
            <Link to="/" className="camap-brand camap-login-form-mark">
              <BrandMark className="camap-mark" />
              <span className="camap-word">IchiVol</span>
            </Link>
            <ThemeToggle />
          </div>

          <form className="camap-login-card" onSubmit={onSubmit}>
            <div className="camap-login-card-head">
              <h1>Connexion</h1>
              <p className="camap-login-lede">Accès admin unique.</p>
            </div>

            {HAS_DEV_HINT && (
              <div className="camap-dev-hint">
                <span className="camap-dev-hint-tag">Dev</span>
                <div>
                  <p>
                    <code>{DEV_EMAIL}</code>
                  </p>
                  <p>
                    <code>{DEV_PASSWORD}</code>
                  </p>
                </div>
              </div>
            )}

            <label className="camap-field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="camap-field">
              <span>Mot de passe</span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </label>

            {error && <p className="camap-form-error">{error}</p>}

            <button
              type="submit"
              className="camap-btn camap-btn-primary camap-btn-lg camap-btn-block"
              disabled={submitting || !checked}
            >
              {submitting ? 'Connexion…' : 'Se connecter'}
            </button>
            <Link to="/" className="camap-back">
              ← Retour à l’accueil
            </Link>
          </form>
        </div>
      </div>

      {/* Metronic branded: inset brand panel (right on desktop) */}
      <aside className="camap-login-brand" aria-label="Présentation IchiVol">
        <div className="camap-login-brand-panel">
          <div className="camap-login-brand-glow" aria-hidden />

          <Link to="/" className="camap-brand camap-login-brand-mark">
            <BrandMark className="camap-mark" />
            <span className="camap-word">IchiVol</span>
          </Link>

          <div className="camap-login-brand-mid">
            <div className="camap-login-brand-copy">
              <p className="camap-login-brand-lockup">IchiVol</p>
              <p className="camap-eyebrow">
                <KeenIcon icon="abstract-26" style="outline" className="camap-eyebrow-icon" />
                Trading · Desk paper
              </p>
              <h1>
                Observer. Qualifier. <em>Décider.</em>
              </h1>
              <p className="camap-login-brand-lede">
                Accès au Desk : opportunités, portefeuille, journal et Copilot ancré sur le
                moteur — sans jamais inventer le BUY.
              </p>
            </div>

            <div className="camap-hero-visual camap-login-brand-visual">
              <span className="camap-hero-visual-badge">
                <span className="camap-dot camap-dot-live" aria-hidden />
                Signal confirmé
              </span>
              <IchimokuMockChart />
              <div className="camap-hero-visual-footer">
                <span>BTCUSDT · 1h</span>
                <span className="camap-chip camap-chip-bull">RVOL 2.4×</span>
              </div>
            </div>
          </div>

          <blockquote className="camap-login-quote">
            <p>« Un signal Ichimoku ne compte que s’il est confirmé par le volume relatif. »</p>
            <cite>Principe IchiVol</cite>
          </blockquote>
        </div>
      </aside>
    </div>
  )
}
