import os
import logging
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField
from dspy import Example, Signature, ChainOfThought, Predict
from reportlab.lib.pagesizes import letter, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import re
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Path to the SSL certificate file
CERTIFICATE_PATH = os.path.join(os.path.dirname(__file__), "huggingface.co.crt")

# Set the environment variable for SSL verification
os.environ["REQUESTS_CA_BUNDLE"] = CERTIFICATE_PATH

# Confluence API credentials
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")  # e.g., "https://your-domain.atlassian.net/wiki"
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")  # e.g., your_email@example.com
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

# FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for input validation
class ProductData(BaseModel):
    product_category: str = Field(
        description="Category of the product (e.g., 'Electronics', 'Appliances', 'Tools')"
    )
    rag_source: UploadFile = File(None, description="Uploaded PDF file for RAG content retrieval")
    language: str = Field(
        default="en",
        description="Target language for the manual (e.g., 'en', 'es', 'fr', 'de', 'it')"
    )

# Configure DSPy with Azure OpenAI
try:
    lm = dspy.LM(
        model="azure/" + os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        temperature=0.7,
        max_tokens=4096,
    )
    dspy.configure(lm=lm)
    logger.info("DSPy configured successfully with Azure OpenAI.")
except Exception as e:
    logger.error(f"Failed to configure DSPy: {str(e)}")
    raise RuntimeError(f"Failed to configure DSPy: {str(e)}")

# Define signatures for content generation
class GenerateContent(Signature):
    """Generate structured content for a specific section in the specified language."""
    section_title: str = InputField(desc="Title of the section")
    prompt: str = InputField(desc="Prompt for generating content")
    language: str = InputField(desc="Target language for content generation")
    output: str = OutputField(desc="Generated content in specified language")

def load_translations():
    file_path = os.path.join(os.path.dirname(__file__), "translations.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Load translations once
TRANSLATIONS = load_translations()

def get_language_texts(language):
    """Return language-specific texts for UI elements."""
    # If the provided language is not found, default to English.
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])

def load_and_index_pdf(pdf_path):
    """Load PDF content and create a FAISS index for RAG."""
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} documents from PDF.")
        
        if not documents:
            logger.error("No documents found in the uploaded PDF.")
            raise HTTPException(status_code=400, detail="Uploaded PDF contains no valid text.")
        
        # Split text into smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(documents)
        
        if not texts:
            logger.error("Failed to split documents into chunks.")
            raise HTTPException(status_code=400, detail="Failed to process PDF content.")
        
        # Generate embeddings and create FAISS index
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_store = FAISS.from_documents(texts, embeddings)
        return vector_store
    except Exception as e:
        logger.error(f"Error loading and indexing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

def retrieve_content(vector_store, query):
    """Retrieve relevant content using RAG."""
    try:
        docs = vector_store.similarity_search(query, k=5)  # Retrieve top 5 matches
        
        if not docs:
            logger.warning("No relevant content found for query: %s", query)
            return "No relevant content found."
        
        # Ensure all documents have valid `page_content`
        retrieved_content = "\n".join([doc.page_content for doc in docs if hasattr(doc, 'page_content')])
        
        if not retrieved_content.strip():
            logger.warning("Retrieved content is empty for query: %s", query)
            return "No relevant content found."
        
        return retrieved_content
    except Exception as e:
        logger.error(f"Error retrieving content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")

def search_confluence(query):
    """Search Confluence for relevant pages based on a query using wildcards."""
    try:
        url = f"{CONFLUENCE_BASE_URL}/rest/api/content/search"
        # Use wildcards (*) for a broader match
        cql_query = f'(title ~ "*{query}*" OR text ~ "*{query}*") AND type = page'
        params = {
            "cql": cql_query,
            "expand": "body.storage,space,version",
            "limit": 10
        }
        auth = HTTPBasicAuth(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)
        
        logger.info(f"Searching Confluence for query: {query} with CQL: {cql_query}")
        response = requests.get(url, params=params, auth=auth, verify=False)
        response.raise_for_status()
        
        results = response.json().get("results", [])
        logger.info(f"Found {len(results)} Confluence pages matching the query")
        return results
    except Exception as e:
        logger.error(f"Error searching Confluence: {str(e)}")
        return []

def get_confluence_page_content(page_id):
    """Retrieve the content of a specific Confluence page."""
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}"
    params = {
        "expand": "body.view"
    }
    auth = HTTPBasicAuth(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)
    
    try:
        response = requests.get(url, params=params, auth=auth)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error retrieving Confluence page content: {str(e)}")
        return None

def extract_confluence_content(pages):
    """Extract and process content from Confluence pages."""
    try:
        content = []
        for page in pages:
            # Extract basic page information
            page_id = page.get("id")
            page_title = page.get("title", "")
            page_space = page.get("space", {}).get("name", "")
            
            # Get the page content
            body = page.get("body", {}).get("storage", {}).get("value", "")
            
            # Clean HTML content using BeautifulSoup
            if body:
                soup = BeautifulSoup(body, 'html.parser')
                
                # Remove unwanted elements
                for element in soup.find_all(['script', 'style']):
                    element.decompose()
                
                # Extract text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Format the content
                formatted_content = f"""
                Page: {page_title}
                Space: {page_space}
                Content:
                {text}
                """
                content.append(formatted_content)
        
        combined_content = "\n\n".join(content)
        logger.info(f"Extracted {len(combined_content)} characters from {len(pages)} Confluence pages")
        return combined_content
    except Exception as e:
        logger.error(f"Error extracting Confluence content: {str(e)}")
        return ""
    
def get_confluence_vector_store(content):
    """Create a vector store from Confluence content."""
    try:
        if not content.strip():
            return None
            
        # Split content into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.create_documents([content])
        
        if not texts:
            return None
            
        # Create embeddings and vector store
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        vector_store = FAISS.from_documents(texts, embeddings)
        
        return vector_store
    except Exception as e:
        logger.error(f"Error creating Confluence vector store: {str(e)}")
        return None

def combine_all_content(scraped_data, pdf_content, confluence_content):
    """Combine content from all sources with proper formatting."""
    combined_content = []
    
    # Add scraped data
    if scraped_data:
        combined_content.append("=== Product Information ===")
        combined_content.append(f"Product Name: {scraped_data.get('product_name', 'N/A')}")
        
        if features := scraped_data.get('key_features', []):
            combined_content.append("\nKey Features:")
            combined_content.extend([f"- {feature}" for feature in features])
            
        if tech_specs := scraped_data.get('technical_specifications', {}):
            combined_content.append("\nTechnical Specifications:")
            combined_content.extend([f"- {key}: {value}" for key, value in tech_specs.items()])
            
        if gen_specs := scraped_data.get('general_specifications', {}):
            combined_content.append("\nGeneral Specifications:")
            combined_content.extend([f"- {key}: {value}" for key, value in gen_specs.items()])
    
    # Add PDF content
    if pdf_content and pdf_content != "No relevant content found.":
        combined_content.append("\n=== Product Documentation ===")
        combined_content.append(pdf_content)
    
    # Add Confluence content
    if confluence_content and confluence_content.strip():
        combined_content.append("\n=== Additional Product Information ===")
        combined_content.append(confluence_content)
    
    return "\n\n".join(combined_content)

def generate_content_prompts(product_data, language, retrieved_content):
    """Generate language-specific prompts for each section using the retrieved content."""
    product_category = product_data["product_category"]
    language_texts = get_language_texts(language)
    
    # Language instruction template
    language_instruction = f"""
    You are a professional technical writer creating content in {language}.
    Instructions:
    1. Generate ALL content in {language} language.
    2. Maintain technical accuracy in the translation.
    3. Use an appropriate formal tone for user manuals in {language}.
    4. Preserve all technical terms and measurements.
    5. Keep the same structured format as the original.
    6. Ensure all headings and subheadings are in {language}.
    """
    
    # Append retrieved content for context
    context_text = f"\n\nRelevant context extracted from the provided sources:\n{retrieved_content}\n\n"
    
    return {
        language_texts["introduction"]: f"{language_instruction}{context_text}Task: Write a structured introduction in {language}.",
        language_texts["key_features"]: f"{language_instruction}{context_text}Task: Describe the key features in {language}.",
        language_texts["technical_specifications"]: f"{language_instruction}{context_text}Task: Present technical specifications in {language}.",
        language_texts["safety_information"]: f"{language_instruction}{context_text}Task: Create safety guidelines in {language}.",
        language_texts["setup_instructions"]: f"{language_instruction}{context_text}Task: Write setup instructions in {language}.",
        language_texts["operation_instructions"]: f"{language_instruction}{context_text}Task: Create operation guidelines in {language}.",
        language_texts["maintenance_and_care"]: f"{language_instruction}{context_text}Task: Write maintenance procedures in {language}.",
        language_texts["troubleshooting"]: f"{language_instruction}{context_text}Task: Create a troubleshooting guide in {language}.",
        language_texts["faq"]: f"{language_instruction}{context_text}Task: Generate FAQs in {language}.",
        language_texts["warranty_information"]: f"{language_instruction}{context_text}Task: Write warranty details in {language}."
    }

def clean_content(text):
    """Clean special characters and formatting from text."""
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'\[.*?\]|\{.*?\}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def clean_product_query(product_name):
    """
    Clean the product name for Confluence search.
    - If a dash exists, use the part before it.
    - Remove special characters such as ® and punctuation.
    - Replace non-alphanumeric characters with spaces.
    """
    if " - " in product_name:
        product_name = product_name.split(" - ")[0].strip()
    # Remove the ® symbol
    product_name = product_name.replace("®", "")
    # Replace any non-alphanumeric characters (except spaces) with a space
    product_name = re.sub(r'[^\w\s]', ' ', product_name)
    # Replace multiple spaces with a single space
    product_name = re.sub(r'\s+', ' ', product_name)
    return product_name.strip()

def generate_pdf(product_data, content):
    """Generate PDF document with enhanced styling and error handling."""
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
        styles = getSampleStyleSheet()
        language_texts = get_language_texts(product_data.get("language", "en"))
        elements = []
        
        # Title
        elements.append(Paragraph(
            f"{language_texts['title']} {product_data['product_category']}",
            styles['Title']
        ))
        elements.append(Spacer(1, 0.5 * inch))
        
        # Table of Contents
        elements.append(Paragraph(language_texts['toc'], styles['Heading1']))
        toc_data = [[language_texts['toc'], language_texts['page']]]
        page_number = 2
        for section in content.keys():
            clean_section = clean_content(section)
            toc_data.append([clean_section, str(page_number)])
            page_number += 1
        toc_table = Table(toc_data, colWidths=[400, 100])
        toc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 13),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('TOPPADDING', (0, 0), (-1, 0), 15),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(toc_table)
        elements.append(PageBreak())
        
        # Content sections
        for section, section_content in content.items():
            clean_section = clean_content(section)
            elements.append(Paragraph(clean_section, styles['Heading2']))
            cleaned_content = clean_content(section_content)
            paragraphs = cleaned_content.split('\n')
            for paragraph in paragraphs:
                if paragraph.strip():
                    elements.append(Paragraph(paragraph.strip(), styles['Normal']))
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(PageBreak())
        
        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )

def scrape_product_data(url):
    """Scrape product data from the given URL using requests and BeautifulSoup."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification for testing
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract product name from <h1>
        product_name = "Unknown Product"
        h1_tag = soup.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)
        logger.info(f"Scraped product name: {product_name}")

        # Extract Key Features
        key_features = []
        key_features_container = soup.find('div', class_='product-info')
        if key_features_container:
            feature_list = key_features_container.find('ul')
            if feature_list:
                features = feature_list.find_all('li')
                for feature in features:
                    key_features.append(feature.get_text(strip=True))
        logger.info(f"Scraped {len(key_features)} key features")

        # Extract Technical Specifications
        technical_specs = {}
        tech_specs_div = soup.find('div', id='tab-0')
        if tech_specs_div:
            tech_specs_table = tech_specs_div.find('table', class_='specifications-table')
            if tech_specs_table:
                for row in tech_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    # If there are exactly 4 cells, assume two key-value pairs per row
                    if len(cols) == 4:
                        key1 = cols[0].get_text(strip=True).rstrip(":")
                        value1 = cols[1].get_text(strip=True)
                        key2 = cols[2].get_text(strip=True).rstrip(":")
                        value2 = cols[3].get_text(strip=True)
                        technical_specs[key1] = value1
                        technical_specs[key2] = value2
                    # If there are 2 cells, assume a single key-value pair
                    elif len(cols) == 2:
                        key = cols[0].get_text(strip=True).rstrip(":")
                        value = cols[1].get_text(strip=True)
                        technical_specs[key] = value
        logger.info(f"Scraped {len(technical_specs)} technical specifications")

        # Extract General Specifications
        general_specs = {}
        general_specs_div = soup.find('div', id='tab-1')
        if general_specs_div:
            general_specs_table = general_specs_div.find('table', class_='specifications-table')
            if general_specs_table:
                for row in general_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    # If there are 2 cells, treat them as one key-value pair
                    if len(cols) == 2:
                        key = cols[0].get_text(strip=True).rstrip(":")
                        value = cols[1].get_text(strip=True)
                        general_specs[key] = value
                    # If there are 4 cells, process as two pairs (just in case)
                    elif len(cols) == 4:
                        key1 = cols[0].get_text(strip=True).rstrip(":")
                        value1 = cols[1].get_text(strip=True)
                        key2 = cols[2].get_text(strip=True).rstrip(":")
                        value2 = cols[3].get_text(strip=True)
                        general_specs[key1] = value1
                        general_specs[key2] = value2
        logger.info(f"Scraped {len(general_specs)} general specifications")

        return {
            "product_name": product_name,
            "key_features": key_features,
            "technical_specifications": technical_specs,
            "general_specifications": general_specs
        }
    except Exception as e:
        logger.error(f"Error scraping product data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape product data: {str(e)}")

def get_product_link(selected_item):
    """
    Look up the product link from the products JSON data based on the selected item.
    """
    for product in products_data.get("products", []):
        for subproduct in product.get("subproducts", []):
            for item in subproduct.get("sub_subproducts", []):
                if item.get("sub_subproduct_name") == selected_item:
                    return item.get("sub_subproduct_link")
    return None

# --- End of Helper Functions ---

@app.post("/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: UploadFile = File(None),
    language: str = Form(...)
):
    """Generate user manual with content from multiple sources."""
    try:
        logger.info(f"Starting manual generation for {product_category} in {language}")
        
        # Step 1: Get product data using the selected product name from the dropdown
        product_link = get_product_link(product_category)
        if not product_link:
            raise HTTPException(status_code=400, detail="Product link not found")
        
        scraped_data = scrape_product_data(product_link)
        
        # Clean the product name for querying Confluence
        cleaned_product_name = clean_product_query(scraped_data["product_name"])
        
        # Step 2: Process PDF content if available
        pdf_content = "No relevant content found."
        if rag_source:
            pdf_path = f"temp_{rag_source.filename}"
            with open(pdf_path, "wb") as buffer:
                buffer.write(await rag_source.read())
            
            vector_store = load_and_index_pdf(pdf_path)
            pdf_content = retrieve_content(vector_store, product_category)
            os.remove(pdf_path)
        
        # Step 3: Get Confluence content using the cleaned product name
        confluence_pages = search_confluence(cleaned_product_name)
        confluence_content = extract_confluence_content(confluence_pages)
        
        # Create vector store for Confluence content if available
        confluence_vector_store = None
        if confluence_content:
            confluence_vector_store = get_confluence_vector_store(confluence_content)
        
        # Step 4: Combine all content
        combined_content = combine_all_content(
            scraped_data,
            pdf_content,
            confluence_content
        )
        
        # Step 5: Generate section-specific content
        language_texts = get_language_texts(language)
        sections = [
            "introduction",
            "key_features",
            "technical_specifications",
            "safety_information",
            "setup_instructions",
            "operation_instructions",
            "maintenance_and_care",
            "troubleshooting",
            "warranty_information"
        ]
        
        generated_content = {}
        for section in sections:
            section_title = language_texts[section]
            
            # Use the cleaned product name for the section query
            section_query = f"{section_title} for {cleaned_product_name}"
            section_content = combined_content
            
            if confluence_vector_store:
                confluence_results = retrieve_content(confluence_vector_store, section_query)
                if confluence_results != "No relevant content found.":
                    section_content += f"\n\nRelevant Confluence content:\n{confluence_results}"
            
            # Generate content using DSPy
            generate_content = Predict(GenerateContent)
            result = generate_content(
                section_title=section_title,
                prompt=f"Based on this information:\n{section_content}\n\nGenerate a detailed {section_title} section in {language}.",
                language=language
            )
            
            generated_content[section_title] = result.output
        
        # Step 6: Generate PDF
        pdf_buffer = generate_pdf({
            "product_category": product_category,
            "product_name": scraped_data["product_name"],
            "language": language
        }, generated_content)
        
        # Return generated PDF
        filename = f"user_manual_{scraped_data['product_name']}_{language}.pdf"
        response = StreamingResponse(pdf_buffer, media_type="application/pdf")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"Error in manual generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
PRODUCTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "product_names.json")

# Load the JSON file with product data
with open(PRODUCTS_FILE_PATH, "r") as file:
    products_data = json.load(file)

# API endpoint to serve product data
@app.get("/api/products")
async def get_products():
    return JSONResponse(content={"products": products_data.get("products", [])})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
