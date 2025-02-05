import os
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField
from dspy import Example, Signature, ChainOfThought, Predict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI()

# Configure DSPy with Azure OpenAI
lm = dspy.LM(
    model="azure/" + os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # Specify Azure as the provider
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    temperature=0.7,
    max_tokens=4096,
)
dspy.configure(lm=lm)

# Define a signature for generating structured content
class GenerateContent(Signature):
    """Generate structured content for a specific section."""
    section_title: str = InputField(desc="Title of the section")
    prompt: str = InputField(desc="Prompt for generating content")
    output: str = OutputField(desc="Generated content")

# Function to load product data from JSON
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

# Function to generate structured PDF
def generate_pdf(product_data, content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles["Title"]
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], spaceAfter=12, fontSize=14, bold=True)
    subheading_style = ParagraphStyle("Subheading", parent=styles["Heading3"], spaceAfter=8, fontSize=12, bold=True, italics=False)
    body_style = styles["BodyText"]

    elements = []

    # Title & Description
    elements.append(Paragraph(f"USER MANUAL FOR {product_data.get('product_name', 'UNKNOWN PRODUCT')}", title_style))
    elements.append(Paragraph(f"DESCRIPTION: {product_data.get('description', 'NO DESCRIPTION AVAILABLE')}", body_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Generate content for each section
    for section, section_content in content.items():
        elements.append(PageBreak())  # Ensure each new section starts on a new page
        elements.append(Paragraph(section.upper(), heading_style))  # Convert heading to uppercase and bold

        lines = section_content.split("\n")
        formatted_lines = []

        for line in lines:
            line = line.strip()
            # Remove unwanted symbols
            line = line.replace("**", "").replace("-", "").replace("###", "").replace("##", "").replace("#", "")

            if ":" in line and not line.endswith(":"):  # Detects subheadings
                subheading, text = line.split(":", 1)
                formatted_lines.append(Paragraph(subheading.strip().capitalize(), subheading_style))  # Capitalize first letter for subheading
                formatted_lines.append(Paragraph(text.strip(), body_style))
            else:
                formatted_lines.append(Paragraph(line, body_style))

        elements.extend(formatted_lines)
        elements.append(Spacer(1, 0.2 * inch))  # Space between sections

    # Function to add page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"{page_num}"
        canvas.setFont("Helvetica", 12)
        canvas.drawCentredString(300, 30, text)  # Position at bottom center

    # Build the PDF with page numbers
    doc.build(elements, onLaterPages=add_page_number, onFirstPage=add_page_number)
    
    buffer.seek(0)
    return buffer

# Define the content prompts for each section
def generate_content_prompts(product_data):
    return {
        "1. INTRODUCTION": f"Write a structured introduction for the following product: {json.dumps(product_data, indent=2)}. Ensure subheadings like 'PRODUCT OVERVIEW', 'DESIGN AND PROTECTION' are included and clearly formatted.",
        "2. SAFETY INFORMATION": "Provide clear safety information for using an industrial motor drive, including warnings and precautions. Use structured subheadings like 'GENERAL WARNINGS' and 'PRECAUTIONARY MEASURES'.",
        "3. SETUP INSTRUCTIONS": "Provide step-by-step setup instructions for an industrial motor drive, covering electrical connections, mounting, and configuration. Include subheadings such as 'UNBOXING', 'INSTALLATION', and 'INITIAL SETUP'.",
        "4. OPERATION INSTRUCTIONS": "Explain how to operate an industrial motor drive, including powering up, using the keypad, and controlling preset speeds. Include subheadings like 'POWERING ON', 'USING THE KEYPAD', and 'SPEED ADJUSTMENTS'.",
        "5. MAINTENANCE AND CARE": "Describe how to maintain and care for an industrial motor drive, including routine checks and cleaning instructions. Use subheadings like 'REGULAR MAINTENANCE', 'CLEANING GUIDELINES', and 'STORAGE'.",
        "6. TROUBLESHOOTING": "Create a troubleshooting guide for common issues with industrial motor drives, such as no power or error codes. Use structured subheadings like 'COMMON ERRORS' and 'TROUBLESHOOTING STEPS'.",
        "7. FAQ": "List frequently asked questions about this industrial motor drive, covering power supply, speed adjustments, and warranty details. Use 'POWER SUPPLY FAQS', 'OPERATION FAQS', and 'WARRANTY FAQS' as subheadings.",
        "8. WARRANTY INFORMATION": "Provide warranty details, including what is covered, exclusions, and how to claim warranty support. Use subheadings like 'COVERAGE DETAILS' and 'CLAIM PROCESS'."
    }

# API Endpoint to generate the user manual PDF
@app.get("/generate-manual")
async def generate_manual():
    # Load product data from JSON
    product_data = load_product_data()

    # Generate prompts for each section based on the product data
    content_prompts = generate_content_prompts(product_data)

    # Use DSPy to generate content for each section
    generate_content = Predict(GenerateContent)
    generated_content = {}

    for section, prompt in content_prompts.items():
        result = generate_content(section_title=section, prompt=prompt, temperature=0.7, max_tokens=500)
        generated_content[section] = result.output

    # Generate structured PDF with DSPy-generated content for each section
    pdf_buffer = generate_pdf(product_data, generated_content)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=user_manual.pdf"})
