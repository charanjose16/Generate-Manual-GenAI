import os
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField
from dspy import Example, Signature, ChainOfThought, Predict
from reportlab.lib.pagesizes import letter, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI()

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
except Exception as e:
    raise RuntimeError(f"Failed to configure DSPy: {str(e)}")

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
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in data.json: {str(e)}")

def generate_pdf(product_data, content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles["Title"]
    title_style.fontName = 'Helvetica-Bold'
    title_style.fontSize = 18
    title_style.leading = 22  # Line spacing for title

    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], spaceAfter=8, fontSize=16, bold=True, alignment=1)
    heading_style.fontName = 'Helvetica-Bold'
    heading_style.leading = 18  # Line spacing for headings
    heading_style.textColor = "black"

    subheading_style = ParagraphStyle("Subheading", parent=styles["Heading3"], spaceAfter=6, fontSize=12, bold=True, italic=True, alignment=0)
    subheading_style.fontName = 'Helvetica-Bold'
    subheading_style.leading = 14  # Line spacing for subheadings

    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 12  # Line spacing for body text

    index_style = ParagraphStyle("Index", parent=styles["BodyText"], spaceAfter=6, fontSize=12, alignment=0)
    index_style.fontName = 'Helvetica'
    index_style.leading = 12  # Line spacing for index

    elements = []

    # Title & Description
    elements.append(Paragraph(f"USER MANUAL FOR {product_data.get('product_name', 'Leeson SM2 Vector NEMA 1 AC Drives')}", title_style))
    elements.append(Spacer(1, 0.3 * inch))
 

    # Index with Main Topics Only (No Subtopics)
    elements.append(Paragraph("INDEX", heading_style))
    elements.append(Spacer(1, 0.1 * inch))

    for section, section_content in content.items():
        # Only add main topics (No subtopics or section numbering)
        elements.append(Paragraph(section.split('.')[0] + ". " + section.split(' ', 1)[1], index_style))  # Add main section (without subtopic numbering)

    elements.append(PageBreak())  # Start content on a new page after the index

    # Generate content for each section (Remove subtopic numbering and only bold+italicize subtopics)
    for section, section_content in content.items():
        elements.append(Paragraph(section.upper(), heading_style))  # Uppercase Section Title
        lines = section_content.split("\n")
        formatted_lines = []
        subheading_counter = 1  # Counter for subtopics within each section

        for line in lines:
            line = line.strip()
            # Remove symbols like "**", "-", "###", "##", "#", and remove any numbering
            line = line.replace("**", "").replace("-", "").replace("###", "").replace("##", "").replace("#", "")
            # Remove any leading numbers that might have been incorrectly added
            line = re.sub(r'^\d+\.', '', line).strip()  # This will remove any numbers like "1.", "2.", etc.

            if ":" in line and not line.endswith(":"):  # Detect subtopics
                try:
                    subheading, text = line.split(":", 1)
                    # Remove subtopic numbering and keep only the subheading text
                    formatted_subheading = f"{subheading.strip().lower().capitalize()}"
                    formatted_lines.append(Paragraph(formatted_subheading, subheading_style))  # Bold & Italicized subtopic
                    formatted_lines.append(Paragraph(text.strip(), body_style))  # Normal body text
                except ValueError:
                    formatted_lines.append(Paragraph(line, body_style))  # In case of split failure
            else:
                formatted_lines.append(Paragraph(line, body_style))  # Regular body text
        elements.extend(formatted_lines)
        elements.append(PageBreak())  # Start each section on a new page

    # Add page numbers
    def add_page_number(canvas, doc):
        canvas.drawRightString(200 * mm, 20, f"{doc.page}")  # Page number only, no "Page" text
    
    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

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
    try:
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

        # Stream the PDF back to the client
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=user_manual.pdf"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
