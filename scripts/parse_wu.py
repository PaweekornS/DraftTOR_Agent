import urllib.request
import re
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
headers = {'User-Agent': 'Mozilla/5.0'}

pages = ['https://dps.wu.ac.th/?page_id=11231', 'https://dps.wu.ac.th/?p=16795']
for page in pages:
    print(f"=== {page} ===")
    req = urllib.request.Request(page, headers=headers)
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    # match any href with docx, doc, or pdf
    for m in re.finditer(r'href=[\"\']([^\"\']+\.(?:docx|doc|pdf))[\"\']', html, re.I):
        url = m.group(1)
        print("FOUND:", url)
