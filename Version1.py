import streamlit as st
import requests
import json
import pdfplumber
from dotenv import load_dotenv
import os
import re
import pandas as pd # Import pandas for DataFrame display
import io # Import io for handling binary data

# Load environment variables from .env file
load_dotenv()

# Gemini API Configuration
# Ensure you have GOOGLE_API_KEY set in your .env file
gemini_api_key = os.getenv("GOOGLE_API_KEY")
if not gemini_api_key:
    st.error("Gemini API key not found. Please set GOOGLE_API_KEY in your .env file.")
    st.stop() # Stop the app if the API key is not found

gemini_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Function to generate content using the Gemini API
def generate_content(prompt):
    """Sends a prompt to the Gemini API and returns the response."""
    headers = {
        "Content-Type": "application/json",
    }

    # Request data payload for the API
    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    # Make the API request
    try:
        response = requests.post(f"{gemini_endpoint}?key={gemini_api_key}", headers=headers, json=data)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        # Display an informative error message in the Streamlit app
        st.error(f"Error calling Gemini API: {e}")
        return None # Return None to indicate an error

# Function to read and extract text from a PDF file (only page 1)
def extract_text_from_pdf(pdf_file):
    """Extracts text from the first page of a PDF file using pdfplumber."""
    text = ""
    try:
        # Open the PDF file using pdfplumber
        with pdfplumber.open(pdf_file) as pdf:
            # Check if there is at least one page
            if len(pdf.pages) > 0:
                # Extract text only from the first page (index 0)
                text = pdf.pages[0].extract_text()
            else:
                st.warning("PDF file contains no pages.")
                text = "" # Set text to empty if no pages
        return text
    except Exception as e:
        # Display an error message if PDF extraction fails
        st.error(f"Error extracting text from PDF: {e}")
        return None # Return None to indicate an error

# Function to extract specific data fields from the PDF text using Gemini
def extract_data_fields(pdf_file):
    """
    Extracts specific fields from PDF text using the Gemini API.
    Tailored for CUSDEC II documents based on user-specified fields.
    Debugging output is removed in this version.
    """
    # Extract text from the uploaded PDF (only page 1)
    document_text = extract_text_from_pdf(pdf_file)

    # If text extraction failed or no text was found, return empty data structures
    if not document_text:
        return {"error": "Could not extract text from PDF or PDF is empty."}

    # Define the fields to extract and a mapping from Gemini's likely output keys
    # to the desired display keys. Includes the common fields requested. Added Box 38.
    common_fields_map = {
        "Box 2": "Box 2: Exporter",
        "Box 8": "Box 8: Consignee",
        "Box 9": "Box 9: Person Responsible for Financial Settlement",
        "Box 11": "Box 11: Trading", # Box 11 is included here
        "Box 14": "Box 14: Declarant/Representative",
        "Box 15": "Box 15: Country of Export",
        "Box 16": "Box 16: Country of origin",
        "Box 18": "Box 18: Vessel/Flight",
        "Box 20": "Box 20: Delivery Terms",
        "Box 22": "Box 22: Currency & Total Amount Invoiced",
        "Box 23": "Box 23: Exchange Rate",
        "Box 28": "Box 28: Financial and banking data",
        "Customs Reference Number": "Customs Reference Number",
        "Guarantee LKR": "Guarantee LKR",
        "Box 31": "Box 31: Description",
        "Box 33": "Box 33: Commodity (HS) Code",
        "Box 35": "Box 35: Gross Mass (Kg)",
        "Box 38": "Box 38: Net Mass (Kg)", # Added Box 38 as a common field
    }

    # Create the prompt list using the desired display names for clarity in the prompt
    fields_to_extract_prompt_list = list(common_fields_map.values())
    fields_to_extract_prompt = "\n".join([f"- {name}" for name in fields_to_extract_prompt_list])


    # Construct the prompt tailored for CUSDEC II and the user's required fields
    # Explicitly ask Gemini to use the provided field names in its response
    # Added Box 38 to common fields list in prompt
    prompt = f"""Analyze the following text from the first page of a SRI LANKA CUSTOMS-GOODS DECLARATION (CUSDEC II) document.

Extract the following specific fields. For each field, look for the associated label (like 'Box 2: Exporter' or 'Customs Reference Number') and extract the value next to it.
Return the extracted common fields in the format "FieldName: FieldValue". Use the FieldName exactly as specified in the list below.

Common Fields to Extract:
{fields_to_extract_prompt.strip()}

# Removed instructions for extracting line item details

Return the output as simple text. If a field is not found, indicate 'Not Found' for that specific field.

Document text:
{document_text}"""

    # Send the prompt to the Gemini API
    response = generate_content(prompt)

    common_data = {}

    # Process the response from Gemini
    extracted_text_response = "" # Initialize in case response is None
    if response and "candidates" in response and len(response['candidates']) > 0:
        extracted_text_response = response['candidates'][0]['content']['parts'][0]['text']

        # Parse the response text based on the prompt format
        for line in extracted_text_response.strip().split('\n'):
            line = line.strip()

            # --- Simplified Parsing Logic ---
            # Only parse lines that contain a colon, assuming they are common fields
            if ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                     gemini_key, value = parts[0].strip(), parts[1].strip()
                     # Map the key returned by Gemini to the desired display key
                     # We check if the Gemini key is one we expect from the map
                     if gemini_key in common_fields_map:
                          display_key = common_fields_map[gemini_key]
                          common_data[display_key] = value
            # --- End Simplified Parsing Logic ---


    # Debugging output is removed in this version


    # Return only the extracted common data
    return common_data

# Main Streamlit application function
def main():
    # Custom CSS for styling the Streamlit app
    st.markdown("""
        <style>
            .main-title {
                font-size: 40px;
                color: #4F8BF9;
                text-align: center;
                margin-bottom: 20px;
            }
            .sub-title {
                font-size: 24px; /* Slightly larger subtitle */
                color: #4F8BF9;
                margin-top: 20px;
                margin-bottom: 10px; /* Added margin-bottom */
            }
            .text-field {
                border-radius: 10px;
                padding: 10px;
                background: #f4f4f9;
                border: 1px solid #ccc;
                margin-bottom: 15px;
            }
             /* Removed .item-box style */
            .stDataFrame {
                margin-bottom: 15px; /* Add margin below DataFrame */
            }
        </style>
    """, unsafe_allow_html=True)

    # Set the title of the Streamlit app
    st.markdown('<h1 class="main-title">CUSDEC II Data Extractor</h1>', unsafe_allow_html=True)
    st.write("Upload a CUSDEC II PDF to extract specific data fields from the first page.")

    # File uploader widget
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

    # Define the list of common fields we expect to display based on the prompt
    # This list is used for iterating and displaying the extracted common data.
    # These are the desired display keys. Added Box 38.
    common_fields_to_display = [
        "Box 2: Exporter",
        "Box 8: Consignee",
        "Box 9: Person Responsible for Financial Settlement",
        "Box 11: Trading", # Box 11 is included here for display
        "Box 14: Declarant/Representative",
        "Box 15: Country of Export",
        "Box 16: Country of origin",
        "Box 18: Vessel/Flight",
        "Box 20: Delivery Terms",
        "Box 22: Currency & Total Amount Invoiced",
        "Box 23: Exchange Rate",
        "Box 28: Financial and banking data",
        "Customs Reference Number",
        "Guarantee LKR",
        "Box 31: Description",
        "Box 33: Commodity (HS) Code",
        "Box 35: Gross Mass (Kg)",
        "Box 38: Net Mass (Kg)", # Added Box 38 for display
    ]

    # Initialize session state for storing extracted data if it doesn't exist
    if 'extracted_common_data' not in st.session_state:
        st.session_state.extracted_common_data = {}

    # Process the uploaded file when it exists
    if uploaded_file is not None:
        st.write("PDF successfully uploaded!")

        # Button to trigger data extraction
        if st.button("Extract Data"):
            # Show a spinner while extracting data
            with st.spinner("Extracting data..."):
                # Call the extraction function - now only returns common_data
                common_data = extract_data_fields(uploaded_file)
                # Store the extracted data in session state
                st.session_state.extracted_common_data = common_data

            # Display the extracted common data
            st.markdown('<h2 class="sub-title">Extracted Common Data:</h2>', unsafe_allow_html=True)

            # Display common fields in two columns for better layout
            col1, col2 = st.columns(2)
            for index, field in enumerate(common_fields_to_display):
                # Get the extracted value using the correct display key, default to "Not Found" if not present
                field_value = st.session_state.extracted_common_data.get(field, "Not Found")
                # Alternate columns for display
                if index % 2 == 0:
                    with col1:
                        st.text_input(field, value=field_value, key=f"{field}_{index}", disabled=True) # Use disabled=True as these are extracted values
                else:
                    with col2:
                        st.text_input(field, value=field_value, key=f"{field}_{index}", disabled=True) # Use disabled=True

            # Removed the entire section for displaying line item breakdown
            # st.markdown('<h3 class="sub-title">Line Item Details:</h3>', unsafe_allow_html=True)
            # ... (rest of the line item display code)

    # Add the export button below the extraction button and display
    if st.session_state.extracted_common_data: # Only show button if data has been extracted
        # Convert the extracted data dictionary to a pandas DataFrame
        # The DataFrame will have two columns: 'Field Name' and 'Value'
        export_data = pd.DataFrame(list(st.session_state.extracted_common_data.items()), columns=['Field Name', 'Value'])

        # Create an in-memory Excel file buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_data.to_excel(writer, index=False, sheet_name='Extracted Data')
        excel_data = output.getvalue()

        # Provide a download button for the Excel file
        st.download_button(
            label="Export to Excel",
            data=excel_data,
            file_name='cusdec_common_data.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            help='Download the extracted common data as an Excel file.'
        )


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
