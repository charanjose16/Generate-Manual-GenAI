import os
import logging
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
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
        # Add other languages similarly...
    }
    return texts.get(language, texts["en"])

def load_and_index_pdf(pdf_path):
    """Load PDF content and create a FAISS index for RAG."""
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    
    # Split text into smaller chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    
    # Generate embeddings and create FAISS index
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(texts, embeddings)
    return vector_store

def retrieve_content(vector_store, query):
    """Retrieve relevant content using RAG."""
    docs = vector_store.similarity_search(query, k=5)  # Retrieve top 5 matches
    retrieved_content = "\n".join([doc.page_content for doc in docs])
    return retrieved_content

def generate_content_prompts(product_data, language, retrieved_content):
    """Generate language-specific prompts for each section."""
    product_category = product_data["product_category"]
    language_texts = get_language_texts(language)
    
    # Language instruction template
    language_instruction = f"""
    You are a professional technical writer creating content in {language}.
    Instructions:
    1. Generate ALL content in {language} language
    2. Maintain technical accuracy in the translation
    3. Use appropriate formal tone for user manuals in {language}
    4. Preserve all technical terms and measurements
    5. Keep the same structured format as the original
    6. Ensure all headings and subheadings are in {language}
    """
    
    # Generate prompts for each section using language-specific headings
    return {
        language_texts["introduction"]: f"{language_instruction}\n\nTask: Write a structured introduction in {language} for:\nProduct Category: {product_category}\nRetrieved Content: {retrieved_content}",
        language_texts["key_features"]: f"{language_instruction}\n\nTask: Describe key features in {language} for:\nProduct Category: {product_category}\nRetrieved Content: {retrieved_content}",
        language_texts["technical_specifications"]: f"{language_instruction}\n\nTask: Present technical specifications in {language} for:\nProduct Category: {product_category}\nRetrieved Content: {retrieved_content}",
        # Add other sections similarly...
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

@app.post("/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: UploadFile = File(...),
    language: str = Form(...)
):
    """Generate a user manual PDF based on product category and RAG content."""
    try:
        logger.info(f"Starting manual generation for category: {product_category} in {language}")
        
        # Save uploaded file temporarily
        pdf_path = f"temp_{rag_source.filename}"
        try:
            with open(pdf_path, "wb") as buffer:
                buffer.write(await rag_source.read())
            
            # Step 1: Load PDF and create RAG index
            vector_store = load_and_index_pdf(pdf_path)
            
            # Step 2: Retrieve relevant content using RAG
            query = f"User manual content for {product_category}"
            retrieved_content = retrieve_content(vector_store, query)
            
            # Step 3: Generate prompts for each section
            content_prompts = generate_content_prompts({
                "product_category": product_category
            }, language, retrieved_content)
            
            # Step 4: Generate content using DSPy
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
                generated_content[section] = result.output
            
            # Step 5: Generate PDF
            pdf_buffer = generate_pdf({
                "product_category": product_category,
                "language": language
            }, generated_content)
            
            # Clean up temporary file
            os.remove(pdf_path)
            
            filename = f"user_manual_{product_category}_{language}.pdf"
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    except Exception as e:
        logger.error(f"Error generating manual: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Load product data from JSON file
PRODUCTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "backend", "product_names.json")

try:
    with open(PRODUCTS_FILE_PATH, "r") as file:
        products_data = json.load(file)
except FileNotFoundError:
    logger.error(f"Products file not found at path: {PRODUCTS_FILE_PATH}")
    products_data = {"products": []}
except json.JSONDecodeError:
    logger.error(f"Failed to decode JSON from file: {PRODUCTS_FILE_PATH}")
    products_data = {"products": []}

# API endpoint to serve product data
@app.get("/api/products")
async def get_products():
    return JSONResponse(content={"products": products_data.get("products", [])})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)