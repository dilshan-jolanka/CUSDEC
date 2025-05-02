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
def extract_page_from_pdf(pdf_file):
    """Extracts the first page object from a PDF file using pdfplumber."""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Check if there is at least one page
            if len(pdf.pages) > 0:
                # Return the first page object
                return pdf.pages[0]
            else:
                st.warning("PDF file contains no pages.")
                return None # Return None if no pages
    except Exception as e:
        # Display an error message if PDF extraction fails
        st.error(f"Error extracting page from PDF: {e}")
        return None # Return None to indicate an error

# Function to extract specific data fields from the PDF text using Gemini
def extract_data_fields(pdf_file):
    """
    Extracts specific fields from PDF text using the Gemini API and positional information for key boxes.
    Tailored for CUSDEC II documents based on user-specified fields.
    Debugging output is removed in this version.
    """
    # Get the first page object from the PDF using the corrected function
    page = extract_page_from_pdf(pdf_file)

    # If page extraction failed or no page was found, return empty data structures
    if page is None: # Check if page is None
        return {"error": "Could not extract page from PDF or PDF is empty."}

    # Extract full text from the page
    document_text = page.extract_text()

    # Define approximate bounding box coordinates for specific boxes on page 1 (top-left origin)
    # These are rough estimates and may need tuning based on actual PDF scans.
    # Coordinates are (x0, top, x1, bottom)
    specific_box_coords = {
        # Rough estimate for the value region of Box 11.
        "Box 11 Value": (170, 100, 250, 130), # Adjust these coordinates as needed
        # Rough estimate for the value region of the Description sub-field within Box 31.
        "Box 31 Description Value": (550, 300, 800, 450), # Adjust these coordinates as needed
        # Rough estimate for the entire Box 31 area (including labels and description)
        "Box 31 Full Text": (400, 280, 800, 480), # Adjust these coordinates as needed
        # Rough estimate for the D.Val value area near Box 44
        "D.Val Value": (450, 500, 550, 530), # Adjust these coordinates as needed
        # Rough estimate for the D.Qty value area near Box 44
        "D.Qty Value": (580, 500, 680, 530), # Adjust these coordinates as needed
    }

    # Extract text specifically from the defined bounding boxes
    specific_box_texts = {}
    for box_name, bbox in specific_box_coords.items():
        try:
            # Extract text within the bounding box and strip leading/trailing whitespace
            extracted_text = page.extract_text(bbox=bbox)
            specific_box_texts[box_name] = extracted_text.strip() if extracted_text else ""
        except Exception as e:
            st.warning(f"Could not extract text from {box_name} using bbox {bbox}: {e}")
            specific_box_texts[box_name] = "Extraction Failed"

    # Initialize specific_text_prompt before using it
    specific_text_prompt = ""
    # Prepare specific box texts for the prompt, focusing on relevant areas
    if "Box 11 Value" in specific_box_texts:
        specific_text_prompt += f"Text found in the approximate region of Box 11 value: \"{specific_box_texts['Box 11 Value']}\"\n"
    if "Box 31 Description Value" in specific_box_texts:
        specific_text_prompt += f"Text found in the approximate region of Box 31 Description value: \"{specific_box_texts['Box 31 Description Value']}\"\n"
    if "Box 31 Full Text" in specific_box_texts:
         specific_text_prompt += f"Full text found in the approximate region of Box 31: \"{specific_box_texts['Box 31 Full Text']}\"\n"
    if "D.Val Value" in specific_box_texts:
         specific_text_prompt += f"Text found in the approximate region of D.Val value: \"{specific_box_texts['D.Val Value']}\"\n"
    if "D.Qty Value" in specific_box_texts:
         specific_text_prompt += f"Text found in the approximate region of D.Qty value: \"{specific_box_texts['D.Qty Value']}\"\n"


    # Define the fields to extract and a mapping from Gemini's likely output keys
    # to the desired display keys. Removed Box 50 and Export Release granted.
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
        "Box 31": "Box 31: Description", # Box 31 is included here
        "Box 33": "Box 33: Commodity (HS) Code",
        "Box 35": "Box 35: Gross Mass (Kg)",
        "Box 38": "Box 38: Net Mass (Kg)", # Added Box 38 as a common field
        "D.Val": "D.Val", # Added D.Val to common fields
        "D.Qty": "D.Qty", # Added D.Qty to common fields
    }

    # Create the prompt list using the desired display names for clarity in the prompt
    fields_to_extract_prompt_list = list(common_fields_map.values())
    fields_to_extract_prompt = "\n".join([f"- {name}" for name in fields_to_extract_prompt_list])


    # Construct the prompt tailored for CUSDEC II and the user's required fields
    # Explicitly ask Gemini to use the provided field names in its response
    # Added Box 38, D.Val, and D.Qty to common fields list in prompt
    # Included specific box texts and asked Gemini to use them, especially for Box 11, Box 31 Description, D.Val, and D.Qty
    prompt = f"""Analyze the following text from the first page of a SRI LANKA CUSTOMS-GOODS DECLARATION (CUSDEC II) document.

{specific_text_prompt}

Extract the following specific fields. For each field, look for the associated label (like 'Box 2: Exporter' or 'Customs Reference Number') and extract the value next to it.
For 'Box 11: Trading', use the text provided from the approximate region of its value.
For 'Box 31: Description', find the text that follows the label "Description:" within the text from the approximate region of Box 31, or use the text provided from the approximate region of Box 31 Description value. Ignore text associated with other labels like "Marks and numbers", "Containers No(s)", "Number and kind", "Marks & Nos of Packages:", "Number & Kind:", "Containers No(s):".
For 'D.Val' and 'D.Qty', use the text provided from their approximate regions near Box 44. If a value is not present in the provided text, return an empty string for that field.
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

        # --- IMPROVED PARSING AND CLEANING LOGIC for common fields ---
        # Iterate through the lines of Gemini's response
        for line in extracted_text_response.strip().split('\n'):
            line = line.strip()

            # Check if the line contains the expected separator ": "
            if ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                     gemini_key, value = parts[0].strip(), parts[1].strip()

                     # Find the corresponding display key from our map based on Gemini's key
                     # We iterate through the map to find a match for the gemini_key
                     display_key = None
                     for key, val in common_fields_map.items():
                         # Check if Gemini's key matches the original box key or the display name
                         if key == gemini_key or val == gemini_key:
                             display_key = val
                             break

                     if display_key:
                          # --- Clean the value: remove potential field name prefixes ---
                          cleaned_value = value.strip()

                          # Create a list of potential prefixes to remove
                          potential_prefixes = [
                              f"{display_key}:",
                              f"{display_key} :",
                              f"{gemini_key}:",
                              f"{gemini_key} :",
                              # Add more variations if needed, e.g., just the box number
                              f"{gemini_key.split(':')[0]}:",
                              f"{gemini_key.split(':')[0]} :",
                          ]

                          for prefix in potential_prefixes:
                              if cleaned_value.lower().startswith(prefix.lower()):
                                  # Remove the prefix and leading/trailing whitespace
                                  cleaned_value = cleaned_value[len(prefix):].strip()
                                  # Break after removing the first matching prefix
                                  break

                          # Store the cleaned value
                          common_data[display_key] = cleaned_value
        # --- END IMPROVED PARSING AND CLEANING LOGIC ---


    # Debugging output is removed in this version
    # st.subheader("Raw Gemini Response Text (for debugging)")
    # st.text(extracted_text_response if extracted_text_response else "No response text received.")
    # st.subheader("Parsed Common Data (before display - for debugging)")
    # st.write(common_data)


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
        "Box 31: Description", # Box 31 is included here for display
        "Box 33: Commodity (HS) Code",
        "Box 35: Gross Mass (Kg)",
        "Box 38: Net Mass (Kg)",
        "D.Val", # Added D.Val for display
        "D.Qty", # Added D.Qty for display
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
                # Get the extracted value using the correct display key, default to empty string if not present
                field_value = st.session_state.extracted_common_data.get(field, "") # Changed default to empty string
                # Alternate columns for display
                if index % 2 == 0:
                    with col1:
                        st.text_input(field, value=field_value, key=f"{field}_{index}", disabled=True) # Use disabled=True as these are extracted values
                else:
                    with col2:
                        st.text_input(field, value=field_value, key=f"{field}_{index}", disabled=True) # Use disabled=True

    # Add the export button below the extraction button and display
    if st.session_state.extracted_common_data: # Only show button if data has been extracted
        # Convert the extracted data dictionary to a pandas DataFrame
        # The DataFrame will have two columns: 'Field Name' and 'Value'
        # Use the same logic as display to get empty string for missing values
        export_data_list = []
        for field in common_fields_to_display:
             field_value = st.session_state.extracted_common_data.get(field, "") # Changed default to empty string
             export_data_list.append({'Field Name': field, 'Value': field_value})

        export_data = pd.DataFrame(export_data_list)


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
