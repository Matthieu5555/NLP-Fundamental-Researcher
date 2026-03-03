/**
 * Authentication Context Provider.
 *
 * Provides global authentication state and functions:
 * - user: Current user object or null
 * - loading: Whether auth is being initialized
 * - error: Any auth error message
 * - isAuthenticated: Boolean shorthand for !!user
 * - authRequired: Whether the server requires login
 * - login: Authenticate with email/password
 * - register: Create new account
 * - logout: Sign out and clear tokens
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authAPI, getAccessToken, getRefreshToken, clearTokens } from '../utils/api'
import api from '../utils/api'

const AuthContext = createContext(null)

const LOCAL_USER = {
  id: 'local',
  email: 'local@localhost',
  display_name: 'Local User',
  is_active: true,
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [authRequired, setAuthRequired] = useState(true) // assume true until server says otherwise

  // Fetch auth config from server, then initialize auth state
  useEffect(() => {
    const init = async () => {
      try {
        const { data } = await api.get('/api/auth/config')
        const serverRequiresAuth = data.require_auth === true

        setAuthRequired(serverRequiresAuth)

        if (!serverRequiresAuth) {
          // Auth disabled: use local user, skip token logic entirely
          setUser(LOCAL_USER)
          setLoading(false)
          return
        }
      } catch (err) {
        // If the config endpoint is unreachable, fall back to requiring auth
        // (the server is probably down anyway so the user will see errors elsewhere)
        console.warn('Could not fetch auth config, assuming auth required:', err)
      }

      // Auth is enabled: check tokens
      const accessToken = getAccessToken()
      const refreshToken = getRefreshToken()

      if (!accessToken && !refreshToken) {
        setLoading(false)
        return
      }

      try {
        const userData = await authAPI.getMe()
        setUser(userData)
      } catch (err) {
        if (refreshToken) {
          try {
            await authAPI.refresh()
            const userData = await authAPI.getMe()
            setUser(userData)
          } catch (refreshError) {
            console.warn('Token refresh failed:', refreshError)
            clearTokens()
          }
        } else {
          clearTokens()
        }
      } finally {
        setLoading(false)
      }
    }

    init()
  }, [])

  // Token refresh timer (only when auth is enabled and user is logged in)
  useEffect(() => {
    if (!user || !authRequired) return

    const refreshInterval = setInterval(async () => {
      try {
        await authAPI.refresh()
      } catch (err) {
        console.warn('Background token refresh failed:', err)
      }
    }, 25 * 60 * 1000)

    return () => clearInterval(refreshInterval)
  }, [user, authRequired])

  // Listen for forced logout events (from API interceptor)
  useEffect(() => {
    if (!authRequired) return

    const handleLogout = () => {
      setUser(null)
      setError(null)
    }

    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [authRequired])

  const login = useCallback(async (email, password) => {
    setError(null)
    try {
      const { user: userData } = await authAPI.login(email, password)
      setUser(userData)
      return userData
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed'
      setError(message)
      throw new Error(message)
    }
  }, [])

  const register = useCallback(async (email, password, displayName = null) => {
    setError(null)
    try {
      const { user: userData } = await authAPI.register(email, password, displayName)
      setUser(userData)
      return userData
    } catch (err) {
      const message = err.response?.data?.detail || 'Registration failed'
      setError(message)
      throw new Error(message)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await authAPI.logout()
    } catch (err) {
      console.warn('Logout error:', err)
    }
    setUser(null)
    setError(null)
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    authRequired,
    login,
    register,
    logout,
    clearError,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
