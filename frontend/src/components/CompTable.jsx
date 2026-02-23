import ReactMarkdown from 'react-markdown'

function CompTable({ content }) {
  if (!content) return null

  return (
    <div className="space-y-4">
      <div className="prose prose-slate max-w-none text-sm leading-relaxed">
        <ReactMarkdown
          components={{
            table: ({ children }) => (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">{children}</table>
              </div>
            ),
            thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
            th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">{children}</th>,
            td: ({ children }) => <td className="px-3 py-2 text-slate-600 border-b border-slate-100">{children}</td>,
            tr: ({ children }) => <tr className="hover:bg-slate-50">{children}</tr>,
            strong: ({ children }) => <strong className="font-semibold text-slate-800">{children}</strong>,
            h2: ({ children }) => <h2 className="text-lg font-bold text-slate-800 mt-6 mb-3">{children}</h2>,
            p: ({ children }) => <p className="mb-3 text-slate-700">{children}</p>,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

export default CompTable
