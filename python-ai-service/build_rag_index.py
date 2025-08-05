#!/usr/bin/env python3
"""
Script to build RAG index for dehumidifier assistant
Run this script to create or rebuild the FAISS index from product documentation
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def main():
    print("🔍 Building RAG Index for Dehumidifier Assistant")
    print("=" * 50)
    
    try:
        # Check if dependencies are available
        from rag_pipeline import build_index, get_rag_pipeline
        from config import config
        
        # Verify configuration
        if not config.RAG_ENABLED:
            print("❌ RAG is disabled in configuration")
            print("Set RAG_ENABLED=True in your environment or .env file")
            return False
        
        if not config.OPENAI_API_KEY:
            print("❌ OpenAI API key not found")
            print("Set OPENAI_API_KEY in your environment or .env file")
            return False
        
        # Check if product docs exist
        pipeline = get_rag_pipeline()
        if not pipeline.docs_dir.exists():
            print(f"❌ Product docs directory not found: {pipeline.docs_dir}")
            return False
        
        # List available documents
        doc_files = list(pipeline.docs_dir.glob("*"))
        doc_files = [f for f in doc_files if f.is_file() and f.suffix.lower() in ['.txt', '.pdf']]
        
        if not doc_files:
            print(f"❌ No documents found in {pipeline.docs_dir}")
            print("Supported formats: .txt, .pdf")
            return False
        
        print(f"📄 Found {len(doc_files)} document(s):")
        for doc_file in doc_files:
            print(f"   - {doc_file.name}")
        
        print("\n🔨 Building index...")
        
        # Build the index
        success = build_index()
        
        if success:
            print("✅ RAG index built successfully!")
            
            # Test the index
            print("\n🧪 Testing index...")
            vectorstore = pipeline.load_vectorstore()
            if vectorstore:
                print(f"✅ Index loaded with {vectorstore.index.ntotal} vectors")
                
                # Test search
                test_query = "installation requirements"
                results = vectorstore.similarity_search(test_query, k=2)
                if results:
                    print(f"✅ Search test successful - found {len(results)} results for '{test_query}'")
                    print("\nSample result:")
                    print(f"   {results[0].page_content[:100]}...")
                else:
                    print("⚠️  Search test returned no results")
            else:
                print("❌ Failed to load built index")
                return False
            
            print("\n🎉 RAG setup complete!")
            print("\nNext steps:")
            print("1. Start your FastAPI service: python main.py")
            print("2. Ask installation questions like: 'How do I install the SP500C?'")
            print("3. The assistant will use RAG to provide accurate manual-based answers")
            
            return True
            
        else:
            print("❌ Failed to build RAG index")
            return False
            
    except ImportError as e:
        print("❌ RAG dependencies not installed")
        print(f"Error: {e}")
        print("\nInstall dependencies with:")
        print("pip install langchain langchain-community faiss-cpu pymupdf")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)