import streamlit as st
import io
import os
import tempfile
import zipfile
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

st.set_page_config(page_title="Certificate Generator", layout="wide")
st.title("Certificate Generator")

# Sidebar for configuration
with st.sidebar:
    st.header("PDF Settings")
    page_width = st.number_input("Page Width", value=841.89, step=10.0)
    page_height = st.number_input("Page Height", value=595.276, step=10.0)

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

# Main form for inputs
with st.form("certificate_form"):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Template & Fonts")
        template_file = st.file_uploader("Upload PDF Template", type=["pdf"])
        name_font_file = st.file_uploader("Upload Name Font (TTF)", type=["ttf"])
        text_font_file = st.file_uploader("Upload Text Font (TTF)", type=["ttf"])

    with col2:
        st.subheader("Names & Content")
        names_text = st.text_area("Enter names (one per line)")
        date_text = st.text_input("Certificate Date", "14 April 2025")

    st.subheader("Certificate Description")
    description_text = st.text_area(
        "Enter description text",
        "This certificate is presented to recognize the successful completion of the program.",
    )

    submit_button = st.form_submit_button("Generate Certificates")


# Function to save uploaded font to temporary file and register it
def register_uploaded_font(font_file, font_name):
    if font_file is None:
        return False

    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, font_file.name)

    # Save the uploaded font to the temporary file
    with open(temp_path, "wb") as f:
        f.write(font_file.getbuffer())

    # Register the font
    pdfmetrics.registerFont(TTFont(font_name, temp_path))
    return True


# Function to read names from input
def get_names():
    return [name.strip() for name in names_text.splitlines() if name.strip()]


def read_template(template_file):
    """Reads a PDF template from the uploaded file and returns a PdfReader object."""
    if template_file is None:
        return None
    template_bytes = template_file.getvalue()
    return PdfReader(io.BytesIO(template_bytes))


def add_name(c, name, coord, font_name, font_size):
    """Adds the given name centered at the specified coordinate on the canvas."""
    c.setFont(font_name, font_size)
    c.drawCentredString(coord[0], coord[1], name)


def add_description(c, description, coord, font_name, font_size, max_width=550):
    """Adds a centered, wrapped paragraph to the canvas using Platypus."""
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
    """Adds the date centered at the specified coordinate."""
    c.setFont(font_name, font_size)
    c.drawCentredString(coord[0], coord[1], date_str)


def merge_overlay(template_page, overlay_page):
    """Merges the overlay page onto the template page."""
    template_page.merge_page(overlay_page)
    return template_page


def process_certificate(template_pdf, name, description, date, name_font, text_font):
    """Processes a single certificate and returns the PDF bytes."""
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


# Process form submission
if submit_button:
    # Check required inputs
    if template_file is None:
        st.error("Please upload a PDF template file.")
    else:
        # Register fonts
        name_font_registered = register_uploaded_font(name_font_file, "NameFont")
        text_font_registered = register_uploaded_font(text_font_file, "TextFont")

        if not name_font_registered:
            st.warning("Name font not uploaded. Using default font.")
            name_font = "Helvetica"
        else:
            name_font = "NameFont"

        if not text_font_registered:
            st.warning("Text font not uploaded. Using default font.")
            text_font = "Helvetica"
        else:
            text_font = "TextFont"

        # Get names
        names = get_names()
        if not names:
            st.error("No names provided. Please enter names or upload a CSV file.")
        else:
            template_pdf = read_template(template_file)

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
                        filename = f"certificate_{name.replace(' ', '_')}.pdf"
                        zip_file.writestr(filename, pdf_bytes.getvalue())

                    # Add a preview for the first certificate
                    if names:
                        preview_pdf = process_certificate(
                            template_pdf,
                            names[0],
                            description_text,
                            date_text,
                            name_font,
                            text_font,
                        )
                        zip_file.writestr("preview.pdf", preview_pdf.getvalue())

                        # Show preview
                        st.subheader("Preview (First Certificate)")
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
    3. **Enter names** - Either directly or via CSV upload
    4. **Configure settings** - Adjust coordinates and font sizes as needed
    5. **Generate certificates** - Create PDFs for all names
    
    You can preview the first certificate before downloading the complete set.
    All certificates will be provided in a single ZIP file.
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
    pandas
    ```
    
    Install with: `pip install streamlit reportlab PyPDF2 pandas`
    
    Run with: `streamlit run app.py`
    """
    )
