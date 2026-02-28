import { useState } from 'react'

function ConvictionScore({ data }) {
  const [hoveredCategory, setHoveredCategory] = useState(null)

  if (!data) return null

  const { overall_score, recommendation, confidence, categories, summary } = data
  const displayConfidence = confidence ?? 50

  const getRecommendationColor = (rec) => {
    switch (rec) {
      case 'BUY': return { bg: 'bg-accent-success-light', text: 'text-accent-success-dark', border: 'border-accent-success' }
      case 'SELL': return { bg: 'bg-accent-danger-light', text: 'text-accent-danger-dark', border: 'border-accent-danger' }
      case 'HOLD': return { bg: 'bg-accent-warning-light', text: 'text-accent-warning-dark', border: 'border-accent-warning' }
      default: return { bg: 'bg-surface-tertiary', text: 'text-primary', border: 'border-medium' }
    }
  }

  const getScoreColor = (score) => {
    if (score >= 70) return 'bg-accent-success'
    if (score >= 55) return 'bg-accent-success-muted'
    if (score >= 40) return 'bg-accent-warning-muted'
    if (score >= 25) return 'bg-accent-danger-muted'
    return 'bg-accent-danger'
  }

  const recColor = getRecommendationColor(recommendation)

  return (
    <div className="space-y-6">
      {/* Overall Score Banner */}
      <div className={`rounded-lg p-6 border ${recColor.bg} ${recColor.border}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-secondary">Overall Conviction</p>
            <div className="flex items-baseline gap-3 mt-1">
              <p className={`text-4xl font-bold ${recColor.text}`}>{overall_score}</p>
              <p className="text-lg text-tertiary">/100</p>
            </div>
          </div>
          <div className={`px-6 py-3 rounded-lg ${recColor.bg} border ${recColor.border} text-center`}>
            <p className={`text-2xl font-bold ${recColor.text}`}>{recommendation}</p>
            <p className={`text-sm font-medium ${recColor.text} opacity-80`}>{displayConfidence}% confidence</p>
          </div>
        </div>
        {/* Overall score bar */}
        <div className="mt-4 w-full h-3 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${getScoreColor(overall_score)}`}
            style={{ width: `${overall_score}%` }}
          />
        </div>
      </div>

      {/* Summary */}
      <p className="text-sm text-primary leading-relaxed">{summary}</p>

      {/* Category Scores */}
      <div>
        <h4 className="text-lg font-semibold text-primary mb-3">Category Breakdown</h4>
        <div className="space-y-3">
          {categories?.map((cat, i) => (
            <div
              key={i}
              className="relative bg-surface-secondary rounded-lg p-4"
              onMouseEnter={() => setHoveredCategory(i)}
              onMouseLeave={() => setHoveredCategory(null)}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-primary">{cat.name}</span>
                <span className="text-sm font-bold text-primary">{cat.score}/100</span>
              </div>
              <div className="w-full h-2 bg-surface-card-hover rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${getScoreColor(cat.score)}`}
                  style={{ width: `${cat.score}%` }}
                />
              </div>
              {/* Evidence tooltip */}
              {hoveredCategory === i && cat.evidence && (
                <div className="mt-2 text-xs text-secondary bg-surface-elevated rounded p-2">
                  {cat.evidence}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ConvictionScore
