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
    """Generate structured content for a specific section."""
    section_title: str = InputField(desc="Title of the section")
    prompt: str = InputField(desc="Prompt for generating content")
    output: str = OutputField(desc="Generated content")

def scrape_product_data(url):
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
        product_name = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Unknown Product"

        # Extract summary (if available)
        summary = soup.find('div', class_='product-summary').get_text(strip=True) if soup.find('div', class_='product-summary') else ""

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
        tech_specs_table = soup.find('div', id='tab-0').find('table', class_='specifications-table')
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
        general_specs_table = soup.find('div', id='tab-1').find('table', class_='specifications-table')
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
        raise HTTPException(status_code=500, detail="Failed to scrape product data.")

def parse_specifications(specs_text):
    """Parse the AI-generated specifications into a structured format."""
    specs_dict = {}
    for line in specs_text.split('\n'):
        line = line.strip()
        if line and ":" in line:
            key, value = line.split(":", 1)
            specs_dict[key.strip()] = value.strip()
    return specs_dict

def format_specifications_table(specs_dict):
    """Format specifications into a table-friendly structure with text wrapping."""
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=getSampleStyleSheet()["BodyText"],
        fontSize=10,
        leading=12,
        textColor=colors.black,
        wordWrap="CJK"
    )
    table_data = [["Specification", "Value"]]
    for key, value in specs_dict.items():
        wrapped_key = Paragraph(key, table_cell_style)
        wrapped_value = Paragraph(value, table_cell_style)
        table_data.append([wrapped_key, wrapped_value])
    return table_data

def generate_pdf(product_data, content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

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
        spaceAfter=12,
        alignment=1
    )
    subheading_style = ParagraphStyle(
        "CustomSubheading",
        parent=styles["Heading3"],
        fontSize=14,
        leading=16,
        textColor=colors.HexColor("#333333"),
        fontName='Helvetica-Bold',
        spaceAfter=8,
        spaceBefore=12
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=12,
        leading=14,
        textColor=colors.black
    )

    elements = []
    elements.append(Paragraph(f"USER MANUAL FOR {product_data.get('product_name', 'Unknown Product')}", title_style))
    elements.append(Spacer(1, 0.5 * inch))

    # Generate Table of Contents
    toc_data = [["Table of Contents", "Page"]]
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

    # Generate content for each section
    for section, section_content in content.items():
        elements.append(Paragraph(section.upper(), heading_style))
        if "Product Specifications" in section:
            specs_dict = parse_specifications(section_content)
            table_data = format_specifications_table(specs_dict)
            table = Table(table_data, colWidths=[200, 300])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0066CC")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))
        else:
            lines = section_content.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    line = re.sub(r'^\d+\.|\*\*|-|###|##|#', '', line).strip()
                    if ":" in line and not line.endswith(":"):
                        try:
                            subheading, text = line.split(":", 1)
                            elements.append(Paragraph(f"{subheading.strip().capitalize()}", subheading_style))
                            elements.append(Paragraph(text.strip(), body_style))
                        except ValueError:
                            elements.append(Paragraph(line, body_style))
                    else:
                        elements.append(Paragraph(line, body_style))
        elements.append(PageBreak())

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 10)
        canvas.drawRightString(200 * mm, 20, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer

def generate_content_prompts(product_data):
    product_name = product_data["product_name"]
    summary = product_data["summary"]
    key_features = product_data.get("key_features", [])
    specifications = product_data.get("specifications", {})

    # Format key features as a bullet list
    key_features_text = "\n".join([f"- {feature}" for feature in key_features])

    # Format specifications as "Category: Value"
    specs_text = "\n".join([f"{key}: {value}" for key, value in specifications.items()])

    return {
        "1. Introduction": f"Write a structured introduction for the following product: {product_name}. Summary: {summary}. Include subheadings for Product Overview and Key Features.",
        "2. Key Features": f"List the key features of the product: {product_name}. Here are some extracted features:\n{key_features_text}",
        "3. Product Specifications": f"Generate comprehensive technical specifications for: {product_name}. Summary: {summary}.\nHere are some extracted specifications:\n{specs_text}",
        "4. Safety Information": f"Provide detailed safety guidelines for: {product_name}. Summary: {summary}. Include General Warnings and Safety Precautions.",
        "5. Setup Instructions": f"Create step-by-step setup instructions for: {product_name}. Summary: {summary}. Include Installation and Configuration steps.",
        "6. Operation Instructions": f"Explain operation procedures for: {product_name}. Summary: {summary}. Include Basic Operation and Advanced Features.",
        "7. Maintenance and Care": f"Provide maintenance guidelines for: {product_name}. Summary: {summary}. Include Routine Maintenance and Cleaning Procedures.",
        "8. Troubleshooting": f"Create a troubleshooting guide for: {product_name}. Summary: {summary}. Include Common Issues and Solutions.",
        "9. FAQ": f"Generate frequently asked questions about: {product_name}. Summary: {summary}. Cover Usage, Maintenance, and Support.",
        "10. Warranty Information": f"Provide warranty details for: {product_name}. Summary: {summary}. Include Coverage Details and Claim Process."
    }

@app.post("/generate-manual")
async def generate_manual(product_data: ProductData):
    try:
        logger.info(f"Starting manual generation for {product_data.website_link}")

        # Scrape product data from the provided link
        scraped_data = scrape_product_data(product_data.website_link)

        # Use scraped data for product name, summary, and other details
        product_name = scraped_data["product_name"]
        summary = scraped_data["summary"]
        key_features = scraped_data["key_features"]
        technical_specs = scraped_data["technical_specifications"]
        general_specs = scraped_data["general_specifications"]

        # Combine technical and general specifications into a single dictionary
        all_specs = {**technical_specs, **general_specs}

        # Generate content prompts based on scraped data
        content_prompts = generate_content_prompts({
            "product_name": product_name,
            "summary": summary,
            "key_features": key_features,
            "specifications": all_specs
        })

        # Initialize the content generation process
        generate_content = Predict(GenerateContent)
        generated_content = {}
        for section, prompt in content_prompts.items():
            logger.info(f"Generating content for section: {section}")
            result = generate_content(
                section_title=section,
                prompt=prompt,
                temperature=0.7,
                max_tokens=1000
            )
            generated_content[section] = result.output
            logger.info(f"Completed content generation for section: {section}")

        # Generate the PDF
        pdf_buffer = generate_pdf({
            "product_name": product_name,
            "summary": summary,
            "key_features": key_features,
            "specifications": all_specs
        }, generated_content)

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=user_manual.pdf"}
        )
    except Exception as e:
        logger.error(f"Error generating manual: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)