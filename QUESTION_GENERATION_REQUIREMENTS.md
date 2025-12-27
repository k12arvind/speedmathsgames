# Question Generation from Chunked PDFs - Requirements

## Overview
Generate flashcard questions from chunked PDFs while maintaining topic context and avoiding duplicates from overlapping pages.

## Context Preservation Strategy

### Chunking Strategy (Already Implemented)
- **Overlap Mode**: Last page of each chunk (except final) becomes first page of next chunk
- **Purpose**: Ensures topics split across chunks maintain context
- **Example**:
  - Chunk 1: Pages 1-10
  - Chunk 2: Pages 10-19 (page 10 is repeated)
  - Chunk 3: Pages 19-28 (page 19 is repeated)

### Question Generation Rules

#### 1. Complete Topic Coverage
- **Rule**: Only generate questions for topics that are COMPLETE within the chunk
- **Implementation**:
  - If a topic starts on the overlapped page (first page of non-initial chunks), check if it was already covered in previous chunk
  - If topic is incomplete (continues beyond last page), skip question generation for that topic

#### 2. Duplicate Detection
- **Problem**: Overlapped pages may cause duplicate questions
- **Solution**:
  ```python
  # Pseudocode
  if chunk_number > 1:
      # First page is overlap - check what topics were already covered
      overlapped_topics = get_topics_from_page(first_page)
      previously_covered = get_questions_from_previous_chunk(overlapped_topics)

      # Skip questions for topics already covered
      skip_topics = set(previously_covered)
  ```

#### 3. Context Window
- **Full Context**: Use entire chunk for context when generating questions
- **Question Scope**: Only generate questions for complete topics (excluding split topics on overlap page)
- **Example**:
  ```
  Chunk 2 (Pages 10-19):
  - Page 10 (overlap): Topic A (continued from chunk 1) - SKIP
  - Page 11-18: Topic B, C, D - GENERATE QUESTIONS
  - Page 19: Topic E (incomplete, continues to page 20) - SKIP
  ```

## Implementation Checklist

### Phase 1: Topic Boundary Detection
- [ ] Add topic boundary detection to PDF parser
- [ ] Identify when topic starts on page
- [ ] Identify when topic ends on page
- [ ] Store topic metadata (start_page, end_page, is_complete)

### Phase 2: Chunk Processing Logic
- [ ] Add `process_chunk_for_questions()` function
- [ ] Implement overlap awareness:
  ```python
  def process_chunk_for_questions(chunk_info, is_first_chunk, previous_topics):
      if not is_first_chunk:
          # Skip topics from overlapped first page if already covered
          first_page_topics = extract_topics_from_page(chunk_info['start_page'])
          topics_to_skip = first_page_topics.intersection(previous_topics)

      # Identify complete topics (not split across boundaries)
      complete_topics = get_complete_topics(chunk_info)

      # Generate questions only for complete, non-duplicate topics
      questions = generate_questions(complete_topics, full_chunk_context)

      return questions, processed_topics
  ```

### Phase 3: Database Schema Updates
- [ ] Add `topic_boundaries` table:
  ```sql
  CREATE TABLE topic_boundaries (
      topic_id INTEGER PRIMARY KEY,
      pdf_id TEXT NOT NULL,
      topic_title TEXT NOT NULL,
      start_page INTEGER NOT NULL,
      end_page INTEGER NOT NULL,
      is_complete BOOLEAN NOT NULL,
      chunk_number INTEGER,
      processed_for_questions BOOLEAN DEFAULT 0,
      FOREIGN KEY (pdf_id) REFERENCES pdfs(filename)
  );
  ```

### Phase 4: Question Generation Pipeline
- [ ] Integrate with existing `generate_flashcards.py`
- [ ] Add `--chunked-mode` flag to handle overlap logic
- [ ] Pass metadata about:
  - Is this first chunk?
  - Which topics were covered in previous chunks?
  - Which page is the overlap page?

### Phase 5: Validation & Testing
- [ ] Test with sample chunked PDF
- [ ] Verify no duplicate questions across chunks
- [ ] Verify topic context is maintained
- [ ] Verify split topics are handled correctly

## Example Workflow

```bash
# Step 1: Chunk large PDF with overlap
python pdf_chunker.py input.pdf /tmp/chunks --max-pages 10 --overlap

# Step 2: Process each chunk for questions
for chunk in /tmp/chunks/*.pdf:
    python generate_flashcards.py $chunk \
        --chunked-mode \
        --chunk-metadata chunk_metadata.json \
        --previous-topics previous_topics.json \
        --output questions_$chunk.json
done

# Step 3: Merge questions (removing duplicates)
python merge_questions.py /tmp/chunks/questions_*.json --output final_questions.json

# Step 4: Import to Anki
python import_to_anki.py final_questions.json
```

## Key Benefits

1. **No Context Loss**: Topics split across pages maintain full context
2. **No Duplicates**: Overlap pages don't generate duplicate questions
3. **Complete Coverage**: All complete topics are covered
4. **Smart Skip**: Incomplete topics at boundaries are skipped (can be picked up by next chunk)

## Technical Considerations

### Topic Detection Methods
1. **Header-based**: Look for topic headers (larger font, bold, numbered)
2. **Semantic**: Use NLP to detect topic changes
3. **Manual markers**: Look for explicit topic markers in PDF

### Edge Cases
- Topic spans entire chunk → Process normally
- Multiple topics on overlap page → Skip all topics from overlap page
- Single topic across multiple chunks → Will be caught in validation phase

## Success Metrics
- Zero duplicate questions across chunks
- 100% complete topic coverage (no partial topics)
- Context preserved in all generated questions
- Processing time < 2 minutes per chunk

## Future Enhancements
- [ ] Visual indicator in dashboard showing overlap pages
- [ ] Manual topic boundary adjustment UI
- [ ] Topic completion confidence score
- [ ] Automatic topic merging across chunks

---

**Status**: Requirements documented
**Next Phase**: Implement topic boundary detection
**Dependencies**: Chunked PDFs with overlap (✓ Completed)
