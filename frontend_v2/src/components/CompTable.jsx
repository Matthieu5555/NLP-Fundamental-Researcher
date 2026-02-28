import ReactMarkdown from 'react-markdown'

function CompTable({ content }) {
  if (!content) return null

  return (
    <div className="space-y-4">
      <div className="prose prose max-w-none text-sm leading-relaxed">
        <ReactMarkdown
          components={{
            table: ({ children }) => (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">{children}</table>
              </div>
            ),
            thead: ({ children }) => <thead className="bg-surface-tertiary">{children}</thead>,
            th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-primary border-b border">{children}</th>,
            td: ({ children }) => <td className="px-3 py-2 text-secondary border-b border">{children}</td>,
            tr: ({ children }) => <tr className="hover:bg-surface-secondary">{children}</tr>,
            strong: ({ children }) => <strong className="font-semibold text-primary">{children}</strong>,
            h2: ({ children }) => <h2 className="text-lg font-bold text-primary mt-6 mb-3">{children}</h2>,
            p: ({ children }) => <p className="mb-3 text-primary">{children}</p>,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

export default CompTable
