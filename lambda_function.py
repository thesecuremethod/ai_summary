

# lambda_function.py
"""
Lambda: crawl arXiv, stream PDFs straight to S3

ENV VARS
--------
ARXIV_SEARCH        full arXiv query string, e.g. 
                    "(cat:cs.LG OR cat:cs.CL) AND (all:application OR all:deployment)"
ARXIV_MAX_RESULTS   how many results to request (≤ 300 is safe).  default = 100
ARXIV_EMAIL         required by arXiv TOS for polite crawling
S3_BUCKET           target bucket
S3_PREFIX           prefix/folder inside the bucket, e.g. "arxiv/2025‑05‑11/"
AWS_REGION          picked up automatically
LOG_LEVEL           INFO | DEBUG

Memory suggestion: 512 MB   Timeout: 300 s
"""
import os, logging, time
import xml.etree.ElementTree as ET
from io import BytesIO
from urllib.parse import quote_plus

import boto3, botocore
import requests

# ---------- config -----------------------------------------------------------
S3_BUCKET   = os.environ["S3_BUCKET"]
S3_PREFIX   = os.getenv("S3_PREFIX",  "")
QUERY       = os.environ["ARXIV_SEARCH"]
MAX_RESULTS = int(os.getenv("ARXIV_MAX_RESULTS", "100"))
ARXIV_EMAIL = os.environ["ARXIV_EMAIL"]

HEADERS = {
    # arXiv asks for a valid UA incl. email; politeness & to avoid 403
    "User-Agent": f"arXiv-pdf-crawler/1.0 ({ARXIV_EMAIL})"
}

TIMEOUT       = (5, 120)        # (connect, read) seconds
PER_FILE_RETRY= 2               # simple client‑side retry
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

s3 = boto3.client("s3")

# ---------- helpers ----------------------------------------------------------
def already_in_s3(key: str) -> bool:
    """HEAD request – cheap.  Returns True if object already exists."""
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise          # propagate real AWS errors


def fetch_feed() -> ET.Element:
    base = "https://export.arxiv.org/api/query"
    params = (
        f"search_query={quote_plus(QUERY)}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={MAX_RESULTS}"
    )
    url = f"{base}?{params}"
    logger.info("Fetching feed %s", url)

    rsp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    rsp.raise_for_status()
    return ET.fromstring(rsp.text)


def iter_entries(feed_root: ET.Element):
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in feed_root.findall("atom:entry", ns):
        paper_id = entry.find("atom:id", ns).text.rsplit("/", 1)[-1]  # e.g. 2505.05471v1
        # find the PDF link
        pdf_url = None
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        if not pdf_url:
            logger.warning("no pdf link for %s", paper_id)
            continue
        yield paper_id, pdf_url


def download_and_upload(paper_id: str, pdf_url: str):
    key = f"{S3_PREFIX}{paper_id}.pdf"
    if already_in_s3(key):
        logger.debug("skip %s (already in S3)", paper_id)
        return "skipped"

    for attempt in range(1, PER_FILE_RETRY + 1):
        try:
            with requests.get(pdf_url, stream=True, headers=HEADERS, timeout=TIMEOUT) as r:
                r.raise_for_status()
                ctype = r.headers.get("Content-Type", "")
                if "pdf" not in ctype.lower():
                    raise ValueError(f"Non‑PDF content type '{ctype}'")

                s3.upload_fileobj(r.raw, Bucket=S3_BUCKET, Key=key)
                logger.info("uploaded %s", key)
                return "ok"
        except Exception as e:
            logger.warning("attempt %d failed for %s: %s", attempt, paper_id, e)
            if attempt == PER_FILE_RETRY:
                raise
            time.sleep(2 * attempt)   # back‑off & retry


# ---------- Lambda entry -----------------------------------------------------
def lambda_handler(event, context):
    ok = skip = fail = 0
    try:
        feed = fetch_feed()
        for paper_id, pdf_url in iter_entries(feed):
            try:
                status = download_and_upload(paper_id, pdf_url)
                if status == "ok":
                    ok += 1
                else:
                    skip += 1
            except Exception as e:
                fail += 1
                logger.error("give‑up on %s: %s", paper_id, e)
    except Exception as top:
        logger.error("fatal crawler error: %s", top, exc_info=True)
        raise

    logger.info("done – ok=%d  skipped=%d  failed=%d", ok, skip, fail)
    return {"ok": ok, "skipped": skip, "failed": fail}
