"""
Report RAG - Semantic search within analysis reports.

Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings and FAISS for
vector similarity search. Enables context-aware responses by retrieving
relevant report sections during chat.

Chunking Strategy:
- Sentence-aware splitting (splits on ". " to avoid mid-sentence breaks)
- Default chunk size: 500 characters
- Overlap: 100 characters (prevents losing context at chunk boundaries)
- Each chunk includes metadata: section_id, section_title, chunk_index

Chunk Metadata Schema:
    {
        'section_id': str,       # ID of source section (e.g., 'fundamentals')
        'section_title': str,    # Display title (e.g., 'Fundamental Analysis')
        'chunk_index': int,      # Position within section (0-indexed)
        'text': str,             # The actual chunk content
        'score': float           # Similarity score (only in search results)
    }

Lazy Loading:
- Embedding model loaded on first query via @property model
- First query takes ~2s to load model (22M params, ~50MB memory)
- Subsequent queries are fast (~100ms for search)
- Model: all-MiniLM-L6-v2 - good balance of speed and quality

Index Type:
- FAISS IndexFlatL2 (exact L2 distance search)
- No approximation - accurate but O(n) search
- Suitable for report-sized documents (~100-500 chunks)
"""

import logging
from typing import Dict, List
import numpy as np

logger = logging.getLogger(__name__)

# Embedding model (runs locally, no API cost)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class ReportRAG:
    """
    Semantic search over analysis report sections.

    Chunks report content and builds a FAISS index for efficient retrieval.
    Index is cached per session to avoid rebuilding on every query.
    """

    def __init__(self):
        """Initialize ReportRAG with lazy loading of model."""
        self._model = None
        self._index = None
        self._chunks = []
        self._is_built = False

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(EMBEDDING_MODEL)
                logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model

    def build_index(self, report_state) -> bool:
        """
        Build FAISS index from report sections.

        Args:
            report_state: ReportState object with sections

        Returns:
            True if index was built successfully
        """
        if not report_state or not report_state.sections:
            logger.warning("No report sections to index")
            return False

        try:
            import faiss

            self._chunks = []

            # Chunk each section
            for section_id, section in report_state.sections.items():
                if not section.content:
                    continue

                chunks = self._chunk_text(
                    text=section.content,
                    section_id=section_id,
                    section_title=section.title,
                    chunk_size=500,
                    overlap=100
                )
                self._chunks.extend(chunks)

            if not self._chunks:
                logger.warning("No chunks created from report")
                return False

            # Embed all chunks
            texts = [c['text'] for c in self._chunks]
            embeddings = self.model.encode(texts, show_progress_bar=False)
            embeddings = np.array(embeddings).astype('float32')

            # Build FAISS index
            dimension = embeddings.shape[1]
            self._index = faiss.IndexFlatL2(dimension)
            self._index.add(embeddings)

            self._is_built = True
            logger.info(f"Built report index with {len(self._chunks)} chunks")
            return True

        except Exception as e:
            logger.error(f"Failed to build report index: {e}")
            return False

    def _chunk_text(
        self,
        text: str,
        section_id: str,
        section_title: str,
        chunk_size: int = 500,
        overlap: int = 100
    ) -> List[Dict]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk
            section_id: Section identifier
            section_title: Section title for context
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of chunk dicts with text and metadata
        """
        chunks = []

        # Clean the text
        text = text.strip()
        if not text:
            return chunks

        # Split into sentences first for cleaner boundaries
        sentences = text.replace('\n', ' ').split('. ')
        sentences = [s.strip() + '.' for s in sentences if s.strip()]

        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            # If adding this sentence would exceed chunk_size
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append({
                    'section_id': section_id,
                    'section_title': section_title,
                    'chunk_index': chunk_index,
                    'text': current_chunk.strip()
                })
                chunk_index += 1

                # Keep last 'overlap' chars for context
                if len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + " " + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                'section_id': section_id,
                'section_title': section_title,
                'chunk_index': chunk_index,
                'text': current_chunk.strip()
            })

        return chunks

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for most relevant chunks.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of chunk dicts with text and metadata
        """
        if not self._is_built or not self._index:
            logger.warning("Index not built, cannot search")
            return []

        try:
            # Embed the query
            query_embedding = self.model.encode([query], show_progress_bar=False)
            query_embedding = np.array(query_embedding).astype('float32')

            # Search
            distances, indices = self._index.search(query_embedding, min(k, len(self._chunks)))

            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx < len(self._chunks):
                    chunk = self._chunks[idx].copy()
                    chunk['score'] = float(distances[0][i])
                    results.append(chunk)

            logger.info(f"Report RAG search returned {len(results)} results for: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Report RAG search failed: {e}")
            return []

    def format_results_for_llm(self, results: List[Dict], max_chars: int = 2000) -> str:
        """
        Format search results for inclusion in LLM context.

        Args:
            results: List of chunk dicts from search()
            max_chars: Maximum characters to include

        Returns:
            Formatted string for LLM context
        """
        if not results:
            return ""

        formatted_parts = ["## Relevant sections from analysis report:\n"]
        total_chars = 0

        for chunk in results:
            section_header = f"**[{chunk['section_title']}]**"
            text = chunk['text']

            # Check if we'd exceed the limit
            entry = f"{section_header}\n{text}\n\n"
            if total_chars + len(entry) > max_chars:
                # Add truncated version
                remaining = max_chars - total_chars - len(section_header) - 10
                if remaining > 50:
                    formatted_parts.append(f"{section_header}\n{text[:remaining]}...\n")
                break

            formatted_parts.append(entry)
            total_chars += len(entry)

        return "".join(formatted_parts)

    @property
    def is_ready(self) -> bool:
        """Check if index is built and ready for search."""
        return self._is_built and self._index is not None

    @property
    def chunk_count(self) -> int:
        """Return number of indexed chunks."""
        return len(self._chunks)
