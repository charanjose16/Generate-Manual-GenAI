import os
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField
from dspy import Example, Signature, ChainOfThought, Predict
from reportlab.lib.pagesizes import letter, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import re
from fastapi.middleware.cors import CORSMiddleware

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

class GenerateSpecifications(Signature):
    """Generate technical specifications for a product."""
    product_name: str = InputField(desc="Name of the product")
    product_summary: str = InputField(desc="Summary of the product")
    output: str = OutputField(desc="Generated specifications in structured format")

def parse_specifications(specs_text):
    """Parse the AI-generated specifications into a structured format."""
    specs_dict = {}
    current_category = None
    
    for line in specs_text.split('\n'):
        line = line.strip()
        if line:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                specs_dict[key] = value
    
    return specs_dict

def format_specifications_table(specs_dict):
    """Format specifications into a table-friendly structure."""
    table_data = [["Specification", "Value"]]  # Header row
    
    for key, value in specs_dict.items():
        table_data.append([key, value])
    
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

    toc_style = ParagraphStyle(
        "TOCEntry",
        parent=styles["Normal"],
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#333333"),
        fontName='Helvetica'
    )

    # Table styles
    toc_table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0066CC")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])

    spec_table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0066CC")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F0F8FF")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])

    elements = []

    # Title
    elements.append(Paragraph(f"USER MANUAL FOR {product_data.get('product_name', 'Unknown Product')}", title_style))
    elements.append(Spacer(1, 0.5 * inch))

    # Generate Table of Contents
    toc_data = [["Table of Contents", "Page"]]
    page_number = 2  # Start from page 2 since page 1 is title and TOC
    
    for section in content.keys():
        toc_data.append([section, str(page_number)])
        # Estimate one page per section (adjust if needed)
        page_number += 1

    toc_table = Table(toc_data, colWidths=[400, 100])
    toc_table.setStyle(toc_table_style)
    elements.append(toc_table)
    elements.append(PageBreak())

    # Generate content for each section
    for section, section_content in content.items():
        elements.append(Paragraph(section.upper(), heading_style))
        
        if "Product Specifications" in section:
            # Parse specifications and create table
            specs_dict = parse_specifications(section_content)
            table_data = format_specifications_table(specs_dict)
            table = Table(table_data, colWidths=[200, 300])
            table.setStyle(spec_table_style)
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))
        else:
            # Process regular content
            lines = section_content.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    line = re.sub(r'^\d+\.|\*\*|-|###|##|#', '', line).strip()
                    if ":" in line and not line.endswith(":"):
                        try:
                            subheading, text = line.split(":", 1)
                            elements.append(Paragraph(f"<b>{subheading.strip().capitalize()}</b>", subheading_style))
                            elements.append(Paragraph(text.strip(), body_style))
                        except ValueError:
                            elements.append(Paragraph(line, body_style))
                    else:
                        elements.append(Paragraph(line, body_style))
        
        elements.append(PageBreak())

    # Add page numbers
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

    return {
        "1. Introduction": f"Write a structured introduction for the following product: {product_name}. Summary: {summary}. Include subheadings for Product Overview and Key Features.",
        
        "2. Product Specifications": f"""Generate comprehensive technical specifications for: {product_name}. Summary: {summary}.
        Include the following categories with specific values (use realistic ranges based on the product type):
        - Model Number
        - Power Specifications (include both KW and HP)
        - Input/Output Specifications
        - Physical Dimensions
        - Operating Parameters
        - Compatibility Information
        Format each specification as 'Category: Value' on a new line.""",
        
        "3. Safety Information": f"Provide detailed safety guidelines for: {product_name}. Summary: {summary}. Include General Warnings and Safety Precautions.",
        
        "4. Setup Instructions": f"Create step-by-step setup instructions for: {product_name}. Summary: {summary}. Include Installation and Configuration steps.",
        
        "5. Operation Instructions": f"Explain operation procedures for: {product_name}. Summary: {summary}. Include Basic Operation and Advanced Features.",
        
        "6. Maintenance and Care": f"Provide maintenance guidelines for: {product_name}. Summary: {summary}. Include Routine Maintenance and Cleaning Procedures.",
        
        "7. Troubleshooting": f"Create a troubleshooting guide for: {product_name}. Summary: {summary}. Include Common Issues and Solutions.",
        
        "8. FAQ": f"Generate frequently asked questions about: {product_name}. Summary: {summary}. Cover Usage, Maintenance, and Support.",
        
        "9. Warranty Information": f"Provide warranty details for: {product_name}. Summary: {summary}. Include Coverage Details and Claim Process."
    }

@app.get("/generate-manual")
async def generate_manual(
    product_name: str = Query(..., description="Name of the product"),
    summary: str = Query(..., description="Brief summary of the product")
):
    try:
        logger.info(f"Starting manual generation for {product_name}")
        
        product_data = {
            "product_name": product_name,
            "summary": summary
        }
        
        content_prompts = generate_content_prompts(product_data)
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
        
        pdf_buffer = generate_pdf(product_data, generated_content)
        
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
    uvicorn.run(app, host="0.0.0.0", port=8000)