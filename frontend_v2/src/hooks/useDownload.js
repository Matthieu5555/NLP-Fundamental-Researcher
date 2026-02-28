import { useState, useCallback } from 'react'
import { downloadFile } from '../utils/download'

/**
 * Manages download state for multiple export formats.
 * Returns per-format loading flags and a trigger function.
 */
export function useDownload(sessionId, ticker) {
  const [downloading, setDownloading] = useState({ docx: false, pptx: false, excel: false })

  const trigger = useCallback(async (format) => {
    const date = new Date().toISOString().split('T')[0]
    const filenames = {
      docx: `${ticker}_equity_report_${date}.docx`,
      pptx: `${ticker}_slides_${date}.pptx`,
      excel: `${ticker}_financial_model_${date}.xlsx`,
    }

    setDownloading(prev => ({ ...prev, [format]: true }))
    try {
      await downloadFile({ sessionId, endpoint: format, filename: filenames[format] })
    } catch (err) {
      console.error(`${format} download error:`, err)
      alert(`${format.charAt(0).toUpperCase() + format.slice(1)} download failed: ${err.message}`)
    } finally {
      setDownloading(prev => ({ ...prev, [format]: false }))
    }
  }, [sessionId, ticker])

  return { downloading, trigger }
}
