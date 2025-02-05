import os
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from io import BytesIO
from dotenv import load_dotenv
from openai import AzureOpenAI
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

load_dotenv()

# FastAPI app
app = FastAPI()

# Azure OpenAI Client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# Load product data from data.json
def load_product_data():
    try:
        with open("data.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {
            "product_name": "Unknown Product",
            "description": "No description available",
            "key_features": [],
            "specifications": {},
            "price": "N/A"
        }

# Function to generate content using Azure OpenAI
def generate_openai_content(section_title, prompt):
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=[
            {"role": "system", "content": f"Generate structured content for {section_title}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

# Function to generate structured PDF
def generate_pdf(product_data, content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles["Title"]
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], spaceAfter=12, fontSize=14, bold=True)
    subheading_style = ParagraphStyle("Subheading", parent=styles["Heading3"], spaceAfter=8, fontSize=12, bold=True)
    body_style = styles["BodyText"]

    elements = []

    # Title & Description
    elements.append(Paragraph(f"User Manual for {product_data.get('product_name', 'Unknown Product')}", title_style))
    elements.append(Paragraph(f"Description: {product_data.get('description', 'No description available')}", body_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Generate content for each section
    for section, prompt in content.items():
        elements.append(Paragraph(section, heading_style))  # Bold Section Title
        section_content = generate_openai_content(section, prompt)

        # Process content: remove unnecessary symbols and format
        lines = section_content.split("\n")
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            # Remove symbols like "**", "-", "###", "##", "#"
            line = line.replace("**", "").replace("-", "").replace("###", "").replace("##", "").replace("#", "")
            
            if ":" in line and not line.endswith(":"):  # Detects subheadings (e.g., "Product Overview:")
                subheading, text = line.split(":", 1)
                formatted_lines.append(Paragraph(subheading.strip(), subheading_style))  # Bold & big subheading
                formatted_lines.append(Paragraph(text.strip(), body_style))  # Normal body text
            else:
                formatted_lines.append(Paragraph(line, body_style))  # Regular body text

        elements.extend(formatted_lines)
        elements.append(Spacer(1, 0.2 * inch))  # Space between sections

    # Build the PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Define the content prompts for each section
def generate_content_prompts(product_data):
    return {
        "1. Introduction": f"Write a structured introduction for the following product: {json.dumps(product_data, indent=2)}. Ensure subheadings like 'Product Overview', 'Design and Protection' are included and clearly formatted.",
        "2. Safety Information": "Provide clear safety information for using an industrial motor drive, including warnings and precautions. Use structured subheadings like 'General Warnings' and 'Precautionary Measures'.",
        "3. Setup Instructions": "Provide step-by-step setup instructions for an industrial motor drive, covering electrical connections, mounting, and configuration. Include subheadings such as 'Unboxing', 'Installation', and 'Initial Setup'.",
        "4. Operation Instructions": "Explain how to operate an industrial motor drive, including powering up, using the keypad, and controlling preset speeds. Include subheadings like 'Powering On', 'Using the Keypad', and 'Speed Adjustments'.",
        "5. Maintenance and Care": "Describe how to maintain and care for an industrial motor drive, including routine checks and cleaning instructions. Use subheadings like 'Regular Maintenance', 'Cleaning Guidelines', and 'Storage'.",
        "6. Troubleshooting": "Create a troubleshooting guide for common issues with industrial motor drives, such as no power or error codes. Use structured subheadings like 'Common Errors' and 'Troubleshooting Steps'.",
        "7. FAQ": "List frequently asked questions about this industrial motor drive, covering power supply, speed adjustments, and warranty details. Use 'Power Supply FAQs', 'Operation FAQs', and 'Warranty FAQs' as subheadings.",
        "8. Warranty Information": "Provide warranty details, including what is covered, exclusions, and how to claim warranty support. Use subheadings like 'Coverage Details' and 'Claim Process'."
    }

# API Endpoint to generate the user manual PDF
@app.get("/generate-manual")
async def generate_manual():
    # Load product data from JSON
    product_data = load_product_data()

    # Generate prompts for each section based on the product data
    content_prompts = generate_content_prompts(product_data)

    # Generate structured PDF with Azure OpenAI content for each section
    pdf_buffer = generate_pdf(product_data, content_prompts)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=user_manual.pdf"})