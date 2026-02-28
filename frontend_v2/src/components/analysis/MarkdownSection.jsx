import ReactMarkdown from 'react-markdown'

/**
 * Shared markdown renderer with consistent styling for analysis sections.
 * Supports citation links, tables, and all standard markdown elements.
 */
const MARKDOWN_COMPONENTS = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand hover:underline font-medium">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-primary">{children}</strong>,
  h2: ({ children }) => <h2 className="text-lg font-bold text-primary mt-6 mb-3">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-bold text-primary mt-4 mb-2">{children}</h3>,
  h4: ({ children }) => <h4 className="text-sm font-bold text-primary mt-3 mb-1">{children}</h4>,
  p: ({ children }) => <p className="mb-3 text-primary">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  li: ({ children }) => <li className="text-primary">{children}</li>,
  table: ({ children }) => <div className="overflow-x-auto"><table className="w-full text-sm border-collapse">{children}</table></div>,
  thead: ({ children }) => <thead className="bg-surface-tertiary">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-primary border-b border">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 text-secondary border-b border">{children}</td>,
  em: ({ children }) => <em className="text-tertiary italic">{children}</em>,
}

function MarkdownSection({ content, className = '' }) {
  if (!content) return null

  return (
    <div className={`prose max-w-none text-sm leading-relaxed ${className}`}>
      <ReactMarkdown components={MARKDOWN_COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownSection
