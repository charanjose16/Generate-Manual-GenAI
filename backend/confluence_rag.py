import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import logging
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import re
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from openai import AzureOpenAI
import numpy as np
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import faiss
import pickle
import shutil
from dotenv import load_dotenv

# Configuration and environment setup
script_dir = os.path.dirname(os.path.abspath(__file__))
crt_path = os.path.join(script_dir, "huggingface.co.crt")
os.environ['CURL_CA_BUNDLE'] = crt_path
warnings.simplefilter('ignore', InsecureRequestWarning)

load_dotenv()

# Access environment variables
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')
CONFLUENCE_BASE_URL = os.getenv('CONFLUENCE_BASE_URL')
CONFLUENCE_USERNAME = os.getenv('CONFLUENCE_USERNAME')
CONFLUENCE_API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')

VECTOR_DB_PATH = "vector_db"

# FastAPI app initialization
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class Query(BaseModel):
    query: str

class SearchResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

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
            if isinstance(doc, dict):
                content = doc.get('page_content', '')
                metadata = doc.get('metadata', {})
            else:
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

    def process_html(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ')
        return re.sub(r'\s+', ' ', text).strip()

    def create_documents(self, content: str, metadata: Dict[str, Any]) -> List[Document]:
        chunks = self.text_splitter.split_text(content)
        return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

class RAGSystem:
    def __init__(self):
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

    def _fetch_confluence_content(self) -> List[Dict[str, Any]]:
        auth = (CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.get(
                CONFLUENCE_BASE_URL,
                auth=auth,
                headers=headers,
                verify=False
            )
            response.raise_for_status()
            
            page_data = response.json()
            return [{
                'title': page_data['title'],
                'id': page_data['id'],
                'space': page_data.get('space', {}).get('key', ''),
                'body': {'storage': {'value': page_data['body']['storage']['value']}},
                'version': {'when': page_data.get('version', {}).get('when', '')},
            }]
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching Confluence content: {str(e)}")
            return []

    def _build_index(self) -> None:
        pages = self._fetch_confluence_content()
        if not pages:
            logging.warning("No content fetched from Confluence")
            return

        all_documents = []
        all_vectors = []

        for page in pages:
            try:
                clean_text = self.document_processor.process_html(
                    page['body']['storage']['value'])
                metadata = {
                    'title': page['title'],
                    'id': page['id'],
                    'space': page['space'],
                    'modified': page['version']['when'],
                    'url': CONFLUENCE_BASE_URL
                }
                documents = self.document_processor.create_documents(
                    clean_text, metadata)

                vectors = self.embeddings.encode(
                    [doc.page_content for doc in documents])

                all_documents.extend(documents)
                all_vectors.extend(vectors)
            except Exception as e:
                logging.error(
                    f"Error processing page {page.get('title', 'unknown')}: {str(e)}")
                continue

        if all_vectors:
            vectors_np = np.array(all_vectors).astype('float32')
            self.index.add(vectors_np, all_documents)
            self.index.save()

    async def query(self, query_text: str) -> Dict[str, Any]:
        query_vector = self.embeddings.encode([query_text]).astype('float32')
        search_results = self.index.search(query_vector)    
        
        if not search_results:
            return {'answer': 'No relevant information found in Confluence.', 'sources': []}
        
        context = '\n'.join(str(result.get('content', '')) for result in search_results)
        
        response = self.llm.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a presales expert. Provide accurate, concise answers based only on the provided context from Confluence pages. Do not use any external knowledge."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
            ],
            temperature=0.7,
            max_tokens=500
        )

        seen_sources = set()
        sources = []
        for result in search_results:
            metadata = result.get('metadata', {}) if isinstance(result.get('metadata'), dict) else {}
            unique_key = metadata.get('url', metadata.get('title', ''))
            if unique_key not in seen_sources:
                source = {
                    'title': metadata.get('title', 'Untitled'),
                    'confidence': round(float(result.get('score', 0)) * 100, 2),
                    'modified': metadata.get('modified', 'Unknown'),
                    'url': metadata.get('url', '#')
                }
                sources.append(source)
                seen_sources.add(unique_key)

        return {
            'answer': response.choices[0].message.content.strip(),
            'sources': sources
        }
    
def query_confluence(query: str, page_urls: list, k: int = 5) -> str:
    """
    Fetches Confluence content from a list of REST API URLs, cleans it, and aggregates it into a single string.
    
    Parameters:
        query (str): A query string (currently not used for filtering, but can be extended).
        page_urls (list): A list of full REST API URLs for Confluence pages.
        k (int): Number of pages to consider (not used in this simple version).
    
    Returns:
        str: Aggregated plain text content from the specified Confluence pages.
    """
    aggregated_content = ""
    for url in page_urls:
        try:
            auth = (CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)
            headers = {'Content-Type': 'application/json'}
            response = requests.get(url, auth=auth, headers=headers, verify=False)
            response.raise_for_status()
            page_data = response.json()
            html_content = page_data.get('body', {}).get('storage', {}).get('value', "")
            soup = BeautifulSoup(html_content, "html.parser")
            plain_text = soup.get_text(separator="\n")
            clean_text = re.sub(r'\s+', ' ', plain_text).strip()
            aggregated_content += clean_text + "\n"
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching Confluence content from {url}: {str(e)}")
            continue

    return aggregated_content.strip()

# FastAPI endpoints
@app.post("/rebuild-index")
async def rebuild_index():
    try:
        if os.path.exists(VECTOR_DB_PATH):
            shutil.rmtree(VECTOR_DB_PATH)
        rag_system = RAGSystem()
        return {"message": "Index rebuilt successfully"}
    except Exception as e:
        logging.error(f"Error rebuilding index: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=SearchResponse)
async def handle_query(query: Query):
    try:
        rag_system = RAGSystem()
        result = await rag_system.query(query.query)
        return result
    except Exception as e:
        logging.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)