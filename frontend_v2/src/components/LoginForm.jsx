/**
 * Login form component.
 *
 * Props:
 * - onSuccess: Callback when login succeeds
 * - onSwitchToRegister: Callback to switch to register form
 */

import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

function LoginForm({ onSuccess, onSwitchToRegister }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await login(email, password)
      onSuccess?.()
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-md">
      <h2 className="text-2xl font-bold text-primary mb-6 text-center">
        Sign In
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-accent-danger-light border border-accent-danger text-accent-danger-dark px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-primary mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className="w-full px-4 py-2 border border-medium rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition-colors"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-primary mb-1">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="w-full px-4 py-2 border border-medium rounded-lg focus:ring-2 focus:ring-brand focus:border-brand outline-none transition-colors"
            placeholder="Enter your password"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className={`w-full py-2.5 px-4 text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${loading ? 'bg-brand-dark' : 'bg-brand'}`}
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-secondary">
        Don't have an account?{' '}
        <button
          onClick={onSwitchToRegister}
          className="font-medium hover:underline text-brand"
        >
          Create one
        </button>
      </p>
    </div>
  )
}

export default LoginForm
