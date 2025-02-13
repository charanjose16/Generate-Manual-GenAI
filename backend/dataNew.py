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
from langchain.vectorstores import FAISS
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Path to the SSL certificate file
CERTIFICATE_PATH = os.path.join(os.path.dirname(__file__), "huggingface.co.crt")

# Set the environment variable for SSL verification
os.environ["REQUESTS_CA_BUNDLE"] = CERTIFICATE_PATH

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
    rag_source: UploadFile = File(..., description="Uploaded PDF file for RAG content retrieval")
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

def get_language_texts(language):
    """Return language-specific texts for UI elements."""
    texts = {
        "en": {
            "title": "USER MANUAL FOR",
            "toc": "Table of Contents",
            "page": "Page",
            "introduction": "Introduction",
            "key_features": "Key Features",
            "technical_specifications": "Technical Specifications",
            "safety_information": "Safety Information",
            "setup_instructions": "Setup Instructions",
            "operation_instructions": "Operation Instructions",
            "maintenance_and_care": "Maintenance and Care",
            "troubleshooting": "Troubleshooting",
            "faq": "FAQ",
            "warranty_information": "Warranty Information"
        },
        # Other languages...
        "es": {
            "title": "MANUAL DE USUARIO PARA",
            "toc": "Índice de Contenidos",
            "page": "Página",
            "introduction": "Introducción",
            "key_features": "Características Principales",
            "technical_specifications": "Especificaciones Técnicas",
            "safety_information": "Información de Seguridad",
            "setup_instructions": "Instrucciones de Configuración",
            "operation_instructions": "Instrucciones de Operación",
            "maintenance_and_care": "Mantenimiento y Cuidado",
            "troubleshooting": "Solución de Problemas",
            "faq": "Preguntas Frecuentes",
            "warranty_information": "Información de Garantía"
        },
        "fr": {
            "title": "MANUEL D'UTILISATION POUR",
            "toc": "Table des Matières",
            "page": "Page",
            "introduction": "Introduction",
            "key_features": "Caractéristiques Clés",
            "technical_specifications": "Spécifications Techniques",
            "safety_information": "Informations de Sécurité",
            "setup_instructions": "Instructions d'Installation",
            "operation_instructions": "Instructions d'Utilisation",
            "maintenance_and_care": "Maintenance et Entretien",
            "troubleshooting": "Dépannage",
            "faq": "FAQ",
            "warranty_information": "Informations sur la Garantie"
        },
        "de": {
            "title": "BENUTZERHANDBUCH FÜR",
            "toc": "Inhaltsverzeichnis",
            "page": "Seite",
            "introduction": "Einführung",
            "key_features": "Hauptmerkmale",
            "technical_specifications": "Technische Spezifikationen",
            "safety_information": "Sicherheitshinweise",
            "setup_instructions": "Einrichtungsanweisungen",
            "operation_instructions": "Betriebsanweisungen",
            "maintenance_and_care": "Wartung und Pflege",
            "troubleshooting": "Fehlerbehebung",
            "faq": "FAQ",
            "warranty_information": "Garantieinformationen"
        },
        "it": {
            "title": "MANUALE UTENTE PER",
            "toc": "Indice dei Contenuti",
            "page": "Pagina",
            "introduction": "Introduzione",
            "key_features": "Caratteristiche Principali",
            "technical_specifications": "Specifiche Tecniche",
            "safety_information": "Informazioni sulla Sicurezza",
            "setup_instructions": "Istruzioni di Installazione",
            "operation_instructions": "Istruzioni di Funzionamento",
            "maintenance_and_care": "Manutenzione e Cura",
            "troubleshooting": "Risoluzione dei Problemi",
            "faq": "FAQ",
            "warranty_information": "Informazioni sulla Garanzia"
        }
    }
    return texts.get(language, texts["en"])

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

def generate_content_prompts(product_data, language, retrieved_content):
    """
    Generate language-specific prompts for each section using the retrieved content 
    as additional context. This helps the language model generate more relevant output.
    """
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

# --- New Helper Functions for Scraping ---

def scrape_product_data(url):
    """
    Scrape product data from the given URL using requests and BeautifulSoup.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract product name
        product_name = "Unknown Product"
        h1_tag = soup.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)

        # Extract summary (if available)
        summary = ""
        summary_div = soup.find('div', class_='product-summary')
        if summary_div:
            summary = summary_div.get_text(strip=True)

        # Extract Key Features
        key_features = []
        key_features_container = soup.find('div', class_='product-info')
        if key_features_container:
            feature_list = key_features_container.find('ul')
            if feature_list:
                features = feature_list.find_all('li')
                for feature in features:
                    key_features.append(feature.get_text(strip=True))

        # Extract Technical Specifications
        technical_specs = {}
        tech_specs_div = soup.find('div', id='tab-0')
        if tech_specs_div:
            tech_specs_table = tech_specs_div.find('table', class_='specifications-table')
            if tech_specs_table:
                for row in tech_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 4:  # Two key-value pairs per row
                        key1 = cols[0].get_text(strip=True).rstrip(":")
                        value1 = cols[1].get_text(strip=True)
                        key2 = cols[2].get_text(strip=True).rstrip(":")
                        value2 = cols[3].get_text(strip=True)
                        technical_specs[key1] = value1
                        technical_specs[key2] = value2

        # Extract General Specifications
        general_specs = {}
        general_specs_div = soup.find('div', id='tab-1')
        if general_specs_div:
            general_specs_table = general_specs_div.find('table', class_='specifications-table')
            if general_specs_table:
                for row in general_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 2:  # One key-value pair per row
                        key = cols[0].get_text(strip=True).rstrip(":")
                        value = cols[1].get_text(strip=True)
                        general_specs[key] = value

        return {
            "product_name": product_name,
            "summary": summary,
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

# --- End of New Helper Functions ---

@app.post("/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: UploadFile = File(...),
    language: str = Form(...)
):
    """Generate a user manual PDF based on product category and RAG content."""
    try:
        logger.info(f"Starting manual generation for category: {product_category} in {language}")

        # --- Step 1: Scrape product data based on the selected item ---
        product_link = get_product_link(product_category)
        if not product_link:
            logger.error("Product link not found for the selected item.")
            raise HTTPException(status_code=400, detail="Product link not found for the selected item.")
        logger.info(f"Scraping product data from: {product_link}")
        scraped_data = scrape_product_data(product_link)
        # Prepare scraped context text
        scraped_context = f"Product Name: {scraped_data['product_name']}\n"
        scraped_context += f"Summary: {scraped_data['summary']}\n"
        scraped_context += f"Key Features: {', '.join(scraped_data['key_features'])}\n"
        scraped_context += "Technical Specifications:\n"
        for key, value in scraped_data['technical_specifications'].items():
            scraped_context += f" - {key}: {value}\n"
        scraped_context += "General Specifications:\n"
        for key, value in scraped_data['general_specifications'].items():
            scraped_context += f" - {key}: {value}\n"

        # --- Step 2: Process PDF if uploaded (for additional context) ---
        pdf_retrieved_content = ""
        pdf_path = None
        if rag_source:
            pdf_path = f"temp_{rag_source.filename}"
            with open(pdf_path, "wb") as buffer:
                buffer.write(await rag_source.read())
            logger.info(f"Loading and indexing PDF from path: {pdf_path}")
            vector_store = load_and_index_pdf(pdf_path)
            query = f"User manual content for {product_category}"
            logger.info(f"Retrieving PDF content for query: {query}")
            pdf_retrieved_content = retrieve_content(vector_store, query)
            # Clean up temporary file
            os.remove(pdf_path)

        # --- Step 3: Combine contexts ---
        combined_context = scraped_context
        if pdf_retrieved_content.strip() and pdf_retrieved_content != "No relevant content found.":
            combined_context += "\nRelevant context extracted from PDF:\n" + pdf_retrieved_content

        logger.info(f"Combined context for manual generation: {combined_context}")

        # --- Step 4: Generate prompts for each section ---
        content_prompts = generate_content_prompts({
            "product_category": product_category
        }, language, combined_context)
        
        # --- Step 5: Generate content using DSPy ---
        generate_content = Predict(GenerateContent)
        generated_content = {}
        for section, prompt in content_prompts.items():
            logger.info(f"Generating content for section: {section} in {language}")
            result = generate_content(
                section_title=section,
                prompt=prompt,
                language=language,
                temperature=0.7,
                max_tokens=1000
            )
            
            if not result.output.strip():
                logger.warning(f"No content generated for section: {section}")
                generated_content[section] = "No content available."
            else:
                generated_content[section] = result.output
        
        # --- Step 6: Generate PDF ---
        pdf_buffer = generate_pdf({
            "product_category": product_category,
            "language": language
        }, generated_content)
        
        filename = f"user_manual_{product_category}_{language}.pdf"
        response = StreamingResponse(pdf_buffer, media_type="application/pdf")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error generating manual: {str(e)}")
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