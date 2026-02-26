import { useState, useEffect, useRef, useCallback } from 'react'
import { createChart, ColorType, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts'
import { authFetch, API_URL } from '../utils/api'

// Timeframes available
const TIMEFRAMES = ['1W', '1M', '3M', '6M', 'YTD', '1Y', '2Y', '5Y', '10Y']

// Get colors from CSS variables (respects dark mode)
const getChartColors = () => {
  const styles = getComputedStyle(document.documentElement)
  const isDark = document.documentElement.classList.contains('dark')

  return {
    background: styles.getPropertyValue('--chart-background').trim() || (isDark ? '#1e293b' : '#ffffff'),
    text: styles.getPropertyValue('--chart-text').trim() || (isDark ? '#e2e8f0' : '#1e293b'),
    grid: styles.getPropertyValue('--chart-grid').trim() || (isDark ? '#334155' : '#e2e8f0'),
    bullish: styles.getPropertyValue('--chart-bullish').trim() || '#22c55e',
    bearish: styles.getPropertyValue('--chart-bearish').trim() || '#ef4444',
    sma20: styles.getPropertyValue('--chart-sma20').trim() || '#3b82f6',
    sma50: styles.getPropertyValue('--chart-sma50').trim() || '#8b5cf6',
    sma200: styles.getPropertyValue('--chart-sma200').trim() || '#f59e0b',
    bollingerFill: isDark ? 'rgba(156, 163, 175, 0.1)' : 'rgba(156, 163, 175, 0.15)',
    bollingerLine: styles.getPropertyValue('--chart-bollinger-line').trim() || '#9ca3af',
    rsiLine: styles.getPropertyValue('--chart-rsi-line').trim() || '#6366f1',
    rsiOverbought: styles.getPropertyValue('--chart-rsi-overbought').trim() || '#ef4444',
    rsiOversold: styles.getPropertyValue('--chart-rsi-oversold').trim() || '#22c55e',
    macdLine: styles.getPropertyValue('--chart-macd-line').trim() || '#3b82f6',
    macdSignal: styles.getPropertyValue('--chart-macd-signal').trim() || '#f59e0b',
    volume: isDark ? 'rgba(100, 116, 139, 0.3)' : 'rgba(100, 116, 139, 0.5)',
  }
}

function TechnicalChart({ ticker }) {
  const [timeframe, setTimeframe] = useState('1Y')
  const [chartData, setChartData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'))

  // Refs for chart containers
  const mainChartRef = useRef(null)
  const rsiChartRef = useRef(null)
  const macdChartRef = useRef(null)
  const volumeChartRef = useRef(null)

  // Refs for chart instances
  const mainChartInstance = useRef(null)
  const rsiChartInstance = useRef(null)
  const macdChartInstance = useRef(null)
  const volumeChartInstance = useRef(null)

  // Listen for theme changes
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          setIsDark(document.documentElement.classList.contains('dark'))
        }
      })
    })
    observer.observe(document.documentElement, { attributes: true })
    return () => observer.disconnect()
  }, [])

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await authFetch(`${API_URL}/api/chart/${ticker}/data?timeframe=${timeframe}`)
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.error || 'Failed to fetch chart data')
      }
      const data = await response.json()
      setChartData(data)
    } catch (err) {
      console.error('Chart data fetch error:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [ticker, timeframe])

  useEffect(() => {
    if (ticker) {
      fetchData()
    }
  }, [ticker, timeframe, fetchData])

  // Create and update charts
  useEffect(() => {
    if (!chartData || loading) return

    // Get current theme colors
    const COLORS = getChartColors()

    // Cleanup existing charts
    const cleanup = () => {
      try {
        if (mainChartInstance.current) {
          mainChartInstance.current.remove()
          mainChartInstance.current = null
        }
        if (rsiChartInstance.current) {
          rsiChartInstance.current.remove()
          rsiChartInstance.current = null
        }
        if (macdChartInstance.current) {
          macdChartInstance.current.remove()
          macdChartInstance.current = null
        }
        if (volumeChartInstance.current) {
          volumeChartInstance.current.remove()
          volumeChartInstance.current = null
        }
      } catch (err) {
        console.error('Chart cleanup error:', err)
      }
    }

    cleanup()

    // Chart options
    const chartOptions = {
      layout: {
        background: { type: ColorType.Solid, color: COLORS.background },
        textColor: COLORS.text,
      },
      grid: {
        vertLines: { color: COLORS.grid },
        horzLines: { color: COLORS.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: COLORS.grid,
      },
      timeScale: {
        borderColor: COLORS.grid,
        timeVisible: true,
      },
      handleScroll: false,
      handleScale: false,
    }

    // Wrap chart creation in try-catch to prevent crashes
    try {
      // === MAIN CHART (Candlesticks + SMAs + Bollinger) ===
      if (mainChartRef.current) {
        const mainChart = createChart(mainChartRef.current, {
          ...chartOptions,
          height: 300,
        })
        mainChartInstance.current = mainChart

        // Candlestick series (v5 API)
        const candlestickSeries = mainChart.addSeries(CandlestickSeries, {
          upColor: COLORS.bullish,
          downColor: COLORS.bearish,
          borderUpColor: COLORS.bullish,
          borderDownColor: COLORS.bearish,
          wickUpColor: COLORS.bullish,
          wickDownColor: COLORS.bearish,
        })
        candlestickSeries.setData(chartData.ohlcv)

        // Bollinger Bands (area + lines)
        if (chartData.indicators.bollinger?.length > 0) {
          // Upper band line
          const bbUpperSeries = mainChart.addSeries(LineSeries, {
            color: COLORS.bollingerLine,
            lineWidth: 1,
            lineStyle: 2, // Dashed
          })
          bbUpperSeries.setData(chartData.indicators.bollinger.map(d => ({ time: d.time, value: d.upper })))

          // Lower band line
          const bbLowerSeries = mainChart.addSeries(LineSeries, {
            color: COLORS.bollingerLine,
            lineWidth: 1,
            lineStyle: 2,
          })
          bbLowerSeries.setData(chartData.indicators.bollinger.map(d => ({ time: d.time, value: d.lower })))
        }

        // SMA 20
        if (chartData.indicators.sma_20?.length > 0) {
          const sma20Series = mainChart.addSeries(LineSeries, {
            color: COLORS.sma20,
            lineWidth: 1,
          })
          sma20Series.setData(chartData.indicators.sma_20)
        }

        // SMA 50
        if (chartData.indicators.sma_50?.length > 0) {
          const sma50Series = mainChart.addSeries(LineSeries, {
            color: COLORS.sma50,
            lineWidth: 1,
          })
          sma50Series.setData(chartData.indicators.sma_50)
        }

        // SMA 200
        if (chartData.indicators.sma_200?.length > 0) {
          const sma200Series = mainChart.addSeries(LineSeries, {
            color: COLORS.sma200,
            lineWidth: 1,
          })
          sma200Series.setData(chartData.indicators.sma_200)
        }

        mainChart.timeScale().fitContent()
      }

      // === RSI CHART ===
      if (rsiChartRef.current && chartData.indicators.rsi?.length > 0) {
        const rsiChart = createChart(rsiChartRef.current, {
          ...chartOptions,
          height: 100,
        })
        rsiChartInstance.current = rsiChart

        const rsiSeries = rsiChart.addSeries(LineSeries, {
          color: COLORS.rsiLine,
          lineWidth: 2,
        })
        rsiSeries.setData(chartData.indicators.rsi)

        // Overbought/oversold reference lines
        rsiSeries.createPriceLine({
          price: 70,
          color: COLORS.rsiOverbought,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: '',
        })
        rsiSeries.createPriceLine({
          price: 30,
          color: COLORS.rsiOversold,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: '',
        })

        rsiChart.priceScale('right').applyOptions({
          scaleMargins: { top: 0.1, bottom: 0.1 },
        })
        rsiChart.timeScale().fitContent()
      }

      // === MACD CHART ===
      if (macdChartRef.current && chartData.indicators.macd?.length > 0) {
        const macdChart = createChart(macdChartRef.current, {
          ...chartOptions,
          height: 100,
        })
        macdChartInstance.current = macdChart

        // MACD line
        const macdLineSeries = macdChart.addSeries(LineSeries, {
          color: COLORS.macdLine,
          lineWidth: 2,
        })
        macdLineSeries.setData(chartData.indicators.macd.map(d => ({ time: d.time, value: d.macd })))

        // Signal line
        const signalSeries = macdChart.addSeries(LineSeries, {
          color: COLORS.macdSignal,
          lineWidth: 2,
        })
        signalSeries.setData(chartData.indicators.macd.map(d => ({ time: d.time, value: d.signal })))

        // Histogram
        const histogramSeries = macdChart.addSeries(HistogramSeries, {
          color: COLORS.bullish,
        })
        histogramSeries.setData(chartData.indicators.macd.map(d => ({
          time: d.time,
          value: d.histogram,
          color: d.histogram >= 0 ? COLORS.bullish : COLORS.bearish,
        })))

        macdChart.priceScale('right').applyOptions({
          scaleMargins: { top: 0.1, bottom: 0.1 },
        })
        macdChart.timeScale().fitContent()
      }

      // === VOLUME CHART ===
      if (volumeChartRef.current) {
        const volumeChart = createChart(volumeChartRef.current, {
          ...chartOptions,
          height: 80,
        })
        volumeChartInstance.current = volumeChart

        const volumeSeries = volumeChart.addSeries(HistogramSeries, {
          color: COLORS.volume,
          priceFormat: {
            type: 'volume',
          },
        })
        volumeSeries.setData(chartData.ohlcv.map((d, i, arr) => ({
          time: d.time,
          value: d.volume,
          color: i > 0 && d.close >= arr[i-1].close ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)',
        })))

        volumeChart.priceScale('right').applyOptions({
          scaleMargins: { top: 0.1, bottom: 0.1 },
        })
        volumeChart.timeScale().fitContent()
      }

      // Sync time scales
      const syncTimeScales = () => {
        const charts = [mainChartInstance.current, rsiChartInstance.current, macdChartInstance.current, volumeChartInstance.current].filter(Boolean)
        if (charts.length < 2) return

        const mainChart = charts[0]
        const mainTimeScale = mainChart.timeScale()

        charts.slice(1).forEach(chart => {
          mainTimeScale.subscribeVisibleLogicalRangeChange(range => {
            if (range) {
              chart.timeScale().setVisibleLogicalRange(range)
            }
          })
        })
      }
      syncTimeScales()
    } catch (err) {
      console.error('Chart creation error:', err)
      setError('Failed to render chart: ' + err.message)
      return
    }

    // Handle resize
    const handleResize = () => {
      const width = mainChartRef.current?.clientWidth || 600
      mainChartInstance.current?.applyOptions({ width })
      rsiChartInstance.current?.applyOptions({ width })
      macdChartInstance.current?.applyOptions({ width })
      volumeChartInstance.current?.applyOptions({ width })
    }
    window.addEventListener('resize', handleResize)
    handleResize()

    return () => {
      window.removeEventListener('resize', handleResize)
      cleanup()
    }
  }, [chartData, loading, isDark])

  // Price change styling
  const priceChangeColor = chartData?.price_change >= 0 ? 'text-accent-success' : 'text-accent-danger'
  const priceChangeSign = chartData?.price_change >= 0 ? '+' : ''

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      {/* Header with price and timeframe selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        {/* Price info */}
        <div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-bold text-slate-800">
              ${chartData?.current_price?.toFixed(2) || '--'}
            </span>
            {chartData && (
              <span className={`text-sm font-medium ${priceChangeColor}`}>
                {priceChangeSign}{chartData.price_change?.toFixed(2)} ({priceChangeSign}{chartData.price_change_pct?.toFixed(2)}%)
              </span>
            )}
          </div>
          {chartData?.summary && (
            <div className="flex flex-wrap gap-3 mt-1 text-xs text-slate-500">
              <span>RSI: <span className={chartData.summary.rsi > 70 ? 'text-accent-danger font-medium' : chartData.summary.rsi < 30 ? 'text-accent-success font-medium' : ''}>{chartData.summary.rsi?.toFixed(1) || '--'}</span></span>
              <span>Trend: <span className={`font-medium ${chartData.summary.trend === 'bullish' ? 'text-accent-success' : chartData.summary.trend === 'bearish' ? 'text-accent-danger' : ''}`}>{chartData.summary.trend}</span></span>
              <span>Vol: {chartData.summary.volume_ratio?.toFixed(2)}x avg</span>
            </div>
          )}
        </div>

        {/* Timeframe buttons */}
        <div className="flex flex-wrap gap-1">
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                timeframe === tf
                  ? 'bg-brand text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--brand-primary)', borderTopColor: 'transparent' }}></div>
          <span className="ml-3 text-slate-600">Loading chart data...</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="text-center py-12 text-accent-danger">
          <p className="font-medium">Failed to load chart</p>
          <p className="text-sm mt-1">{error}</p>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger-dark text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {/* Charts */}
      {!loading && !error && chartData && (
        <div className="space-y-2">
          {/* Legend */}
          <div className="flex flex-wrap gap-4 text-xs text-slate-500 mb-2">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5" style={{ backgroundColor: 'var(--chart-sma20)' }}></span> SMA 20
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5" style={{ backgroundColor: 'var(--chart-sma50)' }}></span> SMA 50
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5" style={{ backgroundColor: 'var(--chart-sma200)' }}></span> SMA 200
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-gray-400" style={{ borderStyle: 'dashed' }}></span> Bollinger Bands
            </span>
          </div>

          {/* Main price chart */}
          <div className="border-b border-slate-100">
            <div ref={mainChartRef} className="w-full" />
          </div>

          {/* RSI */}
          <div className="border-b border-slate-100">
            <div className="text-xs text-slate-500 font-medium mb-1">RSI (14)</div>
            <div ref={rsiChartRef} className="w-full" />
          </div>

          {/* MACD */}
          <div className="border-b border-slate-100">
            <div className="text-xs text-slate-500 font-medium mb-1">MACD (12, 26, 9)</div>
            <div ref={macdChartRef} className="w-full" />
          </div>

          {/* Volume */}
          <div>
            <div className="text-xs text-slate-500 font-medium mb-1">Volume</div>
            <div ref={volumeChartRef} className="w-full" />
          </div>
        </div>
      )}
    </div>
  )
}

export default TechnicalChart
