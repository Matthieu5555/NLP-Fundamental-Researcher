# PDF Sources & Unified RAG System

## Overview

Add user-uploaded PDFs as a first-class source type, with OCR support, vector embeddings, and unified retrieval across all data sources. The system is analyst-centric: user beliefs have highest priority, followed by user-provided documents.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Sources Tab (existing)                       │
│  + [Upload PDF] button                                           │
│  + User PDFs listed alongside SEC/news sources                   │
│  + Remove/exclude functionality                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PDF Processing Pipeline                      │
│  1. PyMuPDF (fitz) for native text extraction                   │
│  2. Tesseract OCR for scanned pages (fallback)                  │
│  3. Chunk into ~500 token segments with 10% overlap             │
│  4. Embed with user's configured embedding model                │
│  5. Store in session-specific FAISS index                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               Unified RAG Engine (extended)                      │
│                                                                 │
│  PRIORITY ORDER:                                                │
│  1. User beliefs (always injected, from BeliefGraph)            │
│  2. User PDFs (embedded, semantic search)                       │
│  3. SEC filings (existing FAISS infrastructure)                 │
│  4. News/Web (Gemini Search Grounding)                          │
│                                                                 │
│  Context builder fits all into window with smart truncation     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Source Priority System

| Priority | Source Type | Retrieval Method | Notes |
|----------|-------------|------------------|-------|
| 1 | User Beliefs | BeliefGraph query | Always included, analyst's own conclusions |
| 2 | User PDFs | FAISS semantic search | Research reports, transcripts, notes |
| 3 | SEC Filings | FAISS semantic search | 10-K, 10-Q (existing infrastructure) |
| 4 | News/Web | Gemini Search Grounding | Real-time, query-triggered |

---

## Embedding Model Configuration

Embedding model matches LLM provider selection in settings:

| LLM Provider | Embedding Model | Cost | Dimensions |
|--------------|-----------------|------|------------|
| Claude/OpenAI (OpenRouter) | `text-embedding-3-small` | $0.02/1M tokens | 1536 |
| Gemini | `text-embedding-004` | Free (1500 RPM) | 768 |
| Local fallback | `all-MiniLM-L6-v2` | Free | 384 |

Add to `user_settings` table:
```sql
embedding_model TEXT DEFAULT 'auto'  -- 'auto' matches LLM, or explicit choice
```

---

## New Files to Create

### 1. `backend/core/pdf_processor.py`

PDF ingestion with OCR fallback:

```python
class PDFProcessor:
    """
    Extract text from PDFs with OCR fallback for scanned documents.

    Pipeline:
    1. Try PyMuPDF text extraction
    2. If text density < threshold, run Tesseract OCR
    3. Clean and normalize text
    4. Chunk into segments
    """

    def process(self, pdf_path: Path) -> List[TextChunk]:
        """Process PDF and return chunks."""

    def _extract_native(self, pdf_path: Path) -> str:
        """PyMuPDF text extraction."""

    def _extract_ocr(self, pdf_path: Path) -> str:
        """Tesseract OCR for scanned pages."""

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[TextChunk]:
        """Split into overlapping chunks."""
```

Dependencies:
- `PyMuPDF` (fitz) - native PDF text
- `pytesseract` + Tesseract binary - OCR
- `pdf2image` - convert pages to images for OCR

### 2. `backend/core/embedding_service.py`

Multi-provider embedding service:

```python
class EmbeddingService:
    """
    Unified embedding interface supporting multiple providers.

    Providers:
    - OpenAI: text-embedding-3-small
    - Gemini: text-embedding-004
    - Local: sentence-transformers
    """

    def __init__(self, provider: str = "auto", llm_model: str = None):
        """Initialize with provider or auto-detect from LLM."""

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Batch embed texts, returns (n, dim) array."""

    def embed_query(self, query: str) -> np.ndarray:
        """Embed single query for search."""

    @property
    def dimension(self) -> int:
        """Embedding dimension for FAISS index."""
```

### 3. `backend/core/session_vector_store.py`

Per-session FAISS index management:

```python
class SessionVectorStore:
    """
    Manages per-session FAISS indexes for user documents.

    Storage: data/sessions/{session_id}/vectors/
    - index.faiss - FAISS index
    - metadata.json - chunk metadata (source, page, text preview)
    """

    def __init__(self, session_id: str, embedding_service: EmbeddingService):
        """Initialize or load existing index."""

    def add_document(self, doc_id: str, chunks: List[TextChunk]) -> int:
        """Add document chunks to index, returns chunk count."""

    def remove_document(self, doc_id: str) -> bool:
        """Remove document from index."""

    def search(self, query: str, k: int = 5, min_score: float = 0.3) -> List[SearchResult]:
        """Semantic search with relevance filtering."""

    def save(self):
        """Persist index to disk."""

    def load(self):
        """Load index from disk."""
```

### 4. `backend/routers/sources.py`

REST API for source management:

```python
router = APIRouter(prefix="/api/sources", tags=["sources"])

@router.post("/{session_id}/upload")
async def upload_pdf(session_id: str, file: UploadFile, user: User):
    """
    Upload PDF to session.

    1. Save to data/sessions/{session_id}/documents/
    2. Process with PDFProcessor
    3. Embed chunks
    4. Add to session vector store
    5. Register in session sources list
    """

@router.get("/{session_id}")
async def list_sources(session_id: str, user: User):
    """List all sources (PDFs, SEC, news) for session."""

@router.delete("/{session_id}/{source_id}")
async def delete_source(session_id: str, source_id: str, user: User):
    """Remove source and its embeddings."""

@router.post("/{session_id}/query")
async def query_sources(session_id: str, query: str, source_types: List[str], user: User):
    """Explicit source query - search specific source types."""
```

---

## Files to Modify

### 1. `backend/core/rag_engine.py`

Extend to unified retrieval:

```python
class RAGEngine:
    def retrieve_context(self, query, ticker, session_id, ...):
        """
        Unified retrieval across all sources.

        1. Get relevant beliefs from BeliefGraph
        2. Search user PDFs (session vector store)
        3. Search SEC filings (existing)
        4. Search news if needed (existing)
        5. Merge and rank by priority + relevance
        6. Fit to context budget
        """
```

### 2. `backend/core/settings_db.py`

Add embedding model setting:

```python
# In UserSettings dataclass
embedding_model: str = "auto"  # 'auto', 'openai', 'gemini', 'local'

# In SCHEMA
embedding_model TEXT DEFAULT 'auto',
```

### 3. `frontend/src/components/AnalysisView.jsx`

Add upload UI to Sources tab:

```jsx
// In Sources tab section (around line 642)
<div className="mb-6 flex justify-between items-center">
  <div>
    <h3>Sources</h3>
    <p>Data sources used in this analysis...</p>
  </div>
  <label className="cursor-pointer px-4 py-2 bg-amber-500 text-white rounded-lg">
    <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
    Upload PDF
  </label>
</div>

// Add PDF sources to the list with special icon
{source.source_type === 'pdf' && (
  <span className="bg-purple-100 text-purple-600">PDF</span>
)}
```

### 4. `backend/main.py`

Register sources router:

```python
from backend.routers import sources
app.include_router(sources.router)
```

### 5. `backend/core/session.py`

Add document tracking to session:

```python
@dataclass
class AnalysisSession:
    # ... existing fields
    documents: List[DocumentMetadata] = field(default_factory=list)

@dataclass
class DocumentMetadata:
    doc_id: str
    filename: str
    upload_time: datetime
    page_count: int
    chunk_count: int
    source_type: str = "pdf"
```

---

## Context Window Management

When building context for LLM calls:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Context Budget: ~120K tokens                  │
├─────────────────────────────────────────────────────────────────┤
│ System prompt + master prompt              ~2K tokens           │
│ User beliefs (all relevant)                ~1-3K tokens         │
│ User PDF chunks (top 5-10)                 ~3-5K tokens         │
│ SEC filing chunks (top 3-5)                ~2-3K tokens         │
│ News snippets (if needed)                  ~1-2K tokens         │
│ Recent conversation (last 10 msgs)         ~5-10K tokens        │
│ ─────────────────────────────────────────────────────────────── │
│ Available for response                     ~95-100K tokens      │
└─────────────────────────────────────────────────────────────────┘
```

Smart truncation rules:
1. Beliefs: Never truncate, always include all relevant
2. User PDFs: Include top chunks by relevance score
3. SEC: Include if relevance > 0.3
4. News: Include only if query explicitly needs current info
5. Conversation: Keep last 10, summarize older

---

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    # ... existing
    "PyMuPDF>=1.24.0",          # PDF text extraction
    "pytesseract>=0.3.10",       # OCR wrapper
    "pdf2image>=1.17.0",         # PDF to image for OCR
    "sentence-transformers>=2.2.0",  # Local embeddings fallback
]
```

System requirements:
- Tesseract OCR binary: `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux)
- Poppler for pdf2image: `brew install poppler` (macOS)

---

## Data Storage Structure

```
data/
├── sessions/
│   └── {session_id}/
│       ├── session.json           # Existing session data
│       ├── documents/
│       │   ├── {doc_id}.pdf       # Original uploaded PDFs
│       │   └── {doc_id}.json      # Document metadata
│       └── vectors/
│           ├── index.faiss        # FAISS index
│           └── metadata.json      # Chunk-level metadata
├── embeddings/
│   └── {ticker}/                  # Existing SEC embeddings
└── cache/
    └── pdf_text/                  # Cached OCR results
```

---

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sources/{session_id}/upload` | Upload PDF |
| GET | `/api/sources/{session_id}` | List all sources |
| DELETE | `/api/sources/{session_id}/{source_id}` | Remove source |
| POST | `/api/sources/{session_id}/query` | Explicit source search |
| POST | `/api/sources/{session_id}/{source_id}/exclude` | Exclude from analysis |
| POST | `/api/sources/{session_id}/{source_id}/restore` | Restore excluded |

---

## Implementation Order

1. **Core infrastructure**
   - `pdf_processor.py` - OCR pipeline
   - `embedding_service.py` - multi-provider embeddings
   - `session_vector_store.py` - FAISS management

2. **API layer**
   - `routers/sources.py` - upload/list/delete endpoints
   - Modify `main.py` to register router

3. **Frontend**
   - Upload button in Sources tab
   - PDF source display with metadata
   - Upload progress indicator

4. **RAG integration**
   - Extend `rag_engine.py` for unified retrieval
   - Modify chat endpoint to use extended RAG
   - Priority-based context building

5. **Settings**
   - Add embedding model to settings
   - Auto-detection from LLM choice

---

## Open Questions

1. **User-level PDF library?** Should PDFs persist across sessions (reusable library) or per-session only?

2. **Max file size?** Suggest 50MB limit per PDF, configurable.

3. **Batch upload?** Allow multiple PDFs at once or one at a time?

4. **OCR quality indicator?** Show user if OCR was used and confidence level?

5. **Source citation format?** How to cite PDF sources in generated text? `[PDF: filename.pdf, p.12]`?

---

## Success Criteria

- [ ] User can upload PDFs in Sources tab
- [ ] PDFs are OCR'd if needed and chunked
- [ ] Chunks are embedded and stored per-session
- [ ] Chat queries retrieve relevant PDF chunks
- [ ] PDF sources appear in citations
- [ ] Embedding model configurable in settings
- [ ] Context budget respected across all sources
- [ ] User beliefs always have highest priority
