import logging
import requests
import os
import traceback
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField, Signature, Predict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,Frame,PageTemplate
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import re
from fastapi.middleware.cors import CORSMiddleware
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
from requests.auth import HTTPBasicAuth
import urllib3
import tempfile
import PyPDF2
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import faiss
import pickle
import shutil
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient
import urllib.parse
from datetime import datetime
from docx2pdf import convert
from fpdf import FPDF
import asyncio
import concurrent.futures
from functools import partial, lru_cache
import aiohttp
from aiohttp import  BasicAuth,ClientTimeout
from urllib.parse import quote
import win32com.client  # For handling .doc files
import pythoncom  # For COM initialization

# Disable warnings and configure logging
urllib3.disable_warnings()
warnings.simplefilter('ignore', InsecureRequestWarning)

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
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_store = FAISS.from_documents(texts, embeddings)
        return vector_store
    except Exception as e:
        logger.error(f"Error creating Confluence vector store: {str(e)}")
        return None

# -------------------------------
# AZURE BLOB STORAGE INTEGRATION
# -------------------------------
# These classes/functions come from your Azure Blob Storage code with added logging.
class FAISSIndex:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index_path = os.path.join(VECTOR_DB_PATH, "index.faiss")
        self.metadata_path = os.path.join(VECTOR_DB_PATH, "metadata.pkl")
        self.documents: List = []
        self.index: Optional[faiss.Index] = None
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)

    def create(self) -> None:
        self.index = faiss.IndexFlatL2(self.dimension)
        logger.info("Created new FAISS index.")

    def add(self, vectors: np.ndarray, documents: List) -> None:
        if self.index is None:
            self.create()
        self.index.add(vectors)
        self.documents.extend(documents)
        logger.info(f"Added {len(documents)} documents to the FAISS index.")

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
                logger.info("FAISS index and metadata loaded successfully.")
                return True
            logger.info("No existing FAISS index found.")
            return False
        except Exception as e:
            logger.error(f"Error loading FAISS index: {str(e)}")
            return False

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or not self.documents:
            logger.warning("FAISS index is empty or not loaded.")
            return []
        distances, indices = self.index.search(query_vector.reshape(1, -1), k)
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
            # Create a temporary file to handle the PDF content
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_content)
                temp_file_path = temp_file.name

            # Process the PDF
            with open(temp_file_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            logger.info("Processed PDF content successfully.")
            return text
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return ""  # Return empty string instead of None

    def create_documents(self, content: str, metadata: Dict[str, Any]) -> List:
        if not content:  # Handle empty content gracefully
            logger.warning("Empty content provided for document creation")
            return []
            
        chunks = self.text_splitter.split_text(content)
        logger.info(f"Split content into {len(chunks)} document chunks.")
        return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

# A simple Document class (mimicking LangChain's Document)
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
        self.embeddings = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
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
        if not self.index.load():
            logger.info("Building new FAISS index from Azure Blob PDFs.")
            self._build_index()

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
                vectors = self.embeddings.encode([doc.page_content for doc in documents])
                all_documents.extend(documents)
                all_vectors.extend(vectors)
            except Exception as e:
                logger.error(f"Error processing blob {blob['metadata'].get('source', 'unknown')}: {str(e)}")
                continue

        if all_vectors:
            vectors_np = np.array(all_vectors).astype('float32')
            self.index.add(vectors_np, all_documents)
            self.index.save()
            logger.info("Azure Blob Storage index built successfully.")

    def query(self, query_text: str) -> Dict[str, Any]:
        try:
            logger.info(f"Querying Azure Blob Storage with: {query_text}")
            query_vector = self.embeddings.encode([query_text]).astype('float32')
            search_results = self.index.search(query_vector)
            if not search_results:
                logger.info("No relevant results found in Azure Blob Storage.")
                return {'answer': 'No relevant information found.', 'sources': []}
            context = '\n'.join(str(result['content']) for result in search_results)
            response = self.llm.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a presales expert. Provide accurate, concise answers based only on the provided context from Azure Blob Storage PDFs. Do not use any external knowledge."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
                ],
                temperature=0.7,
                max_tokens=500
            )
            seen_sources = set()
            sources = []
            for result in search_results:
                source_title = str(result['metadata'].get('source', 'Unknown'))
                if source_title not in seen_sources:
                    source = {
                        'title': source_title,
                        'confidence': round(float(result['score']) * 100, 2),
                        'modified': result['metadata'].get('modified', 'Unknown')
                    }
                    sources.append(source)
                    seen_sources.add(source_title)
            logger.info("Azure Blob Storage query processed successfully.")
            return {
                'answer': response.choices[0].message.content.strip(),
                'sources': sources
            }
        except Exception as e:
            logger.error(f"Error in Azure Blob query processing: {str(e)}")
            return {
                'answer': 'An error occurred while processing your query.',
                'sources': [],
                'error': str(e)
            }

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
            
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            temp_doc_path = os.path.join(temp_dir, f"document{file_extension}")
            temp_pdf_path = os.path.join(temp_dir, "document.pdf")
            
            # Write the document file to disk
            with open(temp_doc_path, 'wb') as f:
                f.write(content)
                
            logger.info(f"Created temporary file at {temp_doc_path}")
            
            # Initialize COM in a separate thread
            pythoncom.CoInitialize()
            success = False
            
            try:
                logger.info("Creating Word application instance")
                word = win32com.client.DispatchEx('Word.Application')
                word.Visible = False
                word.DisplayAlerts = 0
                
                try:
                    # Use absolute paths
                    abs_doc_path = os.path.abspath(temp_doc_path)
                    abs_pdf_path = os.path.abspath(temp_pdf_path)
                    
                    logger.info(f"Opening document from {abs_doc_path}")
                    doc = word.Documents.Open(abs_doc_path, ReadOnly=1)
                    
                    logger.info(f"Saving as PDF to {abs_pdf_path}")
                    doc.SaveAs(abs_pdf_path, FileFormat=17)  # 17 = wdFormatPDF
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
                    if "RPC_E_SERVERCALL_RETRYLATER" in str(e):
                        logger.error("RPC server busy - Word might be running in non-interactive mode")
                    elif "Call was rejected by callee" in str(e):
                        logger.error("COM call rejected - could be security settings or privileges")
                
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
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        def add_page_number(canvas, doc):
            canvas.saveState()
            page_num = canvas.getPageNumber()
            text = f"Page {page_num}"
            canvas.setFont('Helvetica', 10)
            canvas.drawCentredString(doc.pagesize[0] / 2, 36, text)
            logger.info(f"Drawing page number {page_num} at y=36")
            canvas.restoreState()

        frame = Frame(
            doc.leftMargin,
            doc.bottomMargin + 40,
            doc.width,
            doc.height - 40,
            id='normal'
        )

        template = PageTemplate(id='page_template', frames=[frame], onPage=add_page_number)
        doc.addPageTemplates([template])
        
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
        
        elements.append(Spacer(1, inch))
        elements.append(Paragraph(language_texts['table_of_contents'], heading1_style))
        
        section_starts = {}
        current_page = 2
        
        for section, section_content in content.items():
            section_starts[section] = current_page
            paragraphs = clean_content(section_content).split('\n')
            estimated_lines = len(paragraphs) * 2
            current_page += max(1, estimated_lines // 40)
        
        toc_data = [[language_texts['section'], language_texts['page']]]
        for section in content.keys():
            clean_section = clean_content(section)
            page_num = section_starts.get(section, "")
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
            elements.append(Paragraph(clean_section, heading1_style))
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
        
        # The key fix: explicitly specifying onFirstPage and onLaterPages
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
        
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
            
            data = [[language_texts["specification"], language_texts["value"]]]
            for key, value in tech_specs.items():
                data.append([str(key), str(value) if value is not None else "N/A"])
            
            if len(data) > 1:
                table = Table(data, colWidths=[250, 250])
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
            
            data = [[language_texts["specification"], language_texts["value"]]]
            for key, value in gen_specs.items():
                data.append([str(key), str(value) if value is not None else "N/A"])
            
            if len(data) > 1:
                table = Table(data, colWidths=[250, 250])
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
        # Create a ThreadPoolExecutor instead of ProcessPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
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
            for result in completed_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in content generation: {str(result)}")
                    continue
                if isinstance(result, tuple) and len(result) == 2:
                    section_title, content = result
                    if content and content.strip():  # Only add non-empty content
                        result_dict[section_title] = content
            
            if not result_dict:
                logger.error("No content was generated successfully")
                raise ValueError("Failed to generate any content")
                
            return result_dict

    except Exception as e:
        logger.error(f"Error in parallel content generation: {str(e)}")
        raise ValueError(f"Content generation failed: {str(e)}")

# Modified generate_manual endpoint
@app.post("/api/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: Optional[UploadFile] = File(None),
    language: str = Form(...)
):
    try:
        # Enable tracemalloc for debugging
        import tracemalloc
        tracemalloc.start()
        
        async with aiohttp.ClientSession() as session:
            # Parallel execution of initial data gathering
            product_link = get_product_link(product_category)
            if not product_link:
                raise HTTPException(status_code=400, detail="Product link not found")

            # Create tasks for parallel execution
            tasks = [
                async_scrape_product_data(product_link, session),
                async_search_confluence(product_category, session)
            ]

            # Execute tasks concurrently
            scraped_data, confluence_content = await asyncio.gather(*tasks)
            cleaned_product_name = clean_product_query(scraped_data["product_name"])

            # Handle RAG source upload if provided
            if rag_source:
                upload_task = asyncio.create_task(upload_to_azure_blob(rag_source))
                try:
                    await upload_task
                except Exception as e:
                    logger.error(f"Failed to upload PDF: {str(e)}")

            # Parallel processing of vector stores and content retrieval
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_tasks = []
                
                # Create vector store for Confluence content
                if confluence_content:
                    future_tasks.append(
                        executor.submit(get_confluence_vector_store, confluence_content)
                    )

                # Get Azure Blob Storage content
                future_tasks.append(
                    executor.submit(retrieve_azure_blob_content, cleaned_product_name)
                )

                # Wait for all tasks to complete
                results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    concurrent.futures.wait,
                    future_tasks
                )
                
                # Extract results
                confluence_vector_store = results.done.pop().result() if confluence_content else None
                azure_blob_content = results.done.pop().result()

            # Combine all content sources
            combined_content = combine_all_content(
                scraped_data,
                "",
                confluence_content,
                azure_blob_content
            )

            # Generate content prompts
            prompts = generate_content_prompts(cleaned_product_name, combined_content, language)

            # Generate content with better error handling
            try:
                generated_content = await parallel_content_generation(prompts, language)
                if not generated_content:
                    raise HTTPException(
                        status_code=500,
                        detail="No content was generated successfully"
                    )
            except ValueError as ve:
                raise HTTPException(
                    status_code=500,
                    detail=str(ve)
                )
            except Exception as e:
                logger.error(f"Unexpected error in content generation: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Content generation failed: {str(e)}"
                )

            # Generate PDF with error handling
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    pdf_buffer = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        generate_pdf,
                        {
                            "product_category": product_category,
                            "product_name": scraped_data["product_name"],
                            "language": language,
                            "scraped_data": scraped_data
                        },
                        generated_content
                    )
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate PDF: {str(e)}"
                )

            # Prepare response with URL-encoded filename using filename*
            filename = f"user_manual_{scraped_data['product_name']}_{language}.pdf"
            encoded_filename = quote(filename)  # URL-encode the filename to handle special characters
            response = StreamingResponse(pdf_buffer, media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"

            # Stop tracemalloc
            tracemalloc.stop()
            
            return response

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in manual generation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Manual generation failed: {str(e)}"
        )

@app.post("/api/generate-faq")
async def generate_faq(
    product_category: str = Form(...),
    language: str = Form(...),
    preview: bool = Form(True)  # New parameter
):
    try:
        logger.info(f"Starting FAQ generation for {product_category} in {language}")
        
        async with aiohttp.ClientSession() as session:
            # Get product link
            product_link = get_product_link(product_category)
            if not product_link:
                raise HTTPException(status_code=400, detail="Product link not found")
            
            # Create tasks for parallel execution
            tasks = [
                async_scrape_product_data(product_link, session),
                async_search_confluence(product_category, session)
            ]
            
            # Execute tasks concurrently
            scraped_data, confluence_content = await asyncio.gather(*tasks)
            cleaned_product_name = clean_product_query(scraped_data["product_name"])
            
            # Retrieve Azure Blob content
            azure_blob_content = await asyncio.get_event_loop().run_in_executor(
                None,
                retrieve_azure_blob_content,
                cleaned_product_name
            )
            
            # Get language texts
            language_texts = get_language_texts(language)
            
            # Generate FAQ content asynchronously
            try:
                # Create predictor instance
                predictor = Predict(GenerateContent)
                
                # Prepare input for GenerateContent
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
                
                # Generate content
                result = await asyncio.to_thread(
                    lambda: predictor(
                        section_title=input_data["section_title"],
                        prompt=input_data["prompt"],
                        language=input_data["language"]
                    )
                )
                
                if not result or not hasattr(result, 'output'):
                    raise HTTPException(
                        status_code=500,
                        detail="No FAQ content was generated"
                    )
                
                logger.info("FAQ content generated successfully")
                
            except Exception as e:
                logger.error(f"Error generating FAQ content: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"FAQ generation failed: {str(e)}"
                )
            
            # Generate PDF with error handling
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    pdf_buffer = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        generate_pdf,
                        {
                            "product_category": product_category,
                            "product_name": scraped_data["product_name"],
                            "language": language,
                            "scraped_data": scraped_data
                        },
                        {language_texts["faq"]: result.output},
                        True  # is_faq=True
                    )
                    
                logger.info("PDF generated successfully")
                
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate PDF: {str(e)}"
                )
            
            # Convert PDF to base64 if preview is requested
            if preview:
                import base64
                pdf_bytes = pdf_buffer.getvalue()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                return JSONResponse({
                    "pdf_base64": pdf_base64,
                    "filename": f"faq_{scraped_data['product_name']}_{language}.pdf"
                })
            else:
                # Direct download response
                filename = f"faq_{scraped_data['product_name']}_{language}.pdf"
                response = StreamingResponse(pdf_buffer, media_type="application/pdf")
                response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
            
    except Exception as e:
        logger.error(f"Error in FAQ generation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

PRODUCTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "product_names.json")
with open(PRODUCTS_FILE_PATH, "r") as file:
    products_data = json.load(file)

@app.get("/api/products")
async def get_products():
    return JSONResponse(content={"products": products_data.get("products", [])})

# Add these async functions
async def async_scrape_product_data(url: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    """Async version of scrape_product_data with explicit tab label mapping and robust tab detection"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        
        timeout = ClientTimeout(total=30)
        async with session.get(url, headers=headers, verify_ssl=False, timeout=timeout) as response:
            response.raise_for_status()
            content = await response.text()
            
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
                logger.info(f"Skipping {tab_id} ({tab_label}) as it’s not Technical or General Specifications")
        
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
        raise HTTPException(status_code=500, detail=f"Failed to scrape product data: {str(e)}")

async def async_search_confluence(query: str, session: aiohttp.ClientSession) -> str:
    """
    Asynchronously search Confluence for content matching the query.
    
    Args:
        query (str): Search query string
        session (aiohttp.ClientSession): Active aiohttp session
        
    Returns:
        str: Combined content from matching Confluence pages
        
    Raises:
        HTTPException: If API request fails or content processing fails
    """
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
                    raise HTTPException(
                        status_code=504,
                        detail="Confluence API request timed out"
                    )
                logger.warning(f"Request timeout, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                continue
                
            except aiohttp.ClientError as e:
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Confluence API request failed: {str(e)}"
                    )
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
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Confluence search failed: {str(e)}"
        )

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)