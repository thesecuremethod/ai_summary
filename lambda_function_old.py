

import requests                 # For HTTP requests to arXiv and PDFs  
import xml.etree.ElementTree as ET  # To parse arXiv XML responses  
import boto3                    # AWS SDK to upload to S3  
from io import BytesIO          # In-memory byte stream for PDFs  

def lambda_handler(event, context):  # AWS Lambda entry point  
    ARXIV_QUERY = (             # arXiv query URL for AI papers  
        "http://export.arxiv.org/api/query"
        "?search_query=(cat:cs.LG+OR+cat:cs.CL)"
        "+AND+(all:application+OR+all:deployment+OR+all:tool+OR+all:benchmark)"
        "&sortBy=submittedDate&sortOrder=descending&max_results=50"
    )
    S3_BUCKET = "your-s3-bucket-name"       # S3 bucket name  
    S3_PREFIX = "arxiv-papers/"             # S3 key prefix/folder  

    ns = {'atom': 'http://www.w3.org/2005/Atom'}  # XML namespace  
    s3 = boto3.client('s3')                  # S3 client instance  

    resp = requests.get(ARXIV_QUERY)         # Query arXiv API  
    root = ET.fromstring(resp.content)       # Parse XML  

    for entry in root.findall('atom:entry', ns):  # Iterate over papers  
        paper_id = entry.find('atom:id', ns).text.strip().split('/')[-1]  # Extract arXiv ID  
        pdf_url = next(                    # Find the PDF link  
            (l.attrib['href'] for l in entry.findall('atom:link', ns)  
             if l.attrib.get('title') == 'pdf'), None)  

        if pdf_url:                        # If found, download PDF  
            pdf_data = requests.get(pdf_url).content  
            s3.upload_fileobj(             # Upload to S3  
                BytesIO(pdf_data),  
                S3_BUCKET,  
                f"{S3_PREFIX}{paper_id}.pdf"  
            )  

    return {"status": "success"}           # Lambda response  
