import urllib.request
import urllib.parse
import json
import ssl
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_page(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def download_file(url, out_path):
    print(f"Downloading {url} -> {out_path}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = resp.read()
            with open(out_path, 'wb') as f:
                f.write(data)
            print(f"Saved: {out_path} ({len(data)} bytes)")
            return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

if __name__ == '__main__':
    os.makedirs('data/ground_truth/tor_pdfs', exist_ok=True)
    os.makedirs('data/templates/raw', exist_ok=True)
    
    # 1. Fetch DGA procurement listing
    print("--- Searching DGA Procurement ---")
    dga_procure_html = get_page("https://www.dga.or.th/procurement/")
    # Find all pdf links
    pdf_links = re.findall(r'href=[\"\'](https?://[^\s\"\'<>]+\.pdf)[\"\']', dga_procure_html, re.I)
    print(f"Found {len(pdf_links)} PDF links on DGA procurement page")
    
    # If not on main, let's search via DuckDuckGo for direct DGA PDFs
    if not pdf_links:
        from find_links import search_duckduckgo
        print("Searching via DuckDuckGo for DGA TOR PDFs...")
        ddg_links = search_duckduckgo('site:dga.or.th "ขอบเขตของงาน" filetype:pdf', 10)
        for l in ddg_links:
            if '.pdf' in l.lower():
                pdf_links.append(l)

    print("Target DGA PDFs:")
    count = 0
    for url in pdf_links:
        if count >= 5:
            break
        filename = os.path.basename(urllib.parse.urlparse(url).path)
        if not filename.endswith('.pdf'):
            filename = f"dga_tor_{count+1}.pdf"
        target = os.path.join('data/ground_truth/tor_pdfs', filename)
        if download_file(url, target):
            count += 1
