"""
RAG Pipeline for Dehumidifier Assistant
Handles document indexing and retrieval using LangChain and FAISS
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    from langchain.schema import Document

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    from langchain.schema import Document
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"Warning: RAG dependencies not installed: {e}")
    print("Install with: pip install langchain langchain-community langchain-openai faiss-cpu pymupdf")
    # Provide fallback types to prevent NameError
    Document = Any
    RecursiveCharacterTextSplitter = Any
    TextLoader = Any
    PyMuPDFLoader = Any
    FAISS = Any
    OpenAIEmbeddings = Any
    RAG_AVAILABLE = False

from config import config

logger = logging.getLogger(__name__)

class RAGPipeline:
    """RAG Pipeline for document indexing and retrieval"""
    
    def __init__(self):
        self.docs_dir = Path(__file__).parent / "product_docs"
        self.index_dir = Path(__file__).parent / "faiss_index"
        self.embeddings = None
        self.vectorstore = None
        
        # Initialize embeddings if RAG is enabled and OpenAI key is available
        if config.RAG_ENABLED and config.OPENAI_API_KEY:
            try:
                self.embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-large",
                    openai_api_key=config.OPENAI_API_KEY
                )
                print("RAG Pipeline: OpenAI embeddings initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI embeddings: {e}")
                self.embeddings = None
    
    def load_documents(self) -> List[Document]:
        """Load all documents from the product_docs directory"""
        if not RAG_AVAILABLE:
            logger.warning("RAG dependencies not available, cannot load documents")
            return []
            
        documents = []
        
        if not self.docs_dir.exists():
            logger.warning(f"Product docs directory not found: {self.docs_dir}")
            return documents
        
        print(f"RAG Pipeline: Loading documents from {self.docs_dir}")
        
        for file_path in self.docs_dir.iterdir():
            if file_path.is_file():
                try:
                    if file_path.suffix.lower() == '.txt':
                        loader = TextLoader(str(file_path), encoding='utf-8')
                        docs = loader.load()
                        print(f"RAG Pipeline: Loaded {len(docs)} document(s) from {file_path.name}")
                        
                    elif file_path.suffix.lower() == '.pdf':
                        loader = PyMuPDFLoader(str(file_path))
                        docs = loader.load()
                        print(f"RAG Pipeline: Loaded {len(docs)} page(s) from {file_path.name}")
                        
                    else:
                        print(f"RAG Pipeline: Skipping unsupported file type: {file_path.name}")
                        continue
                    
                    # Add source metadata
                    for doc in docs:
                        doc.metadata['source'] = file_path.name
                        doc.metadata['file_type'] = file_path.suffix.lower()
                    
                    documents.extend(docs)
                    
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
                    continue
        
        print(f"RAG Pipeline: Total documents loaded: {len(documents)}")
        return documents
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks using RecursiveCharacterTextSplitter"""
        if not RAG_AVAILABLE:
            logger.warning("RAG dependencies not available, cannot chunk documents")
            return []
            
        if not documents:
            return []
        
        print(f"RAG Pipeline: Chunking {len(documents)} documents")
        
        # Configure text splitter with separators for structured content
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.RAG_CHUNK_SIZE,
            chunk_overlap=config.RAG_CHUNK_OVERLAP,
            separators=[
                "\n\n",  # Paragraphs
                "\n",    # Lines
                ". ",    # Sentences
                ", ",    # Clauses
                " ",     # Words
                ""       # Characters
            ],
            length_function=len,
        )
        
        chunks = text_splitter.split_documents(documents)
        print(f"RAG Pipeline: Created {len(chunks)} chunks")
        
        return chunks
    
    def build_index(self) -> bool:
        """Build and save FAISS index from documents"""
        if not RAG_AVAILABLE:
            logger.warning("RAG dependencies not available, cannot build index")
            return False
            
        if not self.embeddings:
            logger.error("Cannot build index: embeddings not initialized")
            return False
        
        try:
            # Load and chunk documents
            documents = self.load_documents()
            if not documents:
                logger.warning("No documents found to index")
                return False
            
            chunks = self.chunk_documents(documents)
            if not chunks:
                logger.warning("No chunks created from documents")
                return False
            
            print(f"RAG Pipeline: Building FAISS index with {len(chunks)} chunks")
            
            # Create FAISS vectorstore
            vectorstore = FAISS.from_documents(chunks, self.embeddings)
            
            # Create index directory if it doesn't exist
            self.index_dir.mkdir(exist_ok=True)
            
            # Save the index
            vectorstore.save_local(str(self.index_dir))
            
            print(f"RAG Pipeline: Index saved to {self.index_dir}")
            print(f"RAG Pipeline: Index contains {vectorstore.index.ntotal} vectors")
            
            return True
            
        except Exception as e:
            logger.error(f"Error building index: {e}")
            return False
    
    def load_vectorstore(self) -> Optional[FAISS]:
        """Load existing FAISS vectorstore"""
        if not RAG_AVAILABLE:
            logger.warning("RAG dependencies not available, cannot load vectorstore")
            return None
            
        if not config.RAG_ENABLED:
            logger.info("RAG is disabled in configuration")
            return None
            
        if not self.embeddings:
            logger.error("Cannot load vectorstore: embeddings not initialized")
            return None
        
        try:
            if not self.index_dir.exists():
                logger.warning(f"Index directory not found: {self.index_dir}")
                print("RAG Pipeline: Building new index...")
                if self.build_index():
                    print("RAG Pipeline: Index built successfully")
                else:
                    logger.error("Failed to build index")
                    return None
            
            # Load the vectorstore
            vectorstore = FAISS.load_local(
                str(self.index_dir), 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            
            print(f"RAG Pipeline: Loaded vectorstore with {vectorstore.index.ntotal} vectors")
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error loading vectorstore: {e}")
            logger.info("Attempting to rebuild index...")
            
            # Try to rebuild the index
            if self.build_index():
                try:
                    vectorstore = FAISS.load_local(
                        str(self.index_dir), 
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                    print("RAG Pipeline: Successfully rebuilt and loaded vectorstore")
                    return vectorstore
                except Exception as rebuild_error:
                    logger.error(f"Failed to load rebuilt index: {rebuild_error}")
            
            return None


# Global instance and convenience function
_rag_pipeline = None

def get_rag_pipeline() -> RAGPipeline:
    """Get or create RAG pipeline instance"""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline

def load_vectorstore() -> Optional[FAISS]:
    """Convenience function to load vectorstore"""
    pipeline = get_rag_pipeline()
    return pipeline.load_vectorstore()

def build_index() -> bool:
    """Convenience function to build index"""
    pipeline = get_rag_pipeline()
    return pipeline.build_index()


if __name__ == "__main__":
    # Script to build index from command line
    print("Building RAG index...")
    pipeline = RAGPipeline()
    
    if pipeline.build_index():
        print("✅ Index built successfully!")
    else:
        print("❌ Failed to build index")