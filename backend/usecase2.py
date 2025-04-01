# ---------------------------
# Standard Library Imports
# ---------------------------
import os
import re
import json
import shutil
import pickle
import logging
import asyncio
import tempfile
import warnings
import traceback
import base64
import urllib.parse
from urllib.parse import quote
import urllib3
import time
import uuid
import io
from io import BytesIO
from datetime import datetime
from functools import partial, lru_cache
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import win32com.client  # For handling .doc files
import pythoncom  # For COM initialization
from fake_useragent import UserAgent

# ---------------------------
# Third-Party Libraries
# ---------------------------
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

# Requests & HTTP
import requests
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from playwright.async_api import async_playwright

# ---------------------------
# FastAPI Imports
# ---------------------------
from fastapi import (
    FastAPI,
    Query,
    HTTPException,
    File,
    UploadFile,
    Form,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect
)
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse  # Added import for SSE

# ---------------------------
# Data Processing
# ---------------------------
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# ---------------------------
# NLP & Machine Learning
# ---------------------------
import dspy
from dspy import InputField, OutputField, Signature, Predict
from sentence_transformers import SentenceTransformer
from langchain_openai import AzureOpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
import faiss

# ---------------------------
# PDF & Document Processing
# ---------------------------
import PyPDF2
from PyPDF2 import PdfReader  # For PDF text extraction
from docx2pdf import convert
from docx import Document 
from fpdf import FPDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    BaseDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    Frame,
    PageTemplate
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import reportlab.pdfgen.canvas as reportlab_canvas

# ---------------------------
# Cloud & Storage
# ---------------------------
from azure.storage.blob import BlobServiceClient

# ---------------------------
# Async Networking
# ---------------------------
import aiohttp
from aiohttp import BasicAuth, ClientTimeout

# ---------------------------
# Environment & Utility Imports
# ---------------------------
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# ---------------------------
# Pydantic Import (Added)
# ---------------------------
from pydantic import BaseModel

# Add this near the top of the file, after the logging imports but before any logging is configured
class LiteLLMCacheFilter(logging.Filter):
    """Filter out LiteLLM cache-related error messages"""
    def filter(self, record):
        if record.levelno == logging.ERROR and "LiteLLM Cache: Excepton add_cache: __annotations__" in record.getMessage():
            return False
        return True

# Disable warnings and configure logging
urllib3.disable_warnings()
warnings.simplefilter('ignore', InsecureRequestWarning)

# Add the filter to the root logger to suppress these specific errors
logging.getLogger().addFilter(LiteLLMCacheFilter())
# Also add it to the litellm logger specifically
logging.getLogger('LiteLLM').addFilter(LiteLLMCacheFilter())
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set SSL certificate paths if needed
CERTIFICATE_PATH = os.path.join(os.path.dirname(__file__), "huggingface.co.crt")
os.environ["REQUESTS_CA_BUNDLE"] = CERTIFICATE_PATH
os.environ['CURL_CA_BUNDLE'] = CERTIFICATE_PATH

# Confluence API credentials
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

# Azure OpenAI credentials (for DSPy and the Azure RAG system)
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')

AZURE_OPENAI_EMBED_API_ENDPOINT = os.getenv('AZURE_OPENAI_EMBED_API_ENDPOINT')
AZURE_OPENAI_EMBED_API_KEY = os.getenv('AZURE_OPENAI_EMBED_API_KEY')
AZURE_OPENAI_EMBED_MODEL = os.getenv('AZURE_OPENAI_EMBED_MODEL')
AZURE_OPENAI_EMBED_VERSION = os.getenv('AZURE_OPENAI_EMBED_VERSION')

# Azure Blob Storage credentials
AZURE_STORAGE_SAS_URL = os.getenv('AZURE_STORAGE_SAS_URL')

# Vector database path for Azure Blob Storage indexing
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "vector_db")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "vector_db")

# -------------------------------
# FASTAPI SETUP & DSPy CONFIGURATION
# -------------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure DSPy with Azure OpenAI for manual generation
try:
    lm = dspy.LM(
        model="azure/gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        temperature=0.2,
        max_tokens=4096,
    )
    dspy.configure(lm=lm)
    logger.info("DSPy configured successfully with Azure OpenAI.")
except Exception as e:
    logger.error(f"Failed to configure DSPy: {str(e)}")
    raise RuntimeError(f"Failed to configure DSPy: {str(e)}")

# Define DSPy signature for content generation
class GenerateContent(Signature):
    """Generate structured content for a specific section in the specified language."""
    section_title: str = InputField(desc="Title of the section")
    prompt: str = InputField(desc="Prompt for generating content")
    language: str = InputField(desc="Target language for content generation")
    output: str = OutputField(desc="Generated content in specified language")

# -------------------------------
# SSE Progress
# -------------------------------

# Track active tasks for progress updates
active_tasks = {}

# Helper function to update progress
async def update_progress(client_id: str, message: str, percentage: int):
    logger.info(f"Updating progress for {client_id}: {message}, {percentage}%")
    active_tasks[client_id] = {"message": message, "percentage": percentage}
    if percentage >= 100:
        await asyncio.sleep(1)  # Brief delay to ensure client receives final update
        active_tasks.pop(client_id, None)

# -------------------------------
# TRANSLATION & UTILITY FUNCTIONS
# -------------------------------
def load_translations():
    file_path = os.path.join(os.path.dirname(__file__), "translations.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

TRANSLATIONS = load_translations()

@lru_cache(maxsize=100)
def get_language_texts(language):
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])

def clean_content(text):
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'\[.*?\]|\{.*?\}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def clean_product_query(product_name):
    if " - " in product_name:
        product_name = product_name.split(" - ")[0].strip()
    product_name = product_name.replace("®", "")
    product_name = re.sub(r'[^\w\s]', ' ', product_name)
    product_name = re.sub(r'\s+', ' ', product_name)
    return product_name.strip()

# -------------------------------
# CONFLUENCE HANDLING
# -------------------------------
def normalize_text(text):
    """
    Normalize text by removing special characters, extra spaces, and converting to lowercase.
    """
    # Remove special characters and extra spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()

def get_confluence_vector_store(content):
    try:
        if not content.strip():
            return None
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.create_documents([content])
        if not texts:
            return None
            
        # Replace HuggingFaceEmbeddings with AzureOpenAIEmbeddings
        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_OPENAI_EMBED_API_ENDPOINT,
            api_key=AZURE_OPENAI_EMBED_API_KEY,
            model=AZURE_OPENAI_EMBED_MODEL,
            api_version=AZURE_OPENAI_EMBED_VERSION
        )
        
        vector_store = FAISS.from_documents(texts, embeddings)
        return vector_store
    except Exception as e:
        logger.error(f"Error creating Confluence vector store: {str(e)}")
        return None

# -------------------------------
# AZURE BLOB STORAGE INTEGRATION
# -------------------------------
class FAISSIndex:
    def __init__(self):
        # Fixed dimension for text-embedding-3-large
        self.dimension = 384  
        self.index_path = os.path.join(VECTOR_DB_PATH, "index.faiss")
        self.metadata_path = os.path.join(VECTOR_DB_PATH, "metadata.pkl")
        self.documents: List = []
        self.index: Optional[faiss.Index] = None
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)

    def create(self) -> None:
        self.index = faiss.IndexFlatL2(self.dimension)
        logger.info(f"Created new FAISS index with dimension {self.dimension}.")

    def add(self, vectors: np.ndarray, documents: List) -> None:
        if self.index is None:
            self.create()
        if vectors.shape[0] == 0:
            raise ValueError("Cannot add empty vectors")
        if vectors.shape[1] != self.dimension:
            # Ensure vectors are the correct dimension
            vectors = self._adjust_dimensions(vectors)
        self.index.add(vectors)
        self.documents.extend(documents)
        logger.info(f"Added {len(documents)} documents to the FAISS index.")

    def _adjust_dimensions(self, vectors: np.ndarray) -> np.ndarray:
        """Adjust vectors to match the required dimension"""
        if vectors.shape[1] > self.dimension:
            logger.warning(f"Truncating vectors from {vectors.shape[1]} to {self.dimension} dimensions")
            return vectors[:, :self.dimension]
        elif vectors.shape[1] < self.dimension:
            logger.warning(f"Padding vectors from {vectors.shape[1]} to {self.dimension} dimensions")
            return np.pad(vectors, ((0, 0), (0, self.dimension - vectors.shape[1])), mode='constant')
        return vectors

    def save(self) -> None:
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.documents, f)
            logger.info("FAISS index and metadata saved successfully.")

    def load(self) -> bool:
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.documents = pickle.load(f)
                logger.info(f"FAISS index loaded: {self.index.ntotal} vectors, dimension {self.index.d}, {len(self.documents)} documents.")
                return True
            logger.info("No existing FAISS index found.")
            return False   
        except Exception as e:
            logger.error(f"Error loading FAISS index: {str(e)}", exc_info=True)
            return False

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or not self.documents:
            logger.warning("FAISS index is empty or not loaded.")
            return [] 
        # Ensure proper vector shape and dimensions
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        elif query_vector.ndim > 2:
            query_vector = query_vector.reshape(1, -1)
            
        # Adjust dimensions if needed
        query_vector = self._adjust_dimensions(query_vector.astype('float32'))
        
        logger.info(f"Searching index with {self.index.ntotal} vectors (dim: {self.index.d})")
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = self.documents[idx]
            content = doc.page_content
            metadata = doc.metadata
            distance = float(distances[0][i])
            score = 1 / (1 + distance)
            results.append({
                'content': content,
                'metadata': metadata,
                'score': score
            })
        logger.info(f"FAISS search returned {len(results)} results.")
        return results

class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def process_pdf(self, pdf_content: bytes) -> str:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_content)
                temp_file_path = temp_file.name

            with open(temp_file_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            
            os.unlink(temp_file_path)
            logger.info("Processed PDF content successfully.")
            return text
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
            return ""

    def create_documents(self, content: str, metadata: Dict[str, Any]) -> List:
        if not content:
            logger.warning("Empty content provided for document creation")
            return []
            
        chunks = self.text_splitter.split_text(content)
        logger.info(f"Split content into {len(chunks)} document chunks.")
        return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

class Document:
    def __init__(self, page_content: str, metadata: Dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata

class RAGSystem:
    def __init__(self):
        parsed_url = urllib.parse.urlparse(AZURE_STORAGE_SAS_URL)
        account_name = parsed_url.netloc.split('.')[0]
        container_name = parsed_url.path.strip('/').split('/')[0]
        self.blob_service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=AZURE_STORAGE_SAS_URL.split('?')[1],
            connection_verify=False
        )
        self.container_client = self.blob_service_client.get_container_client(container_name)
        logger.info(f"Connected to Azure Blob Storage container: {container_name}")
        
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_OPENAI_EMBED_API_ENDPOINT,
            api_key=AZURE_OPENAI_EMBED_API_KEY,
            model="text-embedding-3-large",
            api_version=AZURE_OPENAI_EMBED_VERSION,
            dimensions=384
  # Explicitly set dimensions
        )
        self.documents = []
        self.index = FAISSIndex()
        self.document_processor = DocumentProcessor()
        from openai import AzureOpenAI
        self.llm = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        self._ensure_index()

    def _ensure_index(self) -> None:
        """Load or build the FAISS index with proper document storage"""
        if not self.index.load():
            logger.info("Building new FAISS index from Azure Blob PDFs.")
            self._build_index()
        else:
            if not hasattr(self.index, 'index') or self.index.index.ntotal == 0:
                logger.warning("Loaded index appears empty, rebuilding...")
                self._build_index()
            else:
                with open(os.path.join(VECTOR_DB_PATH, "metadata.pkl"), 'rb') as f:
                    self.documents = pickle.load(f)
                logger.info(f"Loaded {len(self.documents)} documents with index")

    def _fetch_blob_content(self) -> List[Dict[str, Any]]:
        documents = []
        logger.info("Fetching blob content from Azure Blob Storage...")
        blob_list = self.container_client.list_blobs()
        for blob in blob_list:
            if blob.name.endswith('.pdf'):
                logger.info(f"Found PDF blob: {blob.name}")
                blob_client = self.container_client.get_blob_client(blob.name)
                blob_content = blob_client.download_blob().readall()
                metadata = {
                    'source': blob.name,
                    'type': 'pdf',
                    'created': blob.creation_time,
                    'modified': blob.last_modified
                }
                documents.append({
                    'content': blob_content,
                    'metadata': metadata
                })
        logger.info(f"Fetched {len(documents)} PDF blobs from Azure.")
        return documents

    def _build_index(self) -> None:
        """Build the index and properly store documents"""
        blobs = self._fetch_blob_content()
        if not blobs:
            logger.warning("No content fetched from Azure Blob Storage")
            return

        all_documents = []
        all_vectors = []

        for blob in blobs:
            try:
                logger.info(f"Processing blob: {blob['metadata'].get('source', 'unknown')}")
                clean_text = self.document_processor.process_pdf(blob['content'])
                documents = self.document_processor.create_documents(clean_text, blob['metadata'])
                vectors = self.embeddings.embed_documents([doc.page_content for doc in documents])
                all_documents.extend(documents)
                all_vectors.extend(vectors)
            except Exception as e:
                logger.error(f"Error processing blob {blob['metadata'].get('source', 'unknown')}: {str(e)}", exc_info=True)
                continue

        if all_vectors:
            vectors_np = np.array(all_vectors).astype('float32')
            self.index.add(vectors_np, all_documents)
            self.index.save()
            logger.info("Azure Blob Storage index built successfully.")

    def query(self, query_text: str) -> Dict[str, Any]:
        try:
            result = {
                'answer': '',
                'sources': [],
                'error': None
            }

            # 1. Generate query embedding
            try:
                logger.info(f"Generating embedding for query: '{query_text}'")
                query_vector = self.embeddings.embed_query(query_text)
                if query_vector is None:
                    raise ValueError("Embedding service returned None")
                if not isinstance(query_vector, np.ndarray):
                    logger.info("Converting embedding to numpy array")
                    query_vector = np.array(query_vector, dtype='float32')
                if query_vector.ndim != 1:
                    raise ValueError(f"Invalid embedding shape: {query_vector.shape}")
                logger.debug(f"Embedding vector generated (shape: {query_vector.shape})")
            except Exception as e:
                logger.error(f"Embedding generation failed: {str(e)}", exc_info=True)
                return {'answer': 'Failed to generate embedding', 'sources': [], 'error': str(e)}

            # 2. Search the vector index
            try:
                if self.index is None:
                    raise ValueError("FAISS index not initialized")
                if not hasattr(self.index, 'index') or not hasattr(self.index.index, 'ntotal'):
                    raise ValueError("FAISS index not properly initialized")
                if self.index.index.ntotal == 0:
                    raise ValueError("FAISS index is empty")
                    
                logger.info(f"Index stats - vectors: {self.index.index.ntotal}, dimension: {self.index.index.d}")
                results = self.index.search(query_vector, 5)
                sources = []
                seen_titles = set()
                for res in results:
                    source_title = res['metadata'].get('source', 'Unknown Document')
                    if source_title not in seen_titles:
                        sources.append({
                            'title': source_title,
                            'content': res['content'][:500] + "..." if len(res['content']) > 500 else res['content'],
                            'confidence': round(res['score'] * 100, 2),
                            'modified': res['metadata'].get('modified', 'Unknown date')
                        })
                        seen_titles.add(source_title)
                if not sources:
                    result['answer'] = "No relevant documents found"
                    return result
                logger.info(f"Found {len(sources)} relevant documents")
            except Exception as e:
                logger.error(f"Vector search failed: {str(e)}", exc_info=True)
                result['error'] = str(e)
                result['answer'] = "Failed to search documents"
                return result

            # 3. Generate LLM response
            try:
                context = "\n\n".join([f"Document {i+1}: {src['content']}" for i, src in enumerate(sources)])
                messages = [
                    {"role": "system", "content": "You are a technical expert. Answer using ONLY the provided context."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
                ]
                logger.info("Generating LLM response...")
                response = self.llm.chat.completions.create(
                    model=AZURE_OPENAI_DEPLOYMENT,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=800
                )
                result['answer'] = response.choices[0].message.content.strip()
                result['sources'] = sources
                logger.info("Successfully generated response")
                return result
            except Exception as e:
                logger.error(f"LLM response generation failed: {str(e)}", exc_info=True)
                result['error'] = str(e)
                result['answer'] = "Failed to generate response"
                return result

        except Exception as e:
            logger.error(f"Unexpected error in query processing: {str(e)}", exc_info=True)
            return {'answer': "An unexpected error occurred", 'sources': [], 'error': str(e)}

def get_blob_client(blob_name: str):
    """Helper function to get blob client"""
    parsed_url = urllib.parse.urlparse(AZURE_STORAGE_SAS_URL)
    account_name = parsed_url.netloc.split('.')[0]
    container_name = parsed_url.path.strip('/').split('/')[0]
    blob_service_client = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=AZURE_STORAGE_SAS_URL.split('?')[1],
        connection_verify=False
    )
    container_client = blob_service_client.get_container_client(container_name)
    return container_client.get_blob_client(blob_name)

async def convert_to_pdf(file: UploadFile) -> bytes:
    """Convert uploaded file to PDF format"""
    try:
        content = await file.read()
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension == '.pdf':
            logger.info(f"File {file.filename} is already in PDF format")
            return content
        
        elif file_extension in ['.docx', '.doc']:
            logger.info(f"Starting conversion of {file_extension} file: {file.filename} to PDF")
            
            temp_dir = tempfile.mkdtemp()
            temp_doc_path = os.path.join(temp_dir, f"document{file_extension}")
            temp_pdf_path = os.path.join(temp_dir, "document.pdf")
            
            with open(temp_doc_path, 'wb') as f:
                f.write(content)
                
            logger.info(f"Created temporary file at {temp_doc_path}")
            
            pythoncom.CoInitialize()
            success = False
            
            try:
                logger.info("Creating Word application instance")
                word = win32com.client.DispatchEx('Word.Application')
                word.Visible = False
                word.DisplayAlerts = 0
                
                try:
                    abs_doc_path = os.path.abspath(temp_doc_path)
                    abs_pdf_path = os.path.abspath(temp_pdf_path)
                    
                    logger.info(f"Opening document from {abs_doc_path}")
                    doc = word.Documents.Open(abs_doc_path, ReadOnly=1)
                    
                    logger.info(f"Saving as PDF to {abs_pdf_path}")
                    doc.SaveAs(abs_pdf_path, FileFormat=17)
                    doc.Close()
                    
                    if os.path.exists(abs_pdf_path):
                        logger.info("PDF created successfully")
                        with open(abs_pdf_path, 'rb') as pdf_file:
                            success = True
                            return pdf_file.read()
                    else:
                        logger.error(f"PDF file not found at {abs_pdf_path}")
                        
                except Exception as e:
                    logger.error(f"Error in Word automation: {str(e)}", exc_info=True)
                
                finally:
                    try:
                        word.Quit()
                    except:
                        pass
            
            except Exception as e:
                logger.error(f"Error creating Word application: {str(e)}", exc_info=True)
            
            finally:
                pythoncom.CoUninitialize()
                
                # Clean up temp files
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up: {str(e)}")
            
            if not success:
                raise Exception(f"Failed to convert {file_extension} to PDF using COM automation")
                
        elif file_extension == '.txt':
            logger.info(f"Starting conversion of TXT file: {file.filename} to PDF")
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            text_content = content.decode('utf-8')
            lines = text_content.split('\n')
            
            for line in lines:
                # Replace any non-printable characters
                line = ''.join(c if ord(c) < 128 else ' ' for c in line)
                if line.strip():
                    pdf.multi_cell(0, 10, txt=line)
                else:
                    pdf.ln(5)
            
            pdf_content = pdf.output(dest='S').encode('latin-1')
            logger.info(f"Successfully converted TXT file: {file.filename} to PDF")
            return pdf_content
            
        else:
            logger.error(f"Unsupported file type: {file_extension}")
            raise HTTPException(
                status_code=400,
                detail="Supported file types: PDF, DOCX, DOC, and TXT files."
            )
    
    except Exception as e:
        logger.error(f"Error converting file to PDF: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert file to PDF: {str(e)}"
        )

async def upload_to_azure_blob(file: UploadFile) -> str:
    """Upload file to Azure Blob Storage"""
    try:
        pdf_content = await convert_to_pdf(file)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = os.path.splitext(secure_filename(file.filename))[0]
        blob_name = f"{timestamp}_{original_name}.pdf"
        
        blob_client = get_blob_client(blob_name)
        blob_client.upload_blob(pdf_content, overwrite=True)
        
        logger.info(f"Successfully uploaded converted PDF file {blob_name} to Azure Blob Storage")
        return blob_name
        
    except Exception as e:
        logger.error(f"Error uploading to Azure Blob Storage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

# Helper function to retrieve Azure Blob Storage content for a given query
def retrieve_azure_blob_content(query: str) -> str:
    try:
        logger.info(f"Retrieving Azure Blob content for query: {query}")
        azure_system = RAGSystem()
        result = azure_system.query(query)
        content = result.get('answer', '')
        if not content.strip():
            return "No relevant Azure Blob Storage content found."
        return content
    except Exception as e:
        logger.error(f"Error retrieving Azure blob content: {str(e)}")
        return "No relevant Azure Blob Storage content found."
# -------------------------------
# COMBINING ALL SOURCES
# -------------------------------
def combine_all_content(scraped_data, pdf_content, confluence_content, azure_blob_content):
    combined_content = []
    used_content = set()  # Track used content to avoid duplicates

    def add_content(section_title, content):
        if content and isinstance(content, str) and content.strip() and content not in used_content:
            combined_content.append(f"=== {section_title} ===")
            combined_content.append(content)
            used_content.add(content)

    # Add scraped data
    if scraped_data:
        product_info = []
        product_info.append(f"Product Name: {scraped_data.get('product_name', 'N/A')}")
        if features := scraped_data.get('key_features', []):
            product_info.append("\nKey Features:")
            product_info.extend([f"- {feature}" for feature in features])
        add_content("Product Information", "\n".join(product_info))

        # Add specifications separately
        if tech_specs := scraped_data.get('technical_specifications', {}):
            specs_content = []
            specs_content.append("Technical Specifications:")
            for key, value in tech_specs.items():
                specs_content.append(f"- {key}: {value}")
            add_content("Technical Specifications", "\n".join(specs_content))

        if gen_specs := scraped_data.get('general_specifications', {}):
            specs_content = []
            specs_content.append("General Specifications:")
            for key, value in gen_specs.items():
                specs_content.append(f"- {key}: {value}")
            add_content("General Specifications", "\n".join(specs_content))

    # Add PDF content if it exists and is a string
    if pdf_content and isinstance(pdf_content, str):
        add_content("Additional Documentation", pdf_content)

    # Add Confluence content if it exists and is a string
    if confluence_content and isinstance(confluence_content, str):
        add_content("Confluence Documentation", confluence_content)

    # Add Azure Blob content if it exists and is a string
    if azure_blob_content and isinstance(azure_blob_content, str):
        add_content("Azure Documentation", azure_blob_content)

    # If no content was added, add a default message
    if not combined_content:
        combined_content.append("No content available for this product.")

    return "\n\n".join(combined_content)

# -------------------------------
# PDF GENERATION & WEB SCRAPING
# -------------------------------
def generate_pdf(product_data, content, is_faq=False):
    try:
        buffer = BytesIO()
        
        # Dictionary to store section names and their page numbers
        section_pages = {}
        
        # Custom paragraph class to set bookmarks
        class BookmarkParagraph(Paragraph):
            def __init__(self, text, style, bookmark_key):
                super().__init__(text, style)
                self.bookmark_key = bookmark_key
            
            def draw(self):
                super().draw()
                self.canv.bookmarkPage(self.bookmark_key)
                section_pages[self.bookmark_key] = self.canv.getPageNumber()
        
        # Function to add page numbers to ALL pages
        def add_page_number(canvas, doc):
            canvas.saveState()
            # Draw the black border
            canvas.setStrokeColor(colors.black)  # Set border color to black
            canvas.setLineWidth(1)               # Set line thickness to 1 point
            border_margin = 28
            canvas.rect(
                border_margin,                   # x-coordinate (left edge)
                border_margin,                   # y-coordinate (bottom edge)
                doc.pagesize[0] - 2 * border_margin,  # Width of the rectangle
                doc.pagesize[1] - 2 * border_margin   # Height of the rectangle
            )
            page_num = canvas.getPageNumber()
            text = f"Page {page_num}"
            canvas.setFont('Helvetica', 10)
            canvas.drawCentredString(doc.pagesize[0] / 2, 36, text)
            logger.info(f"Drawing page number {page_num} at y=36")
            canvas.restoreState()
        
        # Build document with helper function
        def create_doc():
            # Create the document
            doc = BaseDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            # Create a single frame for all pages
            frame = Frame(
                doc.leftMargin,
                doc.bottomMargin + 40,  # Leave space for page numbers
                doc.width,
                doc.height - 40,
                id='normal'
            )
            
            # Create a SINGLE template for ALL pages
            template = PageTemplate(
                id='all_pages', 
                frames=frame,
                onPage=add_page_number
            )
            
            # Add ONLY this template to the document - no defaults
            doc.addPageTemplates([template])
            
            return doc
        
        # Get styles
        styles = getSampleStyleSheet()
        
        title_style = styles['Title']
        title_style.fontName = 'Helvetica-Bold'
        title_style.fontSize = 18
        title_style.textColor = colors.HexColor('#1e40af')
        
        heading1_style = styles['Heading1']
        heading1_style.fontName = 'Helvetica-Bold'
        heading1_style.fontSize = 16
        heading1_style.textColor = colors.HexColor('#1e3a8a')
        
        heading2_style = styles['Heading2']
        heading2_style.fontName = 'Helvetica-Bold'
        heading2_style.fontSize = 14
        heading2_style.textColor = colors.HexColor('#2563eb') if not is_faq else colors.black
        
        normal_style = styles['Normal']
        normal_style.fontName = 'Helvetica'
        normal_style.fontSize = 11
        normal_style.leading = 14
        normal_style.textColor = colors.black
        
        # Build elements list
        def build_elements(include_toc_pages=True):
            elements = []
            
            language_texts = get_language_texts(product_data.get("language", "en"))
            if is_faq:
                title_text = f"{language_texts['faq_title']}"
            else:
                title_text = f"{language_texts['manual_title']}"
            
            elements.append(Paragraph(title_text, title_style))
            elements.append(Spacer(1, 0.25 * inch))
            elements.append(Paragraph(product_data['product_category'], styles['Heading3']))
            elements.append(Spacer(1, 0.5 * inch))
            
            elements.append(Paragraph(language_texts['table_of_contents'], heading1_style))
            toc_data = [[language_texts['section'], language_texts['page']]]
            for section in content.keys():
                clean_section = clean_content(section)
                page_num = section_pages.get(clean_section, "") if include_toc_pages else ""
                toc_data.append([clean_section, str(page_num)])
            
            toc_table = Table(toc_data, colWidths=[400, 100])
            toc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 13),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#cbd5e1')),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(toc_table)
            
            for section, section_content in content.items():
                elements.append(PageBreak())
                clean_section = clean_content(section)
                elements.append(BookmarkParagraph(clean_section, heading1_style, clean_section))
                elements.append(Spacer(1, 0.1 * inch))

                if section == language_texts["technical_specifications"]:
                    tables = format_specifications_tables(product_data, is_faq)
                    if tables:
                        for table in tables:
                            elements.append(table)
                            elements.append(Spacer(1, 0.2 * inch))
                        continue
                
                paragraphs = clean_content(section_content).split('\n')
                for paragraph in paragraphs:
                    if paragraph.strip():
                        if paragraph.strip().endswith(':'):
                            elements.append(Paragraph(paragraph.strip(), heading2_style))
                        else:
                            elements.append(Paragraph(paragraph.strip(), normal_style))
                        elements.append(Spacer(1, 0.05 * inch))
                
                elements.append(Spacer(1, 0.2 * inch))
            
            return elements
        
        # First build to collect page numbers
        doc = create_doc()
        first_elements = build_elements(include_toc_pages=False)
        doc.build(first_elements)
        
        # Second build with updated TOC
        buffer.seek(0)
        buffer.truncate(0)  # Clear the buffer for the second build
        doc = create_doc()
        second_elements = build_elements(include_toc_pages=True)
        doc.build(second_elements)
        
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

def get_product_link(selected_item):
    for product in products_data.get("products", []):
        for subproduct in product.get("subproducts", []):
            for item in subproduct.get("sub_subproducts", []):
                if item.get("sub_subproduct_name") == selected_item:
                    return item.get("sub_subproduct_link")
    return None

def generate_content_prompts(cleaned_product_name, combined_content, language):
    language_texts = get_language_texts(language)
    language_instruction = (
        f"You are a professional technical writer creating content in {language}.\n"
        "Instructions:\n"
        "1. Generate ALL content in the target language.\n"
        "2. Maintain technical accuracy and use a formal tone.\n"
        "3. Preserve all technical terms and measurements.\n"
        "4. Keep the same structured format as the original.\n"
        "5. Ensure all headings and subheadings are in the target language.\n"
        "6. IMPORTANT: Create unique content for each section that doesn't duplicate information from other sections.\n"
    )
    context_text = f"\n\nRelevant context:\n{combined_content}\n\n"
    prompts = {}
    sections = {
        "introduction": language_texts["introduction"],
        "key_features": language_texts["key_features"],
        "technical_specifications": language_texts["technical_specifications"],
        "safety_information": language_texts["safety_information"],
        "setup_instructions": language_texts["setup_instructions"],
        "operation_instructions": language_texts["operation_instructions"],
        "maintenance_and_care": language_texts["maintenance_and_care"],
        "troubleshooting": language_texts["troubleshooting"],
        "warranty_information": language_texts["warranty_information"]
    }
    
    # Special instructions for sections that often overlap
    section_specific_instructions = {
        "maintenance_and_care": "IMPORTANT: Focus on regular maintenance tasks like cleaning, lubrication, and inspection. Do not include content about fixing problems or diagnosing issues, as that belongs in Troubleshooting.",
        "troubleshooting": "IMPORTANT: Focus on diagnosing and fixing specific problems or issues. Do not include routine maintenance tasks, as those belong in Maintenance and Care.",
        "technical_specifications": "IMPORTANT: This section should consist of tabular data and precise measurements. Do not repeat detailed descriptions of features.",
        "key_features": "IMPORTANT: Focus on the most important capabilities and benefits. Do not include detailed specifications as those belong in Technical Specifications."
    }
    
    for key, section_title in sections.items():
        prompt = f"{language_instruction}{context_text}"
        
        # Add section-specific instructions to reduce redundancy
        if key in section_specific_instructions:
            prompt += f"{section_specific_instructions[key]}\n\n"
            
        prompt += f"Task: Generate a detailed '{section_title}' section for {cleaned_product_name} in {language}."
        prompts[section_title] = prompt
        
    return prompts

async def translate_specifications(specs: Dict[str, str], language: str) -> Dict[str, str]:
    """Translate specification keys and values into the target language using DSPy."""
    try:
        if not specs:
            return {}
        
        # Prepare the prompt for translation
        specs_text = "\n".join([f"{key}: {value}" for key, value in specs.items()])
        language_texts = get_language_texts(language)
        prompt = f"""
        You are a professional translator converting technical specifications into {language}.
        Instructions:
        1. Translate the following specification keys and values into {language}.
        2. Preserve technical accuracy and maintain a formal tone.
        3. Do not translate units (e.g., 'V', 'rpm', 'Hz', 'LB', 'IN') or proper nouns (e.g., brand names, country names like 'Mexico').
        4. Return the translated content in the same key-value format.
        
        Specifications to translate:
        {specs_text}
        """
        
        # Use DSPy to translate
        predictor = Predict(GenerateContent)
        result = await asyncio.to_thread(
            lambda: predictor(
                section_title=f"Translated Specifications in {language}",
                prompt=prompt,
                language=language
            )
        )
        
        if not result or not hasattr(result, 'output'):
            logger.warning(f"Failed to translate specifications into {language}")
            return specs  # Fallback to original if translation fails
        
        # Parse the translated output back into a dictionary
        translated_specs = {}
        lines = result.output.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                translated_specs[key.strip()] = value.strip()
        
        logger.info(f"Translated {len(translated_specs)} specification items into {language}")
        return translated_specs
    
    except Exception as e:
        logger.error(f"Error translating specifications into {language}: {str(e)}")
        return specs  # Fallback to original on error

def format_specifications_tables(product_data, is_faq=False):
    try:
        tables = []
        styles = getSampleStyleSheet()
        language = product_data.get("language", "en")
        language_texts = get_language_texts(language)
        
        sub_header_style = styles['Heading4']
        sub_header_style.fontName = 'Helvetica-Bold'
        sub_header_style.fontSize = 12
        sub_header_style.textColor = colors.HexColor('#1e40af') if not is_faq else colors.black
        
        header_bg_color = colors.HexColor('#e6efff') if not is_faq else colors.HexColor('#f5f5f5')
        header_text_color = colors.HexColor('#1e40af') if not is_faq else colors.black
        
        scraped_data = product_data.get("scraped_data", {})
        
        tech_specs = scraped_data.get('technical_specifications', {})
        if language != "en":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tech_specs = loop.run_until_complete(translate_specifications(tech_specs, language))
            finally:
                loop.close()
        
        if tech_specs:
            logger.info(f"Formatting {len(tech_specs)} technical specifications")
            tables.append(Paragraph(language_texts["technical_specifications"], sub_header_style))
            tables.append(Spacer(1, 0.1 * inch))
            
            # Create paragraph style for cell content with wrapping
            cell_style = styles['Normal'].clone('CellStyle')
            cell_style.fontSize = 10
            cell_style.leading = 12  # Line spacing
            
            # Prepare data with paragraphs to enable wrapping
            data = [[Paragraph(language_texts["specification"], cell_style), 
                     Paragraph(language_texts["value"], cell_style)]]
            
            for key, value in tech_specs.items():
                data.append([
                    Paragraph(clean_html_for_reportlab(str(key)), cell_style), 
                    Paragraph(clean_html_for_reportlab(str(value) if value is not None else "N/A"), cell_style)
                ])
            
            if len(data) > 1:
                # Adjust column widths (first column wider for specification names)
                table = Table(data, colWidths=[275, 225])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), header_bg_color),
                    ('TEXTCOLOR', (0, 0), (-1, 0), header_text_color),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                    ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical alignment
                    ('TOPPADDING', (0, 1), (-1, -1), 8),     # Add more padding between rows
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ]))
                tables.append(table)
            else:
                logger.warning("No valid technical specifications data to format")
        
        gen_specs = scraped_data.get('general_specifications', {})
        if language != "en":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen_specs = loop.run_until_complete(translate_specifications(gen_specs, language))
            finally:
                loop.close()
        
        if gen_specs:
            logger.info(f"Formatting {len(gen_specs)} general specifications")
            tables.append(Spacer(1, 0.5 * inch))
            tables.append(Paragraph(language_texts["general_specifications"], sub_header_style))
            tables.append(Spacer(1, 0.1 * inch))
            
            # Create paragraph style for cell content with wrapping
            cell_style = styles['Normal'].clone('CellStyle')
            cell_style.fontSize = 10
            cell_style.leading = 12  # Line spacing
            
            # Prepare data with paragraphs to enable wrapping
            data = [[Paragraph(language_texts["specification"], cell_style), 
                     Paragraph(language_texts["value"], cell_style)]]
            
            for key, value in gen_specs.items():
                data.append([
                    Paragraph(clean_html_for_reportlab(str(key)), cell_style), 
                    Paragraph(clean_html_for_reportlab(str(value) if value is not None else "N/A"), cell_style)
                ])
            
            if len(data) > 1:
                # Adjust column widths (first column wider for specification names)
                table = Table(data, colWidths=[275, 225])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), header_bg_color),
                    ('TEXTCOLOR', (0, 0), (-1, 0), header_text_color),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                    ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#cbd5e1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical alignment
                    ('TOPPADDING', (0, 1), (-1, -1), 8),     # Add more padding between rows
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ]))
                tables.append(table)
            else:
                logger.warning("No valid general specifications data to format")
        
        if tables:
            logger.info(f"Formatted {len(tables)} tables for specifications")
            return tables
        else:
            logger.info("No specification tables created")
            return None
    except Exception as e:
        logger.error(f"Error formatting specification tables: {str(e)}")
        return None
    
def run_generate_content(section_title: str, prompt: str, language: str) -> Tuple[str, str]:
    """Generate content for a specific section."""
    try:
        generate_content = Predict(GenerateContent)
        result = generate_content(
            section_title=section_title,
            prompt=prompt,
            language=language
        )
        return section_title, result.output
    except Exception as e:
        logger.error(f"Error generating content for {section_title}: {str(e)}")
        return section_title, ""

async def parallel_content_generation(prompts: Dict[str, str], language: str) -> Dict[str, str]:
    try:
        # First attempt: Try parallel processing with more robust error handling
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:  # Reduce concurrency
            loop = asyncio.get_event_loop()
            
            # Create tasks for each prompt
            futures = []
            for title, prompt in prompts.items():
                future = loop.run_in_executor(
                    executor,
                    run_generate_content,
                    title,
                    prompt,
                    language
                )
                futures.append(future)
            
            # Wait for all tasks to complete
            completed_results = await asyncio.gather(*futures, return_exceptions=True)
            
            # Process results
            result_dict = {}
            errors = []
            for result in completed_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in content generation: {str(result)}")
                    errors.append(str(result))
                    continue
                if isinstance(result, tuple) and len(result) == 2:
                    section_title, content = result
                    if content and content.strip():  # Only add non-empty content
                        result_dict[section_title] = content
            
            # If we got some results but not all, that's still acceptable
            if result_dict:
                logger.info(f"Generated {len(result_dict)} sections successfully with {len(errors)} errors")
                return result_dict
                
            # If parallel processing failed completely, try sequential processing
            if errors:
                logger.warning(f"Parallel content generation failed with errors: {errors[:3]}...")
                logger.info("Falling back to sequential content generation")
                return await sequential_content_generation(prompts, language)
            
            raise ValueError("Failed to generate any content")

    except Exception as e:
        logger.error(f"Error in parallel content generation: {str(e)}")
        # Try sequential as a fallback
        return await sequential_content_generation(prompts, language)

async def sequential_content_generation(prompts: Dict[str, str], language: str) -> Dict[str, str]:
    """Fall back to sequential content generation with retries if parallel fails"""
    result_dict = {}
    retry_count = 3
    retry_delay = 2  # seconds
    
    for title, prompt in prompts.items():
        for attempt in range(retry_count):
            try:
                logger.info(f"Generating content for '{title}' (Attempt {attempt+1}/{retry_count})")
                result = await asyncio.to_thread(
                    run_generate_content,
                    title,
                    prompt,
                    language
                )
                
                if isinstance(result, tuple) and len(result) == 2:
                    section_title, content = result
                    if content and content.strip():
                        result_dict[section_title] = content
                        break  # Success, move to next section
            except Exception as e:
                logger.error(f"Error generating '{title}' (Attempt {attempt+1}): {str(e)}")
                if attempt < retry_count - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
    
    if not result_dict:
        raise ValueError("Failed to generate any content after multiple retries")
    
    return result_dict

def run_generate_content(section_title: str, prompt: str, language: str) -> Tuple[str, str]:
    """Generate content for a specific section with improved error handling"""
    try:
        generate_content = Predict(GenerateContent)
        # Add timeout and retry handling
        max_retries = 3
        retry_delay = 1
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = generate_content(
                    section_title=section_title,
                    prompt=prompt,
                    language=language,
                    temperature=0.3  # Lower temperature for more consistent output
                )
                return section_title, result.output
            except Exception as e:
                last_error = e
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
        
        # If we get here, all retries failed
        raise last_error or ValueError(f"Failed to generate content for {section_title} after {max_retries} attempts")
    except Exception as e:
        logger.error(f"Error generating content for {section_title}: {str(e)}")
        return section_title, ""

async def async_scrape_product_data(url: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    """Async version of scrape_product_data with dynamic headers and robust error handling"""
    try:
        # Initialize UserAgent for dynamic rotation
        ua = UserAgent()
        headers = {
            "User-Agent": ua.random,  # Start with a random User-Agent
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",
        }
        
        max_retries = 3
        content = None
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                # Rotate User-Agent for each retry
                headers["User-Agent"] = ua.random
                logger.info(f"Attempt {attempt + 1}/{max_retries} to scrape {url} with User-Agent: {headers['User-Agent']}")
                async with session.get(url, headers=headers, verify_ssl=False, timeout=timeout) as response:
                    if response.status == 403 or response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                        logger.warning(f"Received {response.status} for {url}, retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    content = await response.text()
                    logger.info(f"Successfully retrieved content from {url}")
                    break
            except aiohttp.ClientResponseError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Scraping failed after {max_retries} attempts: {str(e)}")
                    return {
                        "product_name": "Unknown Product",
                        "key_features": [],
                        "technical_specifications": {},
                        "general_specifications": {}
                    }
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    return {
                        "product_name": "Unknown Product",
                        "key_features": [],
                        "technical_specifications": {},
                        "general_specifications": {}
                    }
        
        # If no content was retrieved after retries, return fallback
        if content is None:
            logger.error(f"No content retrieved from {url} after {max_retries} attempts")
            return {
                "product_name": "Unknown Product",
                "key_features": [],
                "technical_specifications": {},
                "general_specifications": {}
            }
        
        # Parse the content with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract product name
        product_name = "Unknown Product"
        h1_tag = soup.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)
        logger.info(f"Scraped product name: {product_name}")
        
        # Extract key features
        key_features = []
        key_features_container = soup.find('div', class_='product-info')
        if key_features_container:
            feature_list = key_features_container.find('ul')
            if feature_list:
                features = feature_list.find_all('li')
                for feature in features:
                    key_features.append(feature.get_text(strip=True))
        logger.info(f"Scraped {len(key_features)} key features")
        
        # Initialize dictionaries for specifications
        technical_specs = {}
        general_specs = {}
        
        # Find the specification navigation links
        spec_nav = soup.find('ul', class_='pdp-spec-nav')
        if not spec_nav:
            logger.warning("No pdp-spec-nav found; unable to categorize specifications")
            return {
                "product_name": product_name,
                "key_features": key_features,
                "technical_specifications": technical_specs,
                "general_specifications": general_specs
            }
        
        # Map tab labels to their IDs
        tab_mapping = {}
        for nav_item in spec_nav.find_all('a', class_='pdp-spec-nav__item'):
            tab_label = nav_item.get_text(strip=True).lower()
            tab_id = nav_item.get('href', '').lstrip('#')  # e.g., "tab-0"
            if tab_id:
                tab_mapping[tab_id] = tab_label
                logger.info(f"Found tab mapping: {tab_id} -> {tab_label}")
        
        # Find the tab content container
        tab_content = soup.find('div', class_='tab-content')
        if not tab_content:
            logger.warning("No tab-content div found; cannot process specifications")
            return {
                "product_name": product_name,
                "key_features": key_features,
                "technical_specifications": technical_specs,
                "general_specifications": general_specs
            }
        logger.info(f"Found tab-content div")
        
        # Process each tab by ID from tab_mapping
        tabs = [soup.find('div', id=tab_id) for tab_id in tab_mapping.keys()]
        tabs = [tab for tab in tabs if tab is not None]  # Filter out None results
        logger.info(f"Found {len(tabs)} tabs with matching IDs: {[tab.get('id') for tab in tabs]}")
        
        for tab in tabs:
            tab_id = tab.get('id')
            if tab_id not in tab_mapping:
                logger.warning(f"Tab {tab_id} has no corresponding nav link; skipping")
                continue
                
            tab_label = tab_mapping[tab_id]
            specs_table = tab.find('table', class_='specifications-table')
            if not specs_table:
                logger.warning(f"No specifications table found in {tab_id} ({tab_label})")
                continue
                
            # Extract specifications from the table
            specs_dict = {}
            rows = specs_table.find_all('tr', class_='specifications-table_row')
            logger.info(f"Found {len(rows)} rows in {tab_id} ({tab_label})")
            for row in rows:
                cols = row.find_all('td', class_='specifications-table_col')
                logger.info(f"Processing row with {len(cols)} columns in {tab_id}")
                if len(cols) == 4:
                    key1 = cols[0].get_text(strip=True).rstrip(":")
                    value1 = cols[1].get_text(strip=True)
                    key2 = cols[2].get_text(strip=True).rstrip(":")
                    value2 = cols[3].get_text(strip=True)
                    specs_dict[key1] = value1
                    specs_dict[key2] = value2
                elif len(cols) == 2:
                    key = cols[0].get_text(strip=True).rstrip(":")
                    value = cols[1].get_text(strip=True)
                    specs_dict[key] = value
                
            logger.info(f"Extracted {len(specs_dict)} items from {tab_id} ({tab_label})")
            
            # Assign to the correct category based on label
            if "technical specifications" in tab_label:
                technical_specs.update(specs_dict)
                logger.info(f"Assigned {tab_id} as Technical Specifications with {len(specs_dict)} items")
            elif "general specifications" in tab_label:
                general_specs.update(specs_dict)
                logger.info(f"Assigned {tab_id} as General Specifications with {len(specs_dict)} items")
            else:
                logger.info(f"Skipping {tab_id} ({tab_label}) as it's not Technical or General Specifications")
        
        # Log final results
        logger.info(f"Scraped {len(technical_specs)} technical specifications")
        logger.info(f"Scraped {len(general_specs)} general specifications")
        
        # Check for overlap
        tech_keys = set(technical_specs.keys())
        gen_keys = set(general_specs.keys())
        overlap = tech_keys.intersection(gen_keys)
        if overlap:
            logger.warning(f"Overlap detected between technical and general specifications: {overlap}")
        
        return {
            "product_name": product_name,
            "key_features": key_features,
            "technical_specifications": technical_specs,
            "general_specifications": general_specs
        }
    except Exception as e:
        logger.error(f"Error in async scraping: {str(e)}")
        return {
            "product_name": "Unknown Product",
            "key_features": [],
            "technical_specifications": {},
            "general_specifications": {}
        }

async def async_search_confluence(query: str, session: aiohttp.ClientSession) -> str:
    """
    Asynchronously search Confluence for content matching the query.
    
    Args:
        query (str): Search query string
        session (aiohttp.ClientSession): Active aiohttp session
        
    Returns:
        str: Combined content from matching Confluence pages
    """
    if not session or session.closed:
        logger.error("Session is invalid or closed")
        return ""
        
    try:
        logger.info(f"Starting async Confluence search for query: '{query}'")
        
        # Build request parameters
        url = f"{CONFLUENCE_BASE_URL}/rest/api/content/search"
        normalized_query = normalize_text(query)
        cql_query = f'(text ~ "{normalized_query}") AND type = page'
        params = {
            "cql": cql_query,
            "expand": "body.storage,space,version",
            "limit": 10
        }
        auth = aiohttp.BasicAuth(login=CONFLUENCE_USERNAME, password=CONFLUENCE_API_TOKEN)
        
        # Add timeout and retry logic
        timeout = aiohttp.ClientTimeout(total=30)
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async with session.get(
                    url, 
                    params=params, 
                    auth=auth, 
                    verify_ssl=False,
                    timeout=timeout
                ) as response:
                    if response.status == 429:  # Rate limit
                        retry_after = int(response.headers.get('Retry-After', retry_delay))
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    results = await response.json()
                    break  # Success, exit retry loop
                    
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    logger.warning(f"Confluence API request timed out after {max_retries} attempts")
                    return ""
                logger.warning(f"Request timeout, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                continue
                
            except aiohttp.ClientError as e:
                if attempt == max_retries - 1:
                    logger.warning(f"Confluence API request failed after {max_retries} attempts: {str(e)}")
                    return ""
                logger.warning(f"Request failed, attempt {attempt + 1}/{max_retries}: {str(e)}")
                await asyncio.sleep(retry_delay)
                continue
        
        # Process results
        pages = results.get("results", [])
        if not pages:
            logger.info(f"No Confluence pages found for query: {query}")
            return ""
            
        logger.info(f"Retrieved {len(pages)} pages from Confluence search")
        
        # Process pages in parallel
        tasks = []
        for page in pages:
            tasks.append(process_confluence_page(page))
        
        processed_contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors and combine content
        valid_contents = []
        for content in processed_contents:
            if isinstance(content, Exception):
                logger.error(f"Error processing page: {str(content)}")
                continue
            if content:
                valid_contents.append(content)
                
        combined_content = "\n\n".join(valid_contents)
        logger.info(f"Processed {len(valid_contents)} pages successfully")
        
        return combined_content
        
    except Exception as e:
        logger.error(f"Error in Confluence search: {str(e)}")
        return ""

async def process_confluence_page(page: dict) -> str:
    """Process a single Confluence page and extract relevant content."""
    try:
        page_title = page.get("title", "")
        page_space = page.get("space", {}).get("name", "")
        body = page.get("body", {}).get("storage", {}).get("value", "")
        
        if not body:
            logger.warning(f"No content found in page: {page_title}")
            return ""
            
        # Parse HTML content
        soup = BeautifulSoup(body, 'html.parser')
        
        # Remove unwanted elements
        for element in soup.find_all(['script', 'style', 'head']):
            element.decompose()
            
        # Extract text content
        text_content = soup.get_text(separator='\n', strip=True)
        
        # Format the content
        formatted_content = f"""
        Page: {page_title}
        Space: {page_space}
        Content:
        {text_content}
        """
        
        return formatted_content.strip()
        
    except Exception as e:
        logger.error(f"Error processing page {page.get('title', 'Unknown')}: {str(e)}")
        return ""

# Add this helper function to clean HTML tags before PDF generation
def clean_html_for_reportlab(text):
    """
    Clean HTML tags from text or convert them to ReportLab-compatible format.
    ReportLab's basic paragraph handling doesn't support many HTML tags.
    """
    if not text or not isinstance(text, str):
        return text
        
    # Replace <br> tags with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Remove paragraph tags but keep their content
    text = re.sub(r'<para>(.*?)</para>', r'\1', text)
    
    # Remove other HTML tags but keep their content
    text = re.sub(r'<[^>]*>', '', text)
    
    # Fix any double spaces or excessive newlines
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

# Find the generate_pdf function and update it to use this cleaning function
# Modify the format_detailed_text function to clean HTML from paragraphs
def format_detailed_text(detailed_text: str) -> List:
    flowables = []
    for line in detailed_text.split("\n"):
        line = line.strip()
        if not line:
            flowables.append(Spacer(1, 0.1 * inch))
            continue
        line = convert_markdown_to_html(line)
        # Clean HTML tags from the line
        line = clean_html_for_reportlab(line)
        if line.startswith("###"):
            text = line.lstrip("#").strip()
            flowables.append(Paragraph(text, STYLES['Heading3']))
        elif re.match(r'^\d+\.', line):
            numbered_style = ParagraphStyle('Numbered', parent=STYLES['Normal'], leftIndent=20)
            flowables.append(Paragraph(line, numbered_style))
        elif line.startswith("-"):
            text = line.lstrip("-").strip()
            flowables.append(Paragraph("• " + text, STYLES['Bullet']))
        else:
            flowables.append(Paragraph(line, STYLES['Normal']))
        flowables.append(Spacer(1, 0.05 * inch))
    return flowables

# Add this class to better handle network issues with the RAG system
class NetworkResilientRAG:
    """A wrapper for RAG functionality with improved network error handling"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2  # base seconds
        self.cached_results = {}  # Simple in-memory cache
    
    def query_with_fallback(self, query_text, retry=0):
        """Query RAG system with fallbacks for network errors"""
        # First check cache
        if query_text in self.cached_results:
            logger.info(f"Using cached results for query: '{query_text}'")
            return self.cached_results[query_text]
            
        try:
            # Try to use the Azure RAG system
            rag_system = RAGSystem()
            result = rag_system.query(query_text)
            
            # Cache successful result
            if result and 'error' not in result:
                self.cached_results[query_text] = result
            return result
        except Exception as e:
            logger.warning(f"RAG query failed (attempt {retry+1}/{self.max_retries}): {str(e)}")
            
            # Retry with exponential backoff
            if retry < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** retry)
                logger.info(f"Retrying RAG query in {wait_time} seconds...")
                time.sleep(wait_time)
                return self.query_with_fallback(query_text, retry + 1)
            
            # If all retries fail, return a graceful fallback
            logger.error(f"All RAG query attempts failed, using fallback for: '{query_text}'")
            return {
                'answer': f"I couldn't retrieve specific information about {query_text} due to connection issues. Here's some general information based on common properties of this type of product.",
                'sources': [],
                'error': str(e)
            }

# Update the retrieve_azure_blob_content function to use the resilient wrapper
def retrieve_azure_blob_content(product_query: str) -> str:
    """Retrieve content from Azure Blob Storage with improved error handling"""
    try:
        resilient_rag = NetworkResilientRAG()
        result = resilient_rag.query_with_fallback(product_query)
        
        if result and 'answer' in result:
            return result['answer']
        return ""
    except Exception as e:
        logger.error(f"Error retrieving Azure Blob content: {str(e)}")
        return ""

# Add a more robust version of the parallel_content_generation function
async def robust_content_generation(prompts: Dict[str, str], language: str, client_id: str) -> Dict[str, str]:
    """Generate content with multiple fallback strategies and better error handling"""
    max_concurrent = 2  # Limit concurrent requests to avoid overwhelming the network
    
    try:
        # First try sequential processing with fewer concurrent requests
        result_dict = {}
        batches = list(_create_batches(prompts.items(), max_concurrent))
        
        for batch_idx, batch in enumerate(batches):
            batch_size = len(batch)
            await update_progress(client_id, f"Generating content (batch {batch_idx+1}/{len(batches)})...", 70 + (batch_idx * 10 // len(batches)))
            
            # Process this batch concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                batch_futures = []
                for title, prompt in batch:
                    future = asyncio.get_event_loop().run_in_executor(
                        executor,
                        _generate_with_retry,
                        title,
                        prompt,
                        language
                    )
                    batch_futures.append(future)
                
                # Wait for all batch tasks to complete
                batch_results = await asyncio.gather(*batch_futures, return_exceptions=True)
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error in batch content generation: {str(result)}")
                        continue
                    if isinstance(result, tuple) and len(result) == 2:
                        section_title, content = result
                        if content and content.strip():
                            result_dict[section_title] = content
        
        # If we have results, return them
        if result_dict:
            return result_dict
        
        # If no results, try one-by-one with explicit delays
        logger.warning("Batch generation failed, trying sequential generation with delays")
        return await sequential_content_generation(prompts, language)
        
    except Exception as e:
        logger.error(f"Error in robust content generation: {str(e)}")
        return await sequential_content_generation(prompts, language)

def _create_batches(items, batch_size):
    """Helper to create batches of items for processing"""
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:  # yield any remaining items
        yield batch

def _generate_with_retry(section_title, prompt, language, max_retries=3):
    """Generate content with explicit retries and backoff"""
    retry_delay = 2  # base seconds
    last_error = None
    
    for attempt in range(max_retries):
        try:
            generate_content = Predict(GenerateContent)
            result = generate_content(
                section_title=section_title,
                prompt=prompt,
                language=language,
                temperature=0.3
            )
            return section_title, result.output
        except Exception as e:
            last_error = e
            logger.warning(f"Content generation for '{section_title}' failed (attempt {attempt+1}/{max_retries}): {str(e)}")
            time.sleep(retry_delay * (2 ** attempt))
    
    # If all retries fail, use fallback content generation
    logger.error(f"All content generation attempts failed for '{section_title}', using fallback")
    return section_title, _generate_fallback_content(section_title, prompt)

def _generate_fallback_content(section_title, prompt):
    """Generate fallback content when all API calls fail"""
    if "Introduction" in section_title:
        return "This section provides an introduction to the product, including its purpose and main applications."
    elif "Key Features" in section_title:
        return "This product comes with several important features designed for reliability and performance."
    elif "Technical Specifications" in section_title:
        return "This section details the technical specifications of the product, including dimensions, materials, and operating parameters."
    elif "Safety" in section_title:
        return "Important safety information for proper installation, use, and maintenance of this product."
    elif "Setup" in section_title or "Installation" in section_title:
        return "This section provides guidance on proper setup and installation procedures."
    elif "Maintenance" in section_title:
        return "Regular maintenance ensures optimal performance and longevity of your product."
    elif "Troubleshooting" in section_title:
        return "This section helps identify and resolve common issues that may occur."
    else:
        return f"Information for {section_title}."

# ---------------------------
# Playwright Setup for Web Scraping
# ---------------------------
async def scrape_with_playwright(url, wait_time=10):
    """
    Scrape the given URL using Playwright asynchronously.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to the URL
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for the page to load completely
            await asyncio.sleep(wait_time)
            
            # Extract data
            data = {}
            
            # Extract title
            try:
                h1_element = await page.query_selector('h1')
                if h1_element:
                    data['title'] = clean_html_for_reportlab(await h1_element.inner_text())
                else:
                    data['title'] = clean_html_for_reportlab(await page.title())
            except Exception as e:
                logger.warning(f"Error extracting title: {e}")
                data['title'] = clean_html_for_reportlab(await page.title())
            
            # Extract paragraphs
            try:
                paragraphs = await page.query_selector_all('p')
                content = []
                for p in paragraphs:
                    text = await p.inner_text()
                    if text.strip():
                        content.append(clean_html_for_reportlab(text))
                
                data['content'] = content
                
                # If no paragraphs found, get all visible text
                if not data.get('content'):
                    body_text = await page.evaluate('() => document.body.innerText')
                    data['content'] = [clean_html_for_reportlab(line) for line in body_text.split('\n') if line.strip()]
            except Exception as e:
                logger.warning(f"Error extracting paragraphs: {e}")
                data['content'] = []
            
            # Extract images
            try:
                images = await page.query_selector_all('img')
                image_srcs = []
                for img in images:
                    src = await img.get_attribute('src')
                    if src and src.strip():
                        image_srcs.append(src)
                data['images'] = image_srcs
            except Exception as e:
                logger.warning(f"Error extracting images: {e}")
                data['images'] = []
            
            return data
        except Exception as e:
            logger.error(f"Error scraping with Playwright: {e}")
            return None
        finally:
            await browser.close()

PRODUCTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "product_names.json")
with open(PRODUCTS_FILE_PATH, "r") as file:
    products_data = json.load(file)

@app.post("/api/motor/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: Optional[UploadFile] = File(None),
    language: str = Form(...),
    client_id: str = Form(...)
):
    try:
        logger.info(f"Starting generation for client_id: {client_id}")
        await update_progress(client_id, "Initializing document generation...", 5)

        async with aiohttp.ClientSession() as session:
            await update_progress(client_id, "Retrieving product information...", 10)
            product_link = get_product_link(product_category)
            if not product_link:
                raise HTTPException(status_code=400, detail="Product link not found")

            await update_progress(client_id, "Gathering information from sources...", 20)
            tasks = [
                async_scrape_product_data(product_link, session),
                async_search_confluence(product_category, session)
            ]
            scraped_data, confluence_content = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle potential exceptions in tasks
            if isinstance(scraped_data, Exception):
                logger.error(f"Scraping failed: {str(scraped_data)}")
                scraped_data = {
                    "product_name": "Unknown Product",
                    "key_features": [],
                    "technical_specifications": {},
                    "general_specifications": {}
                }
            if isinstance(confluence_content, Exception):
                logger.error(f"Confluence search failed: {str(confluence_content)}")
                confluence_content = ""

            cleaned_product_name = clean_product_query(scraped_data["product_name"])

            if rag_source:
                await update_progress(client_id, "Processing uploaded file...", 30)
                try:
                    await upload_to_azure_blob(rag_source)
                except Exception as e:
                    logger.error(f"Failed to upload PDF: {str(e)}")

            await update_progress(client_id, "Retrieving additional content...", 40)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(retrieve_azure_blob_content, cleaned_product_name)
                azure_blob_content = await asyncio.get_event_loop().run_in_executor(None, lambda: future.result())

            await update_progress(client_id, "Analyzing content...", 50)
            combined_content = combine_all_content(scraped_data, "", confluence_content, azure_blob_content)

            await update_progress(client_id, "Preparing content generation...", 60)
            prompts = generate_content_prompts(cleaned_product_name, combined_content, language)

            try:
                await update_progress(client_id, "Generating manual content...", 70)
                # Use our more robust content generation function
                generated_content = await robust_content_generation(prompts, language, client_id)
                if not generated_content:
                    logger.warning("No content was generated, using minimal fallback content")
                    # Create minimal fallback content for critical sections
                    generated_content = {
                        "Introduction": "Introduction to the product and its applications.",
                        "Safety Information": "Important safety guidelines for proper use.",
                        "Technical Specifications": "Product specifications and technical details."
                    }
            except ValueError as ve:
                logger.error(f"Value error in content generation: {str(ve)}")
                raise HTTPException(status_code=500, detail=str(ve))
            except Exception as e:
                logger.error(f"Unexpected error in content generation: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")

            try:
                await update_progress(client_id, "Creating PDF document...", 85)
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    pdf_buffer = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        generate_pdf,
                        {"product_category": product_category, "product_name": scraped_data["product_name"], "language": language, "scraped_data": scraped_data},
                        generated_content
                    )
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

            await update_progress(client_id, "Finalizing document...", 95)
            filename = f"user_manual_{scraped_data['product_name']}_{language}.pdf"
            encoded_filename = quote(filename)
            response = StreamingResponse(pdf_buffer, media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"

            await update_progress(client_id, "Document ready!", 100)
            return response

    except HTTPException as he:
        logger.error(f"HTTP exception in manual generation: {str(he)}")
        await update_progress(client_id, "Error occurred", 100)
        raise he
    except Exception as e:
        logger.error(f"Error in manual generation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update_progress(client_id, "Error occurred", 100)
        raise HTTPException(status_code=500, detail=f"Manual generation failed: {str(e)}")
    finally:
        active_tasks.pop(client_id, None)

@app.post("/api/motor/generate-faq")
async def generate_faq(
    product_category: str = Form(...),
    language: str = Form(...),
    preview: bool = Form(True),
    client_id: str = Form(...)
):
    try:
        logger.info(f"Starting FAQ generation for client_id: {client_id}")
        await update_progress(client_id, "Initializing FAQ generation...", 5)

        async with aiohttp.ClientSession() as session:
            await update_progress(client_id, "Retrieving product information...", 10)
            product_link = get_product_link(product_category)
            if not product_link:
                raise HTTPException(status_code=400, detail="Product link not found")

            await update_progress(client_id, "Gathering information from sources...", 20)
            tasks = [
                async_scrape_product_data(product_link, session),
                async_search_confluence(product_category, session)
            ]
            scraped_data, confluence_content = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle potential exceptions in tasks
            if isinstance(scraped_data, Exception):
                logger.error(f"Scraping failed: {str(scraped_data)}")
                scraped_data = {
                    "product_name": "Unknown Product",
                    "key_features": [],
                    "technical_specifications": {},
                    "general_specifications": {}
                }
            if isinstance(confluence_content, Exception):
                logger.error(f"Confluence search failed: {str(confluence_content)}")
                confluence_content = ""

            cleaned_product_name = clean_product_query(scraped_data["product_name"])

            await update_progress(client_id, "Retrieving additional content...", 30)
            azure_blob_content = await asyncio.get_event_loop().run_in_executor(
                None, retrieve_azure_blob_content, cleaned_product_name
            )

            language_texts = get_language_texts(language)

            try:
                await update_progress(client_id, "Analyzing data and preparing FAQ content...", 40)
                predictor = Predict(GenerateContent)
                input_data = {
                    "section_title": language_texts["faq"],
                    "prompt": f"""Generate a comprehensive FAQ section for {cleaned_product_name}.
                    Include questions and answers about:
                    - Product features and specifications
                    - Installation and setup
                    - Common usage scenarios
                    - Troubleshooting
                    - Maintenance and care
                    
                    Product Information:
                    {json.dumps(scraped_data, indent=2)}
                    
                    Additional Context:
                    {confluence_content}
                    
                    Azure Blob Storage Content:
                    {azure_blob_content}
                    """,
                    "language": language
                }
                await update_progress(client_id, "Generating FAQ content...", 60)
                result = await asyncio.to_thread(lambda: predictor(**input_data))
                if not result or not hasattr(result, 'output'):
                    logger.error("No FAQ content was generated")
                    raise HTTPException(status_code=500, detail="No FAQ content was generated")
                logger.info("FAQ content generated successfully")
            except Exception as e:
                logger.error(f"Error generating FAQ content: {str(e)}")
                raise HTTPException(status_code=500, detail=f"FAQ generation failed: {str(e)}")

            try:
                await update_progress(client_id, "Creating PDF document...", 80)
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    pdf_buffer = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        generate_pdf,
                        {"product_category": product_category, "product_name": scraped_data["product_name"], "language": language, "scraped_data": scraped_data},
                        {language_texts["faq"]: result.output},
                        True
                    )
                logger.info("PDF generated successfully")
                await update_progress(client_id, "Finalizing document...", 95)
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

            if preview:
                import base64
                pdf_bytes = pdf_buffer.getvalue()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                await update_progress(client_id, "Document ready!", 100)
                return JSONResponse({"pdf_base64": pdf_base64, "filename": f"faq_{scraped_data['product_name']}_{language}.pdf"})
            else:
                filename = f"faq_{scraped_data['product_name']}_{language}.pdf"
                response = StreamingResponse(pdf_buffer, media_type="application/pdf")
                response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
                await update_progress(client_id, "Document ready!", 100)
                return response

    except HTTPException as he:
        logger.error(f"HTTP exception in FAQ generation: {str(he)}")
        await update_progress(client_id, "Error occurred", 100)
        raise he
    except Exception as e:
        logger.error(f"Error in FAQ generation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update_progress(client_id, "Error occurred", 100)
        raise HTTPException(status_code=500, detail=f"FAQ generation failed: {str(e)}")
    finally:
        active_tasks.pop(client_id, None)

@app.get("/api/motor/products")
async def get_products():
    return JSONResponse(content={"products": products_data.get("products", [])})

@app.get("/api/motor/sseusecase2/progress/{client_id}")
async def sse_progress(client_id: str):
    logger.info(f"Starting SSE for client_id: {client_id}")
    async def event_generator():
        while True:
            if client_id not in active_tasks:
                logger.info(f"Client {client_id} not in active_tasks, sending complete")
                yield {"event": "complete", "data": json.dumps({"message": "Task completed or disconnected", "percentage": 100})}
                break
            progress = active_tasks.get(client_id, {"message": "Waiting...", "percentage": 0})
            logger.info(f"Sending progress for {client_id}: {progress}")
            yield {"event": "progress", "data": json.dumps(progress)}
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())

# Updated route to use Playwright
@app.post("/scrape")
async def scrape(data: dict):
    url = data.get('url')
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        # Call the async Playwright function
        scraped_data = await scrape_with_playwright(url)
        
        if not scraped_data:
            raise HTTPException(status_code=500, detail="Failed to scrape the URL")
        
        # Generate PDF with the scraped data
        pdf_path = generate_pdf(scraped_data)
        
        # Return the PDF or a download link
        return {"success": True, "pdf_path": pdf_path}
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)