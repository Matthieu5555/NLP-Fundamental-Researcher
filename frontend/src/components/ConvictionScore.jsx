import { useState } from 'react'

function ConvictionScore({ convictionData }) {
  const [hoveredCategory, setHoveredCategory] = useState(null)

  if (!convictionData) return null

  const { overall_score, recommendation, categories, summary } = convictionData

  const getRecommendationColor = (rec) => {
    switch (rec) {
      case 'BUY': return { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300' }
      case 'SELL': return { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300' }
      default: return { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300' }
    }
  }

  const getScoreColor = (score) => {
    if (score >= 70) return 'bg-green-500'
    if (score >= 55) return 'bg-green-400'
    if (score >= 40) return 'bg-amber-400'
    if (score >= 25) return 'bg-red-400'
    return 'bg-red-500'
  }

  const recColor = getRecommendationColor(recommendation)

  return (
    <div className="space-y-6">
      {/* Overall Score Banner */}
      <div className={`rounded-xl p-6 border-2 ${recColor.bg} ${recColor.border}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-600">Overall Conviction</p>
            <div className="flex items-baseline gap-3 mt-1">
              <p className={`text-4xl font-bold ${recColor.text}`}>{overall_score}</p>
              <p className="text-lg text-slate-500">/100</p>
            </div>
          </div>
          <div className={`px-6 py-3 rounded-xl ${recColor.bg} border ${recColor.border}`}>
            <p className={`text-2xl font-bold ${recColor.text}`}>{recommendation}</p>
          </div>
        </div>
        {/* Overall score bar */}
        <div className="mt-4 w-full h-3 bg-white/50 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${getScoreColor(overall_score)}`}
            style={{ width: `${overall_score}%` }}
          />
        </div>
      </div>

      {/* Summary */}
      <p className="text-sm text-slate-700 leading-relaxed">{summary}</p>

      {/* Category Scores */}
      <div>
        <h4 className="text-lg font-semibold text-slate-700 mb-3">Category Breakdown</h4>
        <div className="space-y-3">
          {categories?.map((cat, i) => (
            <div
              key={i}
              className="relative bg-slate-50 rounded-lg p-4 border border-slate-200"
              onMouseEnter={() => setHoveredCategory(i)}
              onMouseLeave={() => setHoveredCategory(null)}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-slate-700">{cat.name}</span>
                <span className="text-sm font-bold text-slate-800">{cat.score}/100</span>
              </div>
              <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${getScoreColor(cat.score)}`}
                  style={{ width: `${cat.score}%` }}
                />
              </div>
              {/* Evidence tooltip */}
              {hoveredCategory === i && cat.evidence && (
                <div className="mt-2 text-xs text-slate-600 bg-white rounded p-2 border border-slate-200">
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
