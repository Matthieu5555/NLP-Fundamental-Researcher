/**
 * SettingsModal Component
 *
 * Allows users to configure:
 * - Master system prompt (tone, language, thinking style)
 * - LLM model selection with pricing
 * - Temperature slider
 * - UI preferences (theme, cost display)
 * - Analysis preferences (chart timeframe, depth, auto-run)
 */

import { useState, useEffect } from 'react'
import api from '../utils/api'

// Default system prompt (matches backend NARRATIVE_STYLE)
const DEFAULT_SYSTEM_PROMPT = `Write in flowing prose - NOT bullet points or checklists.

FORMATTING RULES:
1. NEVER use bullet points (-, *, •)
2. NEVER use emojis
3. Write ONLY in complete sentences and paragraphs
4. Use logical transitions (Furthermore, However, Moreover, etc.)

Be concise, factual, and cite specific numbers when possible. Explain WHY something matters, not just what it is. Present both bull and bear perspectives objectively.`

// Available models with pricing (synced with backend)
const MODELS = [
  {
    id: 'anthropic/claude-3-haiku',
    name: 'Claude 3 Haiku',
    tier: 'budget',
    price: '$0.25 / $1.25',
    description: 'Fast and affordable',
  },
  {
    id: 'anthropic/claude-3.5-haiku',
    name: 'Claude 3.5 Haiku',
    tier: 'budget',
    price: '$0.80 / $4.00',
    description: 'Improved reasoning',
  },
  {
    id: 'anthropic/claude-sonnet-4',
    name: 'Claude Sonnet 4',
    tier: 'standard',
    price: '$3.00 / $15.00',
    description: 'Balanced (recommended)',
  },
  {
    id: 'anthropic/claude-opus-4',
    name: 'Claude Opus 4',
    tier: 'premium',
    price: '$15.00 / $75.00',
    description: 'Most capable',
  },
  {
    id: 'google/gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    tier: 'budget',
    price: '$0.10 / $0.40',
    description: 'Very fast and cheap',
  },
  {
    id: 'google/gemini-2.0-flash-exp',
    name: 'Gemini 2.0 Flash (Free)',
    tier: 'free',
    price: 'Free',
    description: 'Rate limited',
  },
]

const CHART_TIMEFRAMES = [
  { value: '1m', label: '1 Month' },
  { value: '3m', label: '3 Months' },
  { value: '6m', label: '6 Months' },
  { value: '1y', label: '1 Year' },
  { value: '5y', label: '5 Years' },
]

const ANALYSIS_DEPTHS = [
  { value: 'quick', label: 'Quick', description: 'Faster, cheaper' },
  { value: 'standard', label: 'Standard', description: 'Balanced' },
  { value: 'deep', label: 'Deep', description: 'Thorough, more expensive' },
]

// Apply theme to document
const applyTheme = (theme) => {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export default function SettingsModal({ isOpen, onClose }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  // Form state
  const [formState, setFormState] = useState({
    master_system_prompt: DEFAULT_SYSTEM_PROMPT,
    llm_model: 'anthropic/claude-sonnet-4',
    temperature: 0.7,
    theme: 'light',
    show_cost_tracking: true,
    default_chart_timeframe: '1y',
    analysis_depth: 'standard',
    auto_run_analysis: false,
  })

  // Track if there are unsaved changes
  const [originalState, setOriginalState] = useState(null)

  useEffect(() => {
    if (!isOpen) return

    const fetchSettings = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await api.get('/api/settings/')
        const settings = response.data
        // Use default prompt if user hasn't customized it
        const masterPrompt = settings.master_system_prompt || DEFAULT_SYSTEM_PROMPT
        setFormState({
          master_system_prompt: masterPrompt,
          llm_model: settings.llm_model || 'anthropic/claude-sonnet-4',
          temperature: settings.temperature ?? 0.7,
          theme: settings.theme || 'light',
          show_cost_tracking: settings.show_cost_tracking ?? true,
          default_chart_timeframe: settings.default_chart_timeframe || '1y',
          analysis_depth: settings.analysis_depth || 'standard',
          auto_run_analysis: settings.auto_run_analysis ?? false,
        })
        setOriginalState({ ...settings, master_system_prompt: masterPrompt })
        // Apply saved theme
        applyTheme(settings.theme || 'light')
      } catch (err) {
        console.error('Failed to fetch settings:', err)
        setError('Failed to load settings')
      } finally {
        setLoading(false)
      }
    }

    fetchSettings()
  }, [isOpen])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      await api.put('/api/settings/', formState)
      setOriginalState(formState)
      // Apply theme immediately
      applyTheme(formState.theme)
      setSuccessMessage('Settings saved successfully')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      console.error('Failed to save settings:', err)
      setError('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('Reset all settings to defaults?')) return

    setSaving(true)
    setError(null)

    try {
      const response = await api.post('/api/settings/reset')
      const settings = response.data
      const masterPrompt = settings.master_system_prompt || DEFAULT_SYSTEM_PROMPT
      const newFormState = {
        master_system_prompt: masterPrompt,
        llm_model: settings.llm_model || 'anthropic/claude-sonnet-4',
        temperature: settings.temperature ?? 0.7,
        theme: settings.theme || 'light',
        show_cost_tracking: settings.show_cost_tracking ?? true,
        default_chart_timeframe: settings.default_chart_timeframe || '1y',
        analysis_depth: settings.analysis_depth || 'standard',
        auto_run_analysis: settings.auto_run_analysis ?? false,
      }
      setFormState(newFormState)
      setOriginalState({ ...settings, master_system_prompt: masterPrompt })
      // Apply theme
      applyTheme(settings.theme || 'light')
      setSuccessMessage('Settings reset to defaults')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      console.error('Failed to reset settings:', err)
      setError('Failed to reset settings')
    } finally {
      setSaving(false)
    }
  }

  const updateField = (field, value) => {
    setFormState((prev) => ({ ...prev, [field]: value }))
  }

  const hasChanges = JSON.stringify(formState) !== JSON.stringify(originalState)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-amber-600 to-amber-700 px-6 py-4 flex-shrink-0">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-white">Settings</h2>
            <button
              onClick={onClose}
              className="text-white/80 hover:text-white transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content - Scrollable */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
            </div>
          ) : error && !formState ? (
            <div className="text-center py-8 text-red-600">{error}</div>
          ) : (
            <div className="space-y-8">
              {/* Success/Error Messages */}
              {successMessage && (
                <div className="bg-green-50 text-green-700 px-4 py-3 rounded-lg text-sm">
                  {successMessage}
                </div>
              )}
              {error && (
                <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}

              {/* Master System Prompt */}
              <section>
                <h3 className="text-sm font-medium text-slate-700 mb-2">
                  Master System Prompt
                </h3>
                <p className="text-xs text-slate-500 mb-3">
                  Custom instructions applied to ALL analysis. Control tone, language, focus areas, or thinking style.
                </p>
                <textarea
                  value={formState.master_system_prompt}
                  onChange={(e) => updateField('master_system_prompt', e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 resize-none"
                  placeholder="e.g., 'Focus on cash flow metrics. Be concise. Highlight regulatory risks. Write in a skeptical tone.'"
                />
              </section>

              {/* LLM Configuration */}
              <section>
                <h3 className="text-sm font-medium text-slate-700 mb-4">
                  LLM Configuration
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Model Selector */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-2">
                      Model
                    </label>
                    <select
                      value={formState.llm_model}
                      onChange={(e) => updateField('llm_model', e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                    >
                      {MODELS.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name} ({model.price}/1M)
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-xs text-slate-500">
                      {MODELS.find((m) => m.id === formState.llm_model)?.description}
                    </p>
                  </div>

                  {/* Temperature Slider */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-2">
                      Temperature: {formState.temperature.toFixed(1)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={formState.temperature}
                      onChange={(e) => updateField('temperature', parseFloat(e.target.value))}
                      className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-600"
                    />
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>Precise</span>
                      <span>Balanced</span>
                      <span>Creative</span>
                    </div>
                  </div>
                </div>
              </section>

              {/* UI Preferences */}
              <section>
                <h3 className="text-sm font-medium text-slate-700 mb-4">
                  UI Preferences
                </h3>
                <div className="space-y-4">
                  {/* Theme Toggle */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-2">
                      Theme
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => updateField('theme', 'light')}
                        className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                          formState.theme === 'light'
                            ? 'bg-amber-100 border-amber-500 text-amber-700'
                            : 'bg-white border-slate-300 text-slate-600 hover:border-slate-400'
                        }`}
                      >
                        Light
                      </button>
                      <button
                        onClick={() => updateField('theme', 'dark')}
                        className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                          formState.theme === 'dark'
                            ? 'bg-amber-100 border-amber-500 text-amber-700'
                            : 'bg-white border-slate-300 text-slate-600 hover:border-slate-400'
                        }`}
                      >
                        Dark
                      </button>
                    </div>
                  </div>

                  {/* Cost Tracking Toggle */}
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formState.show_cost_tracking}
                      onChange={(e) => updateField('show_cost_tracking', e.target.checked)}
                      className="w-4 h-4 text-amber-600 border-slate-300 rounded focus:ring-amber-500"
                    />
                    <span className="text-sm text-slate-700">
                      Show cost tracking in analysis view
                    </span>
                  </label>
                </div>
              </section>

              {/* Analysis Preferences */}
              <section>
                <h3 className="text-sm font-medium text-slate-700 mb-4">
                  Analysis Preferences
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Default Chart Timeframe */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-2">
                      Default Chart Timeframe
                    </label>
                    <select
                      value={formState.default_chart_timeframe}
                      onChange={(e) => updateField('default_chart_timeframe', e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                    >
                      {CHART_TIMEFRAMES.map((tf) => (
                        <option key={tf.value} value={tf.value}>
                          {tf.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Analysis Depth */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-2">
                      Analysis Depth
                    </label>
                    <select
                      value={formState.analysis_depth}
                      onChange={(e) => updateField('analysis_depth', e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                    >
                      {ANALYSIS_DEPTHS.map((depth) => (
                        <option key={depth.value} value={depth.value}>
                          {depth.label} - {depth.description}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Auto-run Toggle */}
                <label className="flex items-center gap-3 cursor-pointer mt-4">
                  <input
                    type="checkbox"
                    checked={formState.auto_run_analysis}
                    onChange={(e) => updateField('auto_run_analysis', e.target.checked)}
                    className="w-4 h-4 text-amber-600 border-slate-300 rounded focus:ring-amber-500"
                  />
                  <span className="text-sm text-slate-700">
                    Auto-run analysis when ticker is selected
                  </span>
                </label>
              </section>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex justify-between items-center flex-shrink-0">
          <button
            onClick={handleReset}
            disabled={saving}
            className="text-sm text-slate-600 hover:text-slate-800 transition-colors disabled:opacity-50"
          >
            Reset to Defaults
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="px-4 py-2 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
