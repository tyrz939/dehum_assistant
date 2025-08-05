"""
Unit tests for RAG pipeline integration
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Test if RAG dependencies are available
try:
    from rag_pipeline import RAGPipeline, build_index, load_vectorstore
    from tools import DehumidifierTools
    from langchain.schema import Document
    RAG_TESTS_ENABLED = True
except ImportError as e:
    RAG_TESTS_ENABLED = False
    print(f"Warning: RAG dependencies not available: {e}")
    print("Install with: pip install langchain langchain-community faiss-cpu pymupdf")
    
    # Create dummy classes for testing
    class Document:
        def __init__(self, page_content="", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}


@unittest.skipUnless(RAG_TESTS_ENABLED, "RAG dependencies not available")
class TestRAGPipeline(unittest.TestCase):
    """Test RAG pipeline functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directories for testing
        self.test_dir = tempfile.mkdtemp()
        self.docs_dir = Path(self.test_dir) / "product_docs"
        self.index_dir = Path(self.test_dir) / "faiss_index"
        
        # Create test directories
        self.docs_dir.mkdir(exist_ok=True)
        
        # Create test documents
        self.create_test_documents()
        
        # Mock config to point to test directories
        self.config_patcher = patch('rag_pipeline.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.RAG_ENABLED = True
        self.mock_config.RAG_CHUNK_SIZE = 200
        self.mock_config.RAG_CHUNK_OVERLAP = 20
        self.mock_config.RAG_TOP_K = 3
        self.mock_config.OPENAI_API_KEY = "test-key"
    
    def tearDown(self):
        """Clean up test environment"""
        self.config_patcher.stop()
        
        # Remove temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_documents(self):
        """Create test documents for indexing"""
        # Test manual
        manual_content = """
SP500C PRO INSTALLATION MANUAL

1. MOUNTING REQUIREMENTS
   - Wall must support minimum 45kg
   - Minimum 500mm clearance from ceiling
   - Electrical supply: 240V 15A

2. INSTALLATION STEPS
   a) Mark mounting holes using supplied template
   b) Drill holes with 12mm masonry bit
   c) Insert wall plugs and secure mounting bracket
   d) Connect drain hose to condensate outlet

3. TROUBLESHOOTING
   - Unit not starting: Check power supply and fuses
   - Poor dehumidification: Clean filter, check refrigerant
   - Water leakage: Inspect drain connections

WARRANTY: 5 years parts, 2 years labour
"""
        
        with open(self.docs_dir / "SP500C_PRO_manual.txt", "w") as f:
            f.write(manual_content)
        
        # Test brochure
        brochure_content = """
SP500C PRO SPECIFICATIONS

CAPACITY: 50L/day @ 30°C 80% RH
POWER: 720W
DIMENSIONS: 600 x 400 x 300mm
WEIGHT: 42kg

FEATURES:
- Automatic humidity control
- Digital display
- Timer function
- Hot gas defrost
- Pool safe design

APPLICATIONS:
- Residential basements
- Commercial spaces
- Swimming pool areas
- Storage facilities
"""
        
        with open(self.docs_dir / "SP500C_PRO_brochure.txt", "w") as f:
            f.write(brochure_content)
    
    @patch('rag_pipeline.OpenAIEmbeddings')
    def test_rag_pipeline_initialization(self, mock_embeddings):
        """Test RAG pipeline initialization"""
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        
        pipeline = RAGPipeline()
        pipeline.docs_dir = self.docs_dir
        pipeline.index_dir = self.index_dir
        
        # Test document loading
        documents = pipeline.load_documents()
        
        # Should load 2 documents (manual and brochure)
        self.assertEqual(len(documents), 2)
        
        # Check document metadata
        sources = [doc.metadata['source'] for doc in documents]
        self.assertIn('SP500C_PRO_manual.txt', sources)
        self.assertIn('SP500C_PRO_brochure.txt', sources)
    
    @patch('rag_pipeline.OpenAIEmbeddings')
    def test_document_chunking(self, mock_embeddings):
        """Test document chunking functionality"""
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        
        pipeline = RAGPipeline()
        pipeline.docs_dir = self.docs_dir
        
        # Load and chunk documents
        documents = pipeline.load_documents()
        chunks = pipeline.chunk_documents(documents)
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), len(documents))
        
        # Check chunk properties
        for chunk in chunks:
            self.assertIsInstance(chunk.page_content, str)
            self.assertIn('source', chunk.metadata)
            # Chunks should be reasonably sized
            self.assertLessEqual(len(chunk.page_content), self.mock_config.RAG_CHUNK_SIZE + 100)  # Allow some overlap
    
    @patch('rag_pipeline.FAISS')
    @patch('rag_pipeline.OpenAIEmbeddings')
    def test_index_building(self, mock_embeddings, mock_faiss):
        """Test FAISS index building"""
        # Setup mocks
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        
        mock_vectorstore = MagicMock()
        mock_vectorstore.index.ntotal = 5  # Simulate 5 vectors
        mock_faiss.from_documents.return_value = mock_vectorstore
        
        pipeline = RAGPipeline()
        pipeline.docs_dir = self.docs_dir
        pipeline.index_dir = self.index_dir
        pipeline.embeddings = mock_embeddings_instance
        
        # Test index building
        result = pipeline.build_index()
        
        # Should succeed
        self.assertTrue(result)
        
        # Verify FAISS methods were called
        mock_faiss.from_documents.assert_called_once()
        mock_vectorstore.save_local.assert_called_once_with(str(self.index_dir))


@unittest.skipUnless(RAG_TESTS_ENABLED, "RAG dependencies not available")
class TestRAGIntegration(unittest.TestCase):
    """Test RAG integration with DehumidifierTools"""
    
    @patch('tools.load_vectorstore')
    def test_tools_rag_integration(self, mock_load_vectorstore):
        """Test RAG integration in DehumidifierTools"""
        # Mock vectorstore
        mock_vectorstore = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Installation requires 500mm clearance"
        mock_doc1.metadata = {'source': 'SP500C_PRO_manual.txt'}
        
        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Check power supply and fuses if unit not starting"
        mock_doc2.metadata = {'source': 'SP500C_PRO_manual.txt'}
        
        mock_vectorstore.similarity_search.return_value = [mock_doc1, mock_doc2]
        mock_load_vectorstore.return_value = mock_vectorstore
        
        # Initialize tools
        tools = DehumidifierTools()
        
        # Test document retrieval
        results = tools.retrieve_relevant_docs("installation clearance", k=2)
        
        # Should return formatted chunks
        self.assertEqual(len(results), 2)
        self.assertIn("Installation requires 500mm clearance", results[0])
        self.assertIn("[Source: SP500C_PRO_manual.txt]", results[0])
        
        # Verify vectorstore was called correctly
        mock_vectorstore.similarity_search.assert_called_once_with("installation clearance", k=2)
    
    @patch('tools.load_vectorstore')
    def test_tools_without_rag(self, mock_load_vectorstore):
        """Test tools functionality when RAG is not available"""
        mock_load_vectorstore.return_value = None
        
        tools = DehumidifierTools()
        
        # Should handle gracefully
        results = tools.retrieve_relevant_docs("test query")
        self.assertEqual(results, [])
        
        # Should not include RAG tool in available tools
        available_tools = tools.get_available_tools()
        self.assertNotIn("retrieve_relevant_docs", available_tools)


class TestRAGConfiguration(unittest.TestCase):
    """Test RAG configuration and error handling"""
    
    def test_rag_disabled_config(self):
        """Test behavior when RAG is disabled in config"""
        with patch('config.config') as mock_config:
            mock_config.RAG_ENABLED = False
            
            # Should not attempt to load vectorstore
            if RAG_TESTS_ENABLED:
                from rag_pipeline import load_vectorstore
                result = load_vectorstore()
                self.assertIsNone(result)
    
    def test_missing_openai_key(self):
        """Test behavior when OpenAI key is missing"""
        with patch('config.config') as mock_config:
            mock_config.RAG_ENABLED = True
            mock_config.OPENAI_API_KEY = ""
            
            if RAG_TESTS_ENABLED:
                pipeline = RAGPipeline()
                self.assertIsNone(pipeline.embeddings)


def run_rag_tests():
    """Run RAG tests with proper error handling"""
    if not RAG_TESTS_ENABLED:
        print("Skipping RAG tests - dependencies not available")
        return False
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRAGPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestRAGIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRAGConfiguration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("Running RAG Pipeline Tests...")
    success = run_rag_tests()
    
    if success:
        print("\n✅ All RAG tests passed!")
    else:
        print("\n❌ Some RAG tests failed!")
    
    # Also test basic functionality if dependencies are available
    if RAG_TESTS_ENABLED:
        print("\nTesting basic RAG functionality...")
        try:
            from rag_pipeline import get_rag_pipeline
            pipeline = get_rag_pipeline()
            print(f"✅ RAG pipeline created successfully")
            
            # Test document loading (if docs exist)
            docs = pipeline.load_documents()
            print(f"✅ Loaded {len(docs)} documents")
            
        except Exception as e:
            print(f"❌ Basic RAG test failed: {e}")