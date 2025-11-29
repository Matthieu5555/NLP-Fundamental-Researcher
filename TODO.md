# George Financial Analyst - TODO List

**Last Updated**: 2025-11-29
**Priority**: High

---

## Critical Tasks

### 1. Remake Analysis Agents
**Priority**: HIGH
**Status**: Pending
**Estimated Time**: 2-3 days

**Problem**:
Current agents are not producing quality output. The prompts need to be rewritten for better analysis quality.

**Specific Issues**:
- Further Research section uses basic keyword matching (not intelligent)
- Need to review quality of all 7 agent outputs
- Prompts may be too generic or not well-structured
- Contradiction detection is overly simplistic

**Agents to Remake** (in priority order):
1. **Further Research Agent** (CRITICAL - currently just keyword matching)
   - File: `backend/core/contradiction_detector.py`
   - Current: 6 hardcoded keyword rules
   - Needed: LLM-based semantic contradiction detection

2. **Fundamentals Agent**
   - File: `src_george_researcher/prompts/__init__.py`
   - Review prompt quality
   - Ensure comprehensive ratio analysis

3. **Technical Agent**
   - Check if technical analysis is detailed enough
   - Verify chart pattern recognition

4. **Bull Case Agent**
   - Ensure compelling, data-driven arguments
   - Check for specific catalysts

5. **Bear Case Agent**
   - Ensure realistic risk assessment
   - Balance with bull case

6. **Moat Analysis Agent**
   - Verify Warren Buffett framework is properly applied
   - Check for competitive advantage depth

7. **SWOT Agent**
   - Ensure comprehensive coverage
   - Verify actionable insights

**Files to Modify**:
- `src_george_researcher/prompts/__init__.py` - All agent prompts
- `src_george_researcher/analysis.py` - Agent execution logic
- `backend/core/contradiction_detector.py` - Replace with LLM-based detection

**Acceptance Criteria**:
- All agent outputs are comprehensive and actionable
- Further Research uses LLM to detect semantic contradictions
- Each analysis section is 300-500 words minimum
- Sources properly cited
- No generic/template responses

---

### 2. Verify PDF Report Updates from Chat
**Priority**: HIGH
**Status**: Pending
**Estimated Time**: 2-3 hours

**Problem**:
Need to verify that when users chat and ask analytical questions, the PDF report dynamically includes those new insights.

**What to Test**:
1. Start fresh analysis for ticker (e.g., AAPL)
2. Download PDF (save as baseline)
3. Ask analytical questions in chat:
   - "What is the return on equity?"
   - "How does debt compare to competitors?"
   - "What are the main growth drivers?"
4. Download PDF again (save as updated)
5. Compare PDFs - verify chat Q&A appears in report

**Expected Behavior**:
- Chat response triggers `update_report_from_conversation()`
- Relevant sections get appended with Q&A
- PDF export includes all updates
- New sections created if needed (e.g., "Additional Insights")

**Files to Review**:
- `backend/core/belief_extraction.py` - Report update logic
- `backend/api/chat.py` - Where update is triggered (line 124-128)
- `backend/core/report_builder.py` - Section update methods

**Acceptance Criteria**:
- Chat insights appear in downloaded PDF
- Updates are in appropriate sections
- No duplicate content
- Sources tracked properly

**Debug Steps if Broken**:
1. Check logs for "Report updated from conversation"
2. Verify `update_report_from_conversation()` is being called
3. Check keyword matching in belief_extraction.py
4. Verify session.report_state is persisting

---

## Medium Priority Tasks

### 3. Improve Context Window Management
**Status**: Working but can be enhanced
**Time**: 1-2 days

**Current**: Word count × 1.3 heuristic
**Enhancement**: Add real token counting with tiktoken

**Steps**:
1. Add tiktoken to dependencies
2. Replace `estimate_tokens()` in ContextManager
3. Test with actual token counts
4. Compare accuracy vs word count method

### 4. Add Charts to PDF Reports
**Status**: Not implemented
**Time**: 2-3 days

**Requirements**:
- Price charts (6 months, 1 year)
- Financial ratio trends
- Comparison to competitors
- Embed in PDF using matplotlib

**Files to Modify**:
- `backend/core/pdf_generator.py` - Add chart rendering
- Create `backend/core/chart_generator.py` - Chart creation logic

### 5. LLM-Based Section Routing
**Status**: Currently keyword-based
**Time**: 1 day

**Current**: Simple keyword matching in `belief_extraction.py`
**Enhancement**: Use LLM to decide which section to update

**Benefits**:
- More accurate routing
- Handle edge cases
- Better context understanding

---

## Low Priority / Future Enhancements

### 6. PostgreSQL Migration
**Status**: Currently using JSON files
**Time**: 1 week

Replace JSON file storage with PostgreSQL for production scalability.

### 7. Redis Caching
**Status**: Not implemented
**Time**: 3-4 days

Add Redis for session caching and rate limiting.

### 8. Conversation Memory RAG
**Status**: Not implemented
**Time**: 1 week

Add semantic search of past conversation turns using embeddings.

### 9. Advanced Belief Graph
**Status**: Basic implementation
**Time**: 1 week

Add semantic contradiction detection, confidence scoring, and belief merging.

### 10. Multi-User Support
**Status**: Single user only
**Time**: 2 weeks

Add authentication, user management, and session ownership.

---

## Bug Fixes / Technical Debt

### Known Issues

1. **Frontend Rendering**:
   - Some Tailwind v4 + ReactMarkdown compatibility issues
   - May need to revert to Tailwind v3 or replace markdown renderer

2. **Error Handling**:
   - Need more comprehensive error messages
   - Add retry logic for API failures

3. **Loading States**:
   - Add skeleton loaders for better UX
   - Progress indicators for long operations

---

## Testing Checklist

Before considering feature complete:

- [ ] Test PDF download with real analysis
- [ ] Verify chat updates appear in PDF
- [ ] Test session resume with 20+ messages
- [ ] Test RAG search triggering
- [ ] Test all 7 agent outputs for quality
- [ ] Test contradiction detection accuracy
- [ ] Load test with 5+ concurrent sessions
- [ ] Test on mobile devices

---

## Quick Reference

**Start App**:
```bash
# Terminal 1
PORT=5001 uv run python backend/app.py

# Terminal 2
cd frontend && npm run dev
```

**Test Endpoints**:
```bash
# Create session
curl -X POST http://localhost:5001/api/analysis/start -H "Content-Type: application/json" -d '{"ticker":"AAPL"}'

# Download PDF
curl -X POST http://localhost:5001/api/reports/{session_id}/export/pdf -o test.pdf
```

**Key Files**:
- Agents: `src_george_researcher/prompts/__init__.py`
- Further Research: `backend/core/contradiction_detector.py`
- Report Updates: `backend/core/belief_extraction.py`
- PDF Generation: `backend/core/pdf_generator.py`

---

**Next Session**: Focus on tasks 1 and 2 above for immediate quality improvements.
