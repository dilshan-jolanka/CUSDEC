import streamlit as st
import pdfplumber
import re
import json
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_text_from_pdf(pdf_file):
    """Extract all text from PDF"""
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
        return text

def extract_customs_fields(text):
    """Extract specific fields from customs/invoice document"""
    
    # Define patterns for all fields we want to extract
    patterns = {
        "Date": r"Current Date and Time.*?:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
        "User": r"Current User's Login:\s*([\w-]+)",
        "Exporter": r"(?:Exporter|BRFL).*?\n(.*?)(?:\n\d|Consignee|$)",
        "Exporter_Address": r"BRFL TEXTILES.*?\n(.*?)\n(.*?)(?:\n\s*\n|\n\d)",
        "Consignee": r"Consignee\n(.*?)(?:\n\d|$)",
        "Consignee_Address": r"Consignee\n.*?\n(.*?)(?:\n\s*\n|\n\d)",
        "Vessel_Flight": r"Vessel/Flight\s*\n(.*?)(?:\n\d|$)",
        "Description": r"Description\s*\n(.*?)(?:\n\s*\n|\n\d|Customs)",
        "Customs_Reference": r"Customs Reference Number:\s*\n(.*?)(?:\n\d|$)",
        "Financial_Settlement": r"Person Responsible for Financial Settlement\s*\n(.*?)(?:\n\d|$)",
        "Financial_Settlement_Address": r"Person Responsible for Financial Settlement\s*\n.*?\n(.*?)(?:\n\s*\n|\n\d)",
        "Trading": r"Trading\s*\n(.*?)(?:\n\d|$)",
        "Country_Export": r"Country of Export\s*\n(.*?)(?:\n\d|$)",
        "Country_Origin": r"Country of origin\s*\n(.*?)(?:\n\d|$)",
        "Delivery_Terms": r"Delivery Terms\s*\n(.*?)(?:\n\d|$)",
        "Currency_Amount": r"Currency & TotalAmount Invoiced\s*\n(.*?)(?:\n\d|$)",
        "Exchange_Rate": r"Exchanage Rate\s*\n(.*?)(?:\n\d|$)",
        "Payment_Terms": r"Terms of payment\s*(.*?)(?:\n|$)",
        "Bank_Name": r"Bank Name\s*(.*?)(?:\n|$)",
        "Branch": r"Branch\s*(.*?)(?:\n|$)",
        "Commodity_Code": r"Commodity\(HS\) Code\s*\n(.*?)(?:\n\d|$)",
        "Gross_Mass": r"Gross Mass\s*\n(.*?)(?:\n\d|$)",
        "Net_Mass": r"Net Mass\s*\n(.*?)(?:\n\d|$)",
        "Guarantee": r"Guarantee\s*(.*?)(?:\n|$)"
    }
    
    results = {}
    
    # Extract each field using its pattern
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            # Clean up the extracted value
            value = match.group(1).strip()
            # Remove excessive whitespace
            value = re.sub(r'\s+', ' ', value)
            results[field] = value
        else:
            results[field] = "Not found"
            
    # Extract amount specifically
    if "Currency_Amount" in results:
        amount_match = re.search(r'([A-Z]{3})\s+([\d,.]+)', results["Currency_Amount"])
        if amount_match:
            results["Currency"] = amount_match.group(1)
            results["Amount"] = amount_match.group(2)
    
    return results

def main():
    st.set_page_config(page_title="Customs/Invoice Document Extractor", layout="wide")
    
    st.title("Customs & Invoice Document Extractor")
    st.write("Upload your customs declaration or invoice PDF for targeted field extraction")
    
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    
    if uploaded_file:
        # Save the file content for repeated access
        pdf_bytes = uploaded_file.getvalue()
        
        # Extract and display text for reference
        with st.expander("PDF Text Preview", expanded=False):
            text = extract_text_from_pdf(BytesIO(pdf_bytes))
            st.text_area("Document Text", text, height=200)
        
        # Extract button
        if st.button("Extract Document Fields"):
            with st.spinner("Extracting fields..."):
                text = extract_text_from_pdf(BytesIO(pdf_bytes))
                results = extract_customs_fields(text)
                
                # Display results in organized sections
                st.subheader("Extracted Document Fields")
                
                # Create tabs for organized display
                tabs = st.tabs(["Main Info", "Parties", "Shipping Details", "Financial", "Goods"])
                
                with tabs[0]:  # Main Info
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Date", value=results.get("Date", "Not found"))
                        st.text_input("User", value=results.get("User", "Not found"))
                        st.text_input("Customs Reference", value=results.get("Customs_Reference", "Not found"))
                    with col2:
                        st.text_input("Trading", value=results.get("Trading", "Not found"))
                        st.text_input("Country of Export", value=results.get("Country_Export", "Not found"))
                        st.text_input("Country of Origin", value=results.get("Country_Origin", "Not found"))
                
                with tabs[1]:  # Parties
                    st.text_input("Exporter", value=results.get("Exporter", "Not found"))
                    st.text_area("Exporter Address", value=results.get("Exporter_Address", "Not found"), height=100)
                    
                    st.text_input("Consignee", value=results.get("Consignee", "Not found"))
                    st.text_area("Consignee Address", value=results.get("Consignee_Address", "Not found"), height=100)
                    
                    st.text_input("Financial Settlement Party", value=results.get("Financial_Settlement", "Not found"))
                    st.text_area("Financial Settlement Address", value=results.get("Financial_Settlement_Address", "Not found"), height=100)
                    
                with tabs[2]:  # Shipping Details
                    st.text_input("Vessel/Flight", value=results.get("Vessel_Flight", "Not found"))
                    st.text_input("Delivery Terms", value=results.get("Delivery_Terms", "Not found"))
                    
                with tabs[3]:  # Financial
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Currency", value=results.get("Currency", "Not found"))
                        st.text_input("Amount", value=results.get("Amount", "Not found"))
                        st.text_input("Exchange Rate", value=results.get("Exchange_Rate", "Not found"))
                        st.text_input("Guarantee", value=results.get("Guarantee", "Not found"))
                    with col2:
                        st.text_input("Payment Terms", value=results.get("Payment_Terms", "Not found"))
                        st.text_input("Bank Name", value=results.get("Bank_Name", "Not found"))
                        st.text_input("Branch", value=results.get("Branch", "Not found"))
                    
                with tabs[4]:  # Goods
                    st.text_area("Description", value=results.get("Description", "Not found"), height=100)
                    st.text_input("Commodity (HS) Code", value=results.get("Commodity_Code", "Not found"))
                    st.text_input("Gross Mass", value=results.get("Gross_Mass", "Not found"))
                    st.text_input("Net Mass", value=results.get("Net_Mass", "Not found"))
                
                # Download option
                st.subheader("Export Data")
                
                # Format options
                export_format = st.radio("Select format", ["JSON", "CSV", "Text"])
                
                if export_format == "JSON":
                    json_str = json.dumps(results, indent=2)
                    st.download_button(
                        "Download JSON",
                        data=json_str,
                        file_name="customs_invoice_data.json",
                        mime="application/json"
                    )
                elif export_format == "CSV":
                    # Convert nested data to flat structure
                    flat_data = {k: v for k, v in results.items()}
                    df = pd.DataFrame([flat_data])
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        data=csv,
                        file_name="customs_invoice_data.csv",
                        mime="text/csv"
                    )
                else:  # Text
                    text_output = "\n".join([f"{k}: {v}" for k, v in results.items()])
                    st.download_button(
                        "Download Text",
                        data=text_output,
                        file_name="customs_invoice_data.txt",
                        mime="text/plain"
                    )
                    
                # Display raw extraction for debugging
                with st.expander("Raw Extraction Results", expanded=False):
                    st.json(results)

if __name__ == "__main__":
    main()