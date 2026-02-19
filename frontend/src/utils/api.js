/**
 * API client with authentication support.
 *
 * Provides an axios instance configured with:
 * - Base URL from environment
 * - Automatic auth token injection
 * - Token refresh on 401 errors
 * - Logout on refresh failure
 */

import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

// Token storage keys
const ACCESS_TOKEN_KEY = 'accessToken'
const REFRESH_TOKEN_KEY = 'refreshToken'

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token management functions
export const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY)
export const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY)

export const setTokens = (accessToken, refreshToken) => {
  if (accessToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  }
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
}

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

// Request interceptor - add auth header
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle 401 and refresh token
let isRefreshing = false
let refreshSubscribers = []

const subscribeTokenRefresh = (callback) => {
  refreshSubscribers.push(callback)
}

const onTokenRefreshed = (token) => {
  refreshSubscribers.forEach((callback) => callback(token))
  refreshSubscribers = []
}

const onRefreshFailed = () => {
  refreshSubscribers.forEach((callback) => callback(null))
  refreshSubscribers = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = getRefreshToken()

      // No refresh token - just reject
      if (!refreshToken) {
        clearTokens()
        return Promise.reject(error)
      }

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh((token) => {
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(api(originalRequest))
            } else {
              reject(error)
            }
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Attempt to refresh the token
        const response = await axios.post(`${API_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        })

        const { access_token } = response.data
        setTokens(access_token, null) // Keep existing refresh token

        // Update the failed request and notify subscribers
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        onTokenRefreshed(access_token)

        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed - clear tokens and notify subscribers
        clearTokens()
        onRefreshFailed()

        // Redirect to login or handle logout
        window.dispatchEvent(new CustomEvent('auth:logout'))

        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// Auth API functions
export const authAPI = {
  register: async (email, password, displayName = null) => {
    const response = await api.post('/api/auth/register', {
      email,
      password,
      display_name: displayName,
    })
    const { user, tokens } = response.data
    setTokens(tokens.access_token, tokens.refresh_token)
    return { user, tokens }
  },

  login: async (email, password) => {
    const response = await api.post('/api/auth/login', {
      email,
      password,
    })
    const { user, tokens } = response.data
    setTokens(tokens.access_token, tokens.refresh_token)
    return { user, tokens }
  },

  logout: async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        await api.post('/api/auth/logout', {
          refresh_token: refreshToken,
        })
      } catch (error) {
        // Ignore errors on logout
        console.warn('Logout request failed:', error)
      }
    }
    clearTokens()
  },

  refresh: async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      throw new Error('No refresh token')
    }
    const response = await axios.post(`${API_URL}/api/auth/refresh`, {
      refresh_token: refreshToken,
    })
    const { access_token } = response.data
    setTokens(access_token, null)
    return access_token
  },

  getMe: async () => {
    const response = await api.get('/api/auth/me')
    return response.data
  },
}

// Export the configured axios instance as default
export default api

// Export API_URL for SSE connections that need to add token as query param
export { API_URL }
