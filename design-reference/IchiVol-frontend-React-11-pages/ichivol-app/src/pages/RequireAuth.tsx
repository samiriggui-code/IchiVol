import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { getMe } from '../lib/auth'

type Status = 'loading' | 'authenticated' | 'anonymous'

export function RequireAuth() {
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    let cancelled = false
    getMe().then((user) => {
      if (!cancelled) setStatus(user ? 'authenticated' : 'anonymous')
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (status === 'loading') return null
  if (status === 'anonymous') return <Navigate to="/login" replace />
  return <Outlet />
}
