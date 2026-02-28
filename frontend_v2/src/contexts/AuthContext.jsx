/**
 * Authentication Context Provider.
 *
 * Provides global authentication state and functions:
 * - user: Current user object or null
 * - loading: Whether auth is being initialized
 * - error: Any auth error message
 * - isAuthenticated: Boolean shorthand for !!user
 * - login: Authenticate with email/password
 * - register: Create new account
 * - logout: Sign out and clear tokens
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authAPI, getAccessToken, getRefreshToken, clearTokens } from '../utils/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      const accessToken = getAccessToken()
      const refreshToken = getRefreshToken()

      if (!accessToken && !refreshToken) {
        // No tokens, user is not authenticated
        setLoading(false)
        return
      }

      try {
        // Try to get current user info
        const userData = await authAPI.getMe()
        setUser(userData)
      } catch (error) {
        // Token might be expired, try to refresh
        if (refreshToken) {
          try {
            await authAPI.refresh()
            // Retry getting user info
            const userData = await authAPI.getMe()
            setUser(userData)
          } catch (refreshError) {
            // Refresh failed, clear tokens
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

    initAuth()
  }, [])

  // Token refresh timer
  useEffect(() => {
    if (!user) return

    // Refresh token 5 minutes before expiry (25 minutes after login)
    const refreshInterval = setInterval(async () => {
      try {
        await authAPI.refresh()
      } catch (error) {
        console.warn('Background token refresh failed:', error)
        // Will be handled by API interceptor on next request
      }
    }, 25 * 60 * 1000) // 25 minutes

    return () => clearInterval(refreshInterval)
  }, [user])

  // Listen for forced logout events (from API interceptor)
  useEffect(() => {
    const handleLogout = () => {
      setUser(null)
      setError(null)
    }

    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  const login = useCallback(async (email, password) => {
    setError(null)
    try {
      const { user: userData } = await authAPI.login(email, password)
      setUser(userData)
      return userData
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed'
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
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed'
      setError(message)
      throw new Error(message)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await authAPI.logout()
    } catch (error) {
      // Ignore errors, still clear local state
      console.warn('Logout error:', error)
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
