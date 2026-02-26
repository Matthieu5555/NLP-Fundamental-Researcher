import React from 'react'

/**
 * Error Boundary for catching chart rendering errors.
 * Prevents white screen crashes when lightweight-charts throws.
 */
class ChartErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Chart Error Boundary caught error:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
          <div className="text-accent-danger mb-4">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-2">Chart Failed to Load</h3>
          <p className="text-sm text-slate-600 mb-4">
            {this.state.error?.message || 'An error occurred while rendering the chart.'}
          </p>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors text-sm font-medium"
          >
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ChartErrorBoundary
