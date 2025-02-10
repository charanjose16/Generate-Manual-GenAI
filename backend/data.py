import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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
import re
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

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
    website_link: str = Field(
        ...,
        description="Website link of the product",
        pattern=r"^https?://"
    )
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

def scrape_product_data(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract product name
        product_name = "Unknown Product"
        h1_tag = soup.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)

        # Extract summary
        # Extract summary (if available)
        summary = ""
        summary_div = soup.find('div', class_='product-summary')
        if summary_div:
            summary = summary_div.get_text(strip=True)

        # Extract key features
        key_features = []
        features_div = soup.find('div', class_='product-features')
        if features_div:
            for feature in features_div.find_all('li'):
                key_features.append(feature.get_text(strip=True))

        # Extract specifications
        specifications = {}
        specs_div = soup.find('div', class_='product-specifications')
        if specs_div:
            for row in specs_div.find_all('tr'):
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    specifications[key] = value
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
            "specifications": specifications
        }
    except Exception as e:
        logger.error(f"Error scraping product data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape product data: {str(e)}")

def generate_content_prompts(product_data, language):
    """Generate language-specific prompts for each section."""
    product_name = product_data["product_name"]
    summary = product_data["summary"]
    key_features = product_data.get("key_features", [])
    specifications = product_data.get("specifications", {})

    # Get language-specific texts
    language_texts = get_language_texts(language)

    # Format features and specifications
    features_text = "\n".join([f"- {feature}" for feature in key_features])
    specs_text = "\n".join([f"{key}: {value}" for key, value in specifications.items()])

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
        language_texts["introduction"]: f"{language_instruction}\n\nTask: Write a structured introduction in {language} for:\nProduct: {product_name}\nSummary: {summary}",
        language_texts["key_features"]: f"{language_instruction}\n\nTask: Describe these features in {language}:\n{features_text}",
        language_texts["technical_specifications"]: f"{language_instruction}\n\nTask: Present these specifications in {language}:\n{specs_text}",
        language_texts["safety_information"]: f"{language_instruction}\n\nTask: Create safety guidelines in {language} for: {product_name}",
        language_texts["setup_instructions"]: f"{language_instruction}\n\nTask: Write setup instructions in {language} for: {product_name}",
        language_texts["operation_instructions"]: f"{language_instruction}\n\nTask: Create operation guidelines in {language} for: {product_name}",
        language_texts["maintenance_and_care"]: f"{language_instruction}\n\nTask: Write maintenance procedures in {language} for: {product_name}",
        language_texts["troubleshooting"]: f"{language_instruction}\n\nTask: Create a troubleshooting guide in {language} for: {product_name}",
        language_texts["faq"]: f"{language_instruction}\n\nTask: Generate FAQs in {language} for: {product_name}",
        language_texts["warranty_information"]: f"{language_instruction}\n\nTask: Write warranty details in {language} for: {product_name}"
    }

def generate_technical_specifications_table(specifications, language):
    """Generate a table of technical specifications."""
    language_texts = get_language_texts(language)
    data = [[language_texts['technical_specifications'], ""]]
    for key, value in specifications.items():
        data.append([key, value])
    return data

def generate_pdf(product_data, content):
    """Generate PDF document with the manual content."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    language_texts = get_language_texts(product_data.get("language", "en"))

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#004080"),
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0066CC"),
        fontName='Helvetica-Bold',
        spaceAfter=12
    )

    subheading_style = ParagraphStyle(
        "CustomSubheading",
        parent=styles["Heading3"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0066CC"),
        fontName='Helvetica-Bold',
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=12,
        leading=14,
        textColor=colors.black,
        spaceAfter=12
    )

    elements = []

    # Title
    elements.append(Paragraph(
        f"{language_texts['title']} {product_data['product_name']}",
        title_style
    ))
    elements.append(Spacer(1, 0.5 * inch))

    # Table of Contents
    toc_data = [[language_texts['toc'], language_texts['page']]]
    page_number = 2
    for section in content.keys():
        toc_data.append([section, str(page_number)])
        page_number += 1

    toc_table = Table(toc_data, colWidths=[400, 100])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0066CC")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
    ]))
    elements.append(toc_table)
    elements.append(PageBreak())

    # Content sections
    for section, section_content in content.items():
        elements.append(Paragraph(section, heading_style))
        
        # Split content into paragraphs
        paragraphs = section_content.split('\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                elements.append(Paragraph(paragraph.strip(), body_style))
                elements.append(Spacer(1, 0.1 * inch))
        
        elements.append(PageBreak())

    # Add page numbers
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 10)
        canvas.drawRightString(
            200 * mm,
            20,
            f"{language_texts['page']} {doc.page}"
        )
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer

@app.post("/generate-manual")
async def generate_manual(product_data: ProductData):
    try:
        logger.info(f"Starting manual generation for {product_data.website_link} in {product_data.language}")

        # Scrape product data
        scraped_data = scrape_product_data(product_data.website_link)

        # Generate content prompts
        content_prompts = generate_content_prompts(scraped_data, product_data.language)

        # Generate content
        generate_content = Predict(GenerateContent)
        generated_content = {}

        for section, prompt in content_prompts.items():
            logger.info(f"Generating content for section: {section} in {product_data.language}")
            result = generate_content(
                section_title=section,
                prompt=prompt,
                language=product_data.language,
                temperature=0.7,
                max_tokens=1000
            )
            generated_content[section] = result.output

        # Generate PDF
        pdf_buffer = generate_pdf({
            **scraped_data,
            "language": product_data.language
        }, generated_content)

        filename = f"user_manual_{product_data.language}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error generating manual: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)