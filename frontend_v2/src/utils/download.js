import { authFetch, API_URL } from './api'

/**
 * Download a file from an export endpoint. Validates the response,
 * creates a blob URL, triggers a browser download, and cleans up.
 */
export async function downloadFile({ sessionId, endpoint, filename }) {
  const response = await authFetch(`${API_URL}/api/reports/${sessionId}/export/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })

  const contentType = response.headers.get('content-type')
  if (!response.ok || contentType?.includes('application/json')) {
    const errorData = await response.json()
    throw new Error(errorData.detail || errorData.error || `${endpoint} export failed`)
  }

  const blob = await response.blob()

  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}
