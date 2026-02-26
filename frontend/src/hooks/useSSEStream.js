/**
 * SSE stream parsing utility.
 *
 * Handles the low-level mechanics of reading a fetch response body as a
 * Server-Sent Events stream: UTF-8 decoding, line buffering, `data: ` prefix
 * stripping, `[DONE]` termination, and JSON parsing.  All application-level
 * decisions (what to do with a parsed event, how to handle specific event
 * types) stay in the caller.
 *
 * @param {Response} response - A fetch Response whose body will be consumed.
 * @param {object}   callbacks
 * @param {(parsed: object) => void} callbacks.onJSON  - Called for each line
 *   that parses as valid JSON.  The raw text chunk is NOT passed to onText.
 * @param {(chunk: string) => void}  callbacks.onText  - Called for each
 *   non-JSON data line (plain-text streaming tokens).
 * @param {() => void}               callbacks.onDone  - Called once when the
 *   stream ends, either via `[DONE]` or natural EOF.
 * @param {(err: Error) => void}     callbacks.onError - Called on read or
 *   parse infrastructure errors.  Not called for individual JSON parse
 *   failures on a single line (those fall through to onText).
 * @returns {Promise<void>} Resolves when the stream is fully consumed.
 */
export async function parseSSEStream(response, { onJSON, onText, onDone, onError }) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        onDone?.()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // The last element may be an incomplete line — keep it in the buffer.
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue

        const data = line.substring(6)

        if (data === '[DONE]') {
          onDone?.()
          return
        }

        try {
          const parsed = JSON.parse(data)
          onJSON?.(parsed)
        } catch {
          // Not JSON — treat as a plain-text streaming token.
          onText?.(data)
        }
      }
    }
  } catch (err) {
    onError?.(err)
  }
}
