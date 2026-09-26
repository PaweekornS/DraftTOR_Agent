import urllib.request
import urllib.parse
import json
import ssl
import re
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def search_duckduckgo(query, max_results=10):
    """Search DuckDuckGo HTML for direct document links."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            # Extract result links
            raw_links = re.findall(r'<a class="result__url" href="([^"]+)"', html)
            if not raw_links:
                raw_links = re.findall(r'href="//duckduckgo\.com/l/\?uddg=([^&"]+)', html)
                raw_links = [urllib.parse.unquote(l) for l in raw_links]
            return raw_links[:max_results]
    except Exception as e:
        print(f"Error querying {query}: {e}")
        return []

if __name__ == "__main__":
    queries = [
        ('"ร่างขอบเขตของงาน" filetype:docx', "tor_docx"),
        ('"บันทึกข้อความ" filetype:docx site:go.th OR site:ac.th', "memo_docx"),
        ('"ระเบียบวาระการประชุม" filetype:docx', "agenda_docx"),
        ('"แบบใบลาป่วย" filetype:docx', "leave_docx")
    ]
    for q, cat in queries:
        links = search_duckduckgo(q, 5)
        print(f"[{cat}] ({len(links)} results):")
        for l in links:
            print("  -", l)
