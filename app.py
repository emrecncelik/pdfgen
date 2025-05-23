import streamlit as st
import io
import os
import tempfile
import zipfile
import base64
import uuid
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# For PDF to image conversion (deployment-friendly preview)
from pdf2image import convert_from_bytes
from PIL import Image

st.set_page_config(page_title="Certificate Generator", layout="wide")
st.title("Certificate Generator")

# Initialize session state for font tracking
if "name_font_id" not in st.session_state:
    st.session_state.name_font_id = None
if "text_font_id" not in st.session_state:
    st.session_state.text_font_id = None
if "name_font_file_hash" not in st.session_state:
    st.session_state.name_font_file_hash = None
if "text_font_file_hash" not in st.session_state:
    st.session_state.text_font_file_hash = None
if "template_dimensions" not in st.session_state:
    st.session_state.template_dimensions = (841.89, 595.276)  # Default A4 landscape


# Function to detect PDF dimensions
def detect_pdf_dimensions(pdf_file):
    """Detect the width and height of the uploaded PDF template."""
    if pdf_file is None:
        return st.session_state.template_dimensions  # Return default dimensions

    try:
        pdf = PdfReader(io.BytesIO(pdf_file.getvalue()))
        if len(pdf.pages) > 0:
            # Get the first page
            page = pdf.pages[0]
            # Extract media box dimensions (in points)
            media_box = page.mediabox
            width = float(media_box.width)
            height = float(media_box.height)
            # Store in session state
            st.session_state.template_dimensions = (width, height)
            return width, height
    except Exception as e:
        st.warning(f"Could not detect PDF dimensions: {e}")

    return st.session_state.template_dimensions


# Main form for inputs at the top
template_col1, template_col2 = st.columns(2)

with template_col1:
    template_file = st.file_uploader("Upload PDF Template", type=["pdf"])

    # Detect dimensions when template is uploaded
    if template_file:
        pdf_width, pdf_height = detect_pdf_dimensions(template_file)
        st.success(
            f"Template dimensions detected: {pdf_width:.2f} × {pdf_height:.2f} points"
        )

# Sidebar for configuration
with st.sidebar:
    st.header("PDF Settings")

    # Use detected dimensions from session state
    pdf_width, pdf_height = st.session_state.template_dimensions

    page_width = st.number_input("Page Width", value=pdf_width, step=10.0)
    page_height = st.number_input("Page Height", value=pdf_height, step=10.0)

    # Button to reset dimensions to detected values
    if st.button("Reset to Detected Dimensions"):
        page_width = pdf_width
        page_height = pdf_height

    st.header("Coordinates & Font Sizes")
    col1, col2 = st.columns(2)
    with col1:
        name_x = st.number_input("Name X", value=page_width / 2, step=10.0)
        desc_x = st.number_input("Description X", value=page_width / 2, step=10.0)
        date_x = st.number_input("Date X", value=page_width - 120, step=10.0)
    with col2:
        name_y = st.number_input("Name Y", value=page_height / 2 + 30, step=10.0)
        desc_y = st.number_input("Description Y", value=page_height / 2 - 80, step=10.0)
        date_y = st.number_input("Date Y", value=62.0, step=10.0)

    name_font_size = st.number_input("Name Font Size", value=42, step=1)
    desc_font_size = st.number_input("Description Font Size", value=14, step=1)
    date_font_size = st.number_input("Date Font Size", value=14, step=1)

    desc_max_width = st.number_input("Description Max Width", value=550, step=10)


# Function to display PDF (image-based for deployment compatibility)
def display_pdf(pdf_bytes):
    """Display the PDF as an image for better compatibility with Streamlit deployment."""
    try:
        # Try to convert the first page of the PDF to an image
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
        if images:
            st.image(images[0], caption="Certificate Preview", use_column_width=True)
            return True
    except Exception as e:
        st.warning(
            f"Could not generate preview image. Using download option instead. Error: {str(e)}"
        )
        return False

    # Fallback: Try iframe method (works locally but may not work in deployment)
    try:
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        return True
    except:
        return False


# Helper function to get file hash for checking if it's changed
def get_file_hash(file):
    if file is None:
        return None
    return hash(file.getvalue())


# Functions for certificate generation
def register_uploaded_font(font_file, font_type="name"):
    """Register uploaded font with a unique identifier and return font name."""
    if font_file is None:
        return "Helvetica"

    # Calculate hash to detect changes
    file_hash = get_file_hash(font_file)

    # Check if the font has changed
    if font_type == "name":
        if file_hash == st.session_state.name_font_file_hash:
            return (
                st.session_state.name_font_id
            )  # Return existing font id if not changed
        st.session_state.name_font_file_hash = file_hash
    else:  # text font
        if file_hash == st.session_state.text_font_file_hash:
            return (
                st.session_state.text_font_id
            )  # Return existing font id if not changed
        st.session_state.text_font_file_hash = file_hash

    # Create a unique font identifier
    font_id = f"{font_type}_font_{uuid.uuid4().hex[:8]}"

    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, font_file.name)

    # Save the uploaded font to the temporary file
    with open(temp_path, "wb") as f:
        f.write(font_file.getvalue())

    # Register the font with the unique identifier
    pdfmetrics.registerFont(TTFont(font_id, temp_path))

    # Update session state with new font ID
    if font_type == "name":
        st.session_state.name_font_id = font_id
    else:
        st.session_state.text_font_id = font_id

    return font_id


def get_names():
    """Extract names from the text input."""
    return [name.strip() for name in names_text.splitlines() if name.strip()]


def add_name(c, name, coord, font_name, font_size):
    """Add the name centered at the specified coordinate on the canvas."""
    c.setFont(font_name, font_size)
    c.drawCentredString(coord[0], coord[1], name)


def add_description(c, description, coord, font_name, font_size, max_width=550):
    """Add a centered, wrapped paragraph to the canvas using Platypus."""
    style = ParagraphStyle(
        name="Center",
        fontName=font_name,
        fontSize=font_size,
        alignment=TA_CENTER,
        leading=font_size * 1.3,
    )

    para = Paragraph(description, style)
    width, height = para.wrap(max_width, 1000)
    x = coord[0] - width / 2
    y = coord[1] - height / 2
    para.drawOn(c, x, y)


def add_date(c, date_str, coord, font_name, font_size):
    """Add the date centered at the specified coordinate."""
    c.setFont(font_name, font_size)
    c.drawCentredString(coord[0], coord[1], date_str)


def merge_overlay(template_page, overlay_page):
    """Merge the overlay page onto the template page."""
    template_page.merge_page(overlay_page)
    return template_page


def process_certificate(template_pdf, name, description, date, name_font, text_font):
    """Process a single certificate and return the PDF bytes."""
    # Create a fresh reader copy for each certificate to avoid overlapping content
    template_pdf_copy = PdfReader(io.BytesIO(template_file.getvalue()))
    template_page = template_pdf_copy.pages[0]

    # Create an in-memory overlay canvas
    packet = io.BytesIO()
    overlay_canvas = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Add components to the overlay
    add_name(overlay_canvas, name, (name_x, name_y), name_font, name_font_size)
    add_description(
        overlay_canvas,
        description,
        (desc_x, desc_y),
        text_font,
        desc_font_size,
        desc_max_width,
    )
    add_date(overlay_canvas, date, (date_x, date_y), text_font, date_font_size)

    # Finalize the canvas
    overlay_canvas.showPage()
    overlay_canvas.save()

    # Move back to the beginning of the BytesIO stream
    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    overlay_page = overlay_pdf.pages[0]

    # Merge the overlay with the template
    merge_overlay(template_page, overlay_page)

    # Create output PDF
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(template_page)
    writer.write(output)
    output.seek(0)

    return output


# Continue with the rest of the form
with template_col2:
    name_font_file = st.file_uploader("Upload Name Font (TTF)", type=["ttf"])
    text_font_file = st.file_uploader("Upload Text Font (TTF)", type=["ttf"])

# Main form for inputs
with st.form("certificate_form"):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Names & Content")
        names_text = st.text_area("Enter names (one per line)")
        date_text = st.text_input("Certificate Date", "14 April 2025")

    with col2:
        st.subheader("Certificate Description")
        description_text = st.text_area(
            "Enter description text",
            "This certificate is presented to recognize the successful completion of the program.",
        )

    submit_button = st.form_submit_button("Generate Certificates")

# Create a preview section
st.subheader("Certificate Preview")
preview_container = st.container()

# Preview certificate button
if st.button("Preview Certificate"):
    if template_file is None:
        st.error("Please upload a PDF template file.")
    elif not names_text.strip():
        st.error("Please enter at least one name.")
    else:
        with preview_container:
            # Register fonts with unique identifiers
            name_font = register_uploaded_font(name_font_file, "name")
            text_font = register_uploaded_font(text_font_file, "text")

            # Get the first name for preview
            names = get_names()
            if names:
                with st.spinner("Generating preview..."):
                    preview_pdf = process_certificate(
                        None,
                        names[0],
                        description_text,
                        date_text,
                        name_font,
                        text_font,
                    )

                    # Display the PDF preview
                    st.success(f"Preview certificate for: {names[0]}")
                    preview_success = display_pdf(preview_pdf.getvalue())

                    # Always provide a download option
                    st.download_button(
                        label="Download Preview",
                        data=preview_pdf,
                        file_name=f"preview_{names[0].replace(' ', '_')}.pdf",
                        mime="application/pdf",
                    )
            else:
                st.error("No valid names found. Please enter at least one name.")

# Process form submission
if submit_button:
    # Check required inputs
    if template_file is None:
        st.error("Please upload a PDF template file.")
    else:
        # Register fonts with unique identifiers
        name_font = register_uploaded_font(name_font_file, "name")
        text_font = register_uploaded_font(text_font_file, "text")

        # Get names
        names = get_names()
        if not names:
            st.error("No names provided. Please enter at least one name.")
        else:
            # Create a zip file to hold all generated certificates
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                with st.spinner(f"Generating {len(names)} certificates..."):
                    for name in names:
                        # Process the certificate
                        pdf_bytes = process_certificate(
                            None,  # Not used anymore as we create a fresh copy inside function
                            name,
                            description_text,
                            date_text,
                            name_font,
                            text_font,
                        )

                        # Add the certificate to the zip file
                        filename = f"{name.replace(' ', '_')}_katilimbelgesi.pdf"
                        zip_file.writestr(filename, pdf_bytes.getvalue())

                    # Add a preview for the first certificate
                    if names:
                        preview_pdf = process_certificate(
                            None,
                            names[0],
                            description_text,
                            date_text,
                            name_font,
                            text_font,
                        )
                        zip_file.writestr("preview.pdf", preview_pdf.getvalue())

                        # Show preview
                        st.subheader("Generated Certificate Preview")
                        display_pdf(preview_pdf.getvalue())
                        st.download_button(
                            label="Download Preview",
                            data=preview_pdf,
                            file_name=f"preview_{names[0].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                        )

            # Provide download for the zip file
            zip_buffer.seek(0)
            st.success(f"Generated {len(names)} certificates!")
            st.download_button(
                label=f"Download All Certificates ({len(names)} files)",
                data=zip_buffer,
                file_name="certificates.zip",
                mime="application/zip",
            )

# Instructions
with st.expander("How to Use"):
    st.markdown(
        """
    1. **Upload a PDF template** - This will be the base design of your certificate
    2. **Upload font files** - Custom TTF fonts for names and text
    3. **Enter names** - One name per line in the text area
    4. **Configure settings** - Adjust coordinates and font sizes as needed
    5. **Preview** - Click "Preview Certificate" to see how it will look
    6. **Generate certificates** - Create PDFs for all names
    
    All certificates will be provided in a single ZIP file for download.
    """
    )

# Requirements note
with st.expander("Requirements"):
    st.markdown(
        """
    This app requires the following Python packages:
    ```
    streamlit
    reportlab
    PyPDF2
    pdf2image
    pillow
    poppler-utils  # System dependency for pdf2image
    ```
    
    Install Python packages with: 
    `pip install streamlit reportlab PyPDF2 pdf2image pillow`
    
    On Ubuntu/Debian systems, install poppler-utils with:
    `apt-get install -y poppler-utils`
    
    For Streamlit Cloud deployment, create a packages.txt file with:
    ```
    poppler-utils
    ```
    
    Run with: `streamlit run app.py`
    """
    )
