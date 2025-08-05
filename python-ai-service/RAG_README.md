# RAG (Retrieval-Augmented Generation) Integration

This document explains how to use the RAG functionality in the Dehumidifier Assistant to provide accurate, manual-based responses to technical queries.

## Overview

The RAG system enhances the AI assistant by:
- **Indexing product manuals and brochures** using FAISS vector search
- **Retrieving relevant sections** when users ask technical questions
- **Augmenting AI prompts** with precise manual excerpts
- **Providing accurate, source-backed answers** instead of potentially hallucinated responses

## Quick Start

### 1. Install Dependencies

```bash
cd python-ai-service
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (copy from `env.example`) and set:

```bash
OPENAI_API_KEY=your-openai-key-here
RAG_ENABLED=True
```

### 3. Add Product Documents

Place your product manuals in the `product_docs/` folder:
- Supported formats: `.txt`, `.pdf`
- Example: `SP500C_PRO_manual.txt`, `SP600_brochure.pdf`

### 4. Build RAG Index

```bash
python build_rag_index.py
```

This will:
- Load all documents from `product_docs/`
- Split them into semantic chunks
- Create embeddings using OpenAI's `text-embedding-ada-002`
- Build and save a FAISS index to `faiss_index/`

### 5. Start the Service

```bash
python main.py
```

## How RAG Works

### Document Processing
1. **Loading**: Text files via `TextLoader`, PDFs via `PyMuPDFLoader`
2. **Chunking**: `RecursiveCharacterTextSplitter` with structure-aware separators
3. **Embedding**: OpenAI embeddings convert chunks to vectors
4. **Indexing**: FAISS creates a searchable vector database

### Query Processing
1. **Detection**: System identifies when users ask technical questions (keywords: "install", "troubleshoot", "manual", etc.)
2. **Retrieval**: Query is embedded and matched against document chunks
3. **Augmentation**: Top-K relevant chunks are added to the AI prompt
4. **Generation**: AI responds using manual excerpts as authoritative sources

### Example Flow

**User Query**: "How do I install the SP500C dehumidifier?"

**RAG Process**:
1. Detects "install" keyword → triggers RAG
2. Searches index for installation-related content
3. Retrieves relevant manual sections:
   ```
   [Source: SP500C_PRO_manual.txt]
   1. MOUNTING REQUIREMENTS
   - Wall must support minimum 45kg
   - Minimum 500mm clearance from ceiling
   - Electrical supply: 240V 15A
   ```
4. AI generates response using these excerpts

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_ENABLED` | `True` | Enable/disable RAG functionality |
| `RAG_CHUNK_SIZE` | `500` | Size of document chunks (characters) |
| `RAG_CHUNK_OVERLAP` | `50` | Overlap between chunks (characters) |
| `RAG_TOP_K` | `3` | Number of relevant chunks to retrieve |

### Customizing Retrieval

Edit `ai_agent.py` → `_needs_manual_retrieval()` to modify trigger keywords:

```python
manual_keywords = [
    'manual', 'install', 'troubleshoot', 'error',
    'maintenance', 'clean', 'filter', 'warranty',
    # Add your keywords here
]
```

## File Structure

```
python-ai-service/
├── rag_pipeline.py          # Core RAG implementation
├── tools.py                 # RAG integration in tools
├── ai_agent.py             # RAG integration in agent
├── build_rag_index.py      # Index building script
├── test_rag.py             # RAG unit tests
├── product_docs/           # Document storage
│   ├── SP500C_PRO_manual.txt
│   └── SP500C_PRO_brochure.txt
└── faiss_index/            # Generated index (auto-created)
    ├── index.faiss
    └── index.pkl
```

## API Integration

### Tools Class Methods

```python
# In tools.py
tools = DehumidifierTools()

# Retrieve relevant chunks
chunks = tools.retrieve_relevant_docs("installation guide", k=3)
# Returns: ["[Source: manual.txt]\nInstallation steps...", ...]
```

### Agent Integration

RAG is automatically integrated into message preparation:
- `_prepare_messages()` - for regular chat
- `_prepare_messages_streaming()` - for streaming chat

When technical keywords are detected, relevant manual chunks are automatically added as system messages.

## Testing

### Run Unit Tests

```bash
python test_rag.py
```

### Manual Testing

1. Build index: `python build_rag_index.py`
2. Start service: `python main.py`
3. Test queries:
   - "How do I install the SP500C?"
   - "What should I do if the unit won't start?"
   - "How do I clean the filter?"

## Troubleshooting

### Index Building Issues

**Problem**: "No documents found"
```bash
❌ No documents found in /path/to/product_docs
```
**Solution**: Add `.txt` or `.pdf` files to `product_docs/` folder

**Problem**: "OpenAI API key not found"
```bash
❌ OpenAI API key not found
```
**Solution**: Set `OPENAI_API_KEY` in your `.env` file

### Runtime Issues

**Problem**: RAG not triggering
- Check `RAG_ENABLED=True` in config
- Verify trigger keywords in your query
- Check logs for RAG chunk addition messages

**Problem**: Poor retrieval results
- Adjust `RAG_CHUNK_SIZE` (try 300-800)
- Increase `RAG_TOP_K` (try 5-7)
- Improve document formatting/structure

### Performance Optimization

**Large Document Collections**:
- Use `faiss-gpu` instead of `faiss-cpu` for faster search
- Increase chunk size to reduce total vectors
- Consider document filtering by product/category

**Cost Optimization**:
- Reduce `RAG_TOP_K` to minimize tokens
- Use smaller embedding models (if available)
- Cache frequently-retrieved chunks

## Advanced Usage

### Custom Document Loaders

Add support for new formats in `rag_pipeline.py`:

```python
elif file_path.suffix.lower() == '.docx':
    from langchain_community.document_loaders import Docx2txtLoader
    loader = Docx2txtLoader(str(file_path))
    docs = loader.load()
```

### Metadata Filtering

Filter retrievals by product or category:

```python
# In tools.py → retrieve_relevant_docs()
docs = self.vectorstore.similarity_search(
    query, 
    k=k,
    filter={"source": "SP500C_PRO_manual.txt"}
)
```

### Hybrid Search

Combine vector search with keyword matching:

```python
# Add BM25 or keyword search alongside vector search
from rank_bm25 import BM25Okapi
# Combine results from both approaches
```

## Integration with Existing System

RAG integrates seamlessly with the existing system:
- **No breaking changes** to existing tools or APIs
- **Graceful fallback** when RAG is disabled or fails
- **Optional enhancement** that improves responses when available
- **Preserves existing functionality** like sizing calculations

The system automatically detects when manual information would be helpful and enhances responses accordingly, making the assistant more accurate and trustworthy for technical queries.