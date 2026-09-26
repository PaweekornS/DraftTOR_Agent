import urllib.request
import urllib.parse
import ssl
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

WU_FILES = [
    ("tor_ebidding_service_over_500k.docx", "https://dps.wu.ac.th/wp-content/uploads/2023/08/10.-%E0%B8%A7%E0%B8%B4%E0%B8%98%E0%B8%B5e-bidding-%E0%B8%87%E0%B8%B2%E0%B8%99%E0%B8%88%E0%B9%89%E0%B8%B2%E0%B8%87%E0%B8%97%E0%B8%B5%E0%B9%88%E0%B8%A1%E0%B8%B4%E0%B9%83%E0%B8%8a%E0%B9%88%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%88%E0%B9%89%E0%B8%B2%E0%B8%87%E0%B8%81%E0%B9%88%E0%B8%AD%E0%B8%AA%E0%B8%A3%E0%B9%89%E0%B8%B2%E0%B8%87-%E0%B8%A7%E0%B8%87%E0%B9%80%E0%B8%87%E0%B8%B4%E0%B8%99%E0%B9%80%E0%B8%81%E0%B8%B4%E0%B8%99-500000-%E0%B8%9A%E0%B8%B2%E0%B8%97.docx"),
    ("tor_ebidding_purchase_over_500k.docx", "https://dps.wu.ac.th/wp-content/uploads/2023/08/8.-%E0%B8%A7%E0%B8%B4%E0%B8%98%E0%B8%B5-e-bidding-%E0%B8%8B%E0%B8%B7%E0%B9%89%E0%B8%AD-%E0%B8%A7%E0%B8%87%E0%B9%80%E0%B8%87%E0%B8%B4%E0%B8%99%E0%B9%80%E0%B8%81%E0%B8%B4%E0%B8%99-500000-%E0%B8%9A%E0%B8%B2%E0%B8%97.docx"),
    ("tor_specific_service_under_100k.docx", "https://dps.wu.ac.th/wp-content/uploads/2023/08/6.-%E0%B8%A7%E0%B8%B4%E0%B8%98%E0%B8%B5%E0%B9%80%E0%B8%89%E0%B8%9E%E0%B8%B2%E0%B8%B0%E0%B8%88%E0%B8%B2%E0%B8%B0%E0%B8%88%E0%B8%87-%E0%B8%87%E0%B8%B2%E0%B8%99%E0%B8%88%E0%B9%89%E0%B8%B2%E0%B8%87%E0%B8%97%E0%B8%B5%E0%B9%88%E0%B8%A1%E0%B8%B4%E0%B9%83%E0%B8%8a%E0%B9%88%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%88%E0%B9%89%E0%B8%B2%E0%B8%87%E0%B8%81%E0%B9%88%E0%B8%AD%E0%B8%AA%E0%B8%A3%E0%B9%89%E0%B8%B2%E0%B8%87-%E0%B8%A7%E0%B8%87%E0%B9%80%E0%B8%87%E0%B8%B4%E0%B8%99%E0%B9%80%E0%B8%81%E0%B8%B4%E0%B8%99-100000-%E0%B8%9A%E0%B8%B2%E0%B8%97.docx"),
    ("sme_mit_declaration.docx", "https://dps.wu.ac.th/wp-content/uploads/2022/06/15.-%E0%B8%84%E0%B8%B3%E0%B8%A3%E0%B8%B1%E0%B8%9A%E0%B8%A3%E0%B8%AD%E0%B8%87%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%95%E0%B8%A3%E0%B8%A7%E0%B8%88%E0%B8%AA%E0%B8%AD%E0%B8%9A%E0%B8%9集中%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%81%E0%B8%AD%E0%B8%9A%E0%B8%81%E0%B8%B2%E0%B8%A3-SMEs-%E0%B8%81%E0%B8%A5%E0%B8%B0%E0%B8%AA%E0%B8%B4%E0%B8%99%E0%B8%84%E0%B9%89%E0%B8%B2%E0%B8%97%E0%B8%B5%E0%B9%88%E0%B8%9C%E0%B8%A5%E0%B8%B4%E0%B8%95%E0%B8%A0%E0%B8%B2%E0%B8%A2%E0%B9%83%E0%B8%99%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B9%80%E0%B8%97%E0%B8%A8%E0%B9%84%E0%B8%97%E0%B8%A2.docx")
]

for name, url in WU_FILES:
    out = os.path.join('data/templates/raw', name)
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = resp.read()
            with open(out, 'wb') as f:
                f.write(data)
            print(f"  [OK] Saved {out} ({len(data)} bytes)")
    except Exception as e:
        print(f"  [ERR] {e}")
