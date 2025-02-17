import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
import PyPDF2
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from openai import AzureOpenAI
import numpy as np
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import faiss
import pickle
import shutil
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient
import urllib.parse
import logging
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
crt_path = os.path.join(script_dir, "huggingface.co.crt")
os.environ['CURL_CA_BUNDLE'] = crt_path
warnings.simplefilter('ignore', InsecureRequestWarning)

load_dotenv()

# Access environment variables
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
AZURE_STORAGE_SAS_URL = os.getenv('AZURE_STORAGE_SAS_URL')

VECTOR_DB_PATH = "C:\\Users\\288040\\Desktop\\Personal Things to Learn\\Python 12\\Generate-Manual-GenAI\\backend\\vector_db"
UPLOAD_FOLDER = "C:\\Users\\288040\\Desktop\\Personal Things to Learn\\Python 12\\Generate-Manual-GenAI\\backend\\vector_db"
class FAISSIndex:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index_path = os.path.join(VECTOR_DB_PATH, "index.faiss")
        self.metadata_path = os.path.join(VECTOR_DB_PATH, "metadata.pkl")
        self.documents: List[Document] = []
        self.index: Optional[faiss.Index] = None
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)

    def create(self) -> None:
        self.index = faiss.IndexFlatL2(self.dimension)

    def add(self, vectors: np.ndarray, documents: List[Document]) -> None:
        if self.index is None:
            self.create()
        self.index.add(vectors)
        self.documents.extend(documents)

    def save(self) -> None:
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.documents, f)

    def load(self) -> bool:
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.documents = pickle.load(f)
                return True
            return False
        except Exception as e:
            logging.error(f"Error loading index: {str(e)}")
            return False

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or not self.documents:
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
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_content)
            temp_file_path = temp_file.name

        try:
            with open(temp_file_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        finally:
            os.unlink(temp_file_path)

    def create_documents(self, content: str, metadata: Dict[str, Any]) -> List[Document]:
        chunks = self.text_splitter.split_text(content)
        return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

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
        
        self.embeddings = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.index = FAISSIndex()
        self.document_processor = DocumentProcessor()
        self.llm = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self.index.load():
            self._build_index()

    def _fetch_blob_content(self) -> List[Dict[str, Any]]:
        documents = []
        blob_list = self.container_client.list_blobs()
        
        for blob in blob_list:
            if blob.name.endswith('.pdf'):
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
        
        return documents

    def _build_index(self) -> None:
        blobs = self._fetch_blob_content()
        if not blobs:
            logging.warning("No content fetched from Azure Blob Storage")
            return

        all_documents = []
        all_vectors = []

        for blob in blobs:
            try:
                clean_text = self.document_processor.process_pdf(blob['content'])
                documents = self.document_processor.create_documents(clean_text, blob['metadata'])
                vectors = self.embeddings.encode([doc.page_content for doc in documents])
                all_documents.extend(documents)
                all_vectors.extend(vectors)
            except Exception as e:
                logging.error(f"Error processing blob {blob['metadata'].get('source', 'unknown')}: {str(e)}")
                continue

        if all_vectors:
            vectors_np = np.array(all_vectors).astype('float32')
            self.index.add(vectors_np, all_documents)
            self.index.save()

    def query(self, query_text: str) -> Dict[str, Any]:
        try:
            query_vector = self.embeddings.encode([query_text]).astype('float32')
            search_results = self.index.search(query_vector)     
            
            if not search_results:
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
            
            # Keep unique sources while preserving all information
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

            return {
                'answer': response.choices[0].message.content.strip(),
                'sources': sources
            }
        except Exception as e:
            logging.error(f"Error in query processing: {str(e)}")
            return {
                'answer': 'An error occurred while processing your query.',
                'sources': [],
                'error': str(e)
            }

app = Flask(__name__)
CORS(app)

@app.route('/rebuild-index', methods=['POST'])
def rebuild_index():
    try:
        if os.path.exists(VECTOR_DB_PATH):
            shutil.rmtree(VECTOR_DB_PATH)
        rag_system = RAGSystem()
        return jsonify({'message': 'Index rebuilt successfully'}), 200
    except Exception as e:
        logging.error(f"Error rebuilding index: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/a-query', methods=['POST'])
def handle_query():
    try:
        data = request.get_json()
        query_text = data.get('query')

        if not query_text:
            return jsonify({'error': 'Query is required'}), 400

        rag_system = RAGSystem()
        result = rag_system.query(query_text)
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Error processing query: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    try:
        # Print request information for debugging
        print("Files in request:", request.files)
        print("Form data:", request.form)
        
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file part',
                'hint': 'Make sure to use form-data with key="file" in Postman'
            }), 400

        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            blob_client = rag_system.container_client.get_blob_client(filename)
            blob_client.upload_blob(file.read(), overwrite=True)
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename
            }), 200

        return jsonify({'error': 'Invalid file type. Only PDFs are allowed'}), 400
    except Exception as e:
        logging.error(f"Error uploading PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/list-pdfs', methods=['GET'])
def list_pdfs():
    try:
        rag_system = RAGSystem()
        pdf_files = []
        blob_list = rag_system.container_client.list_blobs()
        for blob in blob_list:
            if blob.name.endswith('.pdf'):
                pdf_files.append({
                    'name': blob.name,
                    'size': blob.size,
                    'created': blob.creation_time.isoformat(),
                    'modified': blob.last_modified.isoformat()
                })
        
        return jsonify({
            'pdf_files': pdf_files,
            'total_count': len(pdf_files)
        }), 200
        
    except Exception as e:
        logging.error(f"Error listing PDF files: {str(e)}")
        return jsonify({'error': str(e)}), 500  
       
def print_pdf_list():
    """Utility function to print all PDFs in storage to terminal"""
    try:
        rag_system = RAGSystem()
        print("\n=== Current PDFs in Storage ===")
        blob_list = rag_system.container_client.list_blobs()       
        pdf_count = 0
        for blob in blob_list:
            if blob.name.endswith('.pdf'):
                pdf_count += 1
                size_mb = blob.size / (1024 * 1024)
                print(f"{pdf_count}. {blob.name} ({size_mb:.2f} MB)")
                print(f"   Modified: {blob.last_modified}")
                print("---")
        
        if pdf_count == 0:
            print("No PDFs found in storage.")
        print(f"\nTotal PDFs: {pdf_count}")
        print("============================\n")
        
    except Exception as e:
        print(f"Error listing PDFs: {str(e)}")

rag_system = RAGSystem()

if __name__ == '__main__':
    print("\nInitial PDF list in storage:")
    print_pdf_list()
    app.run(host='0.0.0.0', port=5001)