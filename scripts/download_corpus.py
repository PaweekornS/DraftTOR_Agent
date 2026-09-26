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

DGA_GROUNDING_REDIRECTS = [
    ("DGA_AI_Smart_Search_TOR.pdf", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMXAO_Ed-xKbYXKESFbwHxC6H7eyL03Mo0og6uOg4Z-zIcDN4AatlYXMSxBRPkEV2wrjYniHOvzUJd4KH15VmzvtQe6XhiP9sPfA8wM-V8F4iKRCblzY45312XaxdHx-zlEx5thw0lPyXmIUaPrgGKw89TYVdVsfNPBw=="),
    ("DGA_AI_Gov_Leader_TOR.pdf", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH6WJfAeC1rohe8Gwc1tSp4Be4ZxIeBM31DKRyOmU0DJVYsEHtGwUcGUUHS-2UN1GLl_-dmn7MgH6J2lXNyuuZuBFnFWmDTW6oLHFZknfuBjQoNhC7oOAv7S6O47leGjfqw0TYQ5wmNRYXm6NU2uDt4LKQYSmo1_mccVA=="),
    ("DGA_Budget_System_TOR.pdf", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGffR6J09A67YslD5WINOQop1nPgmXGy7dCQpBpFK3qV0axjbC3Sy_Z6F0sfOWL1vVGNd8KuUiFIFbbooQKbRgkHtcNT9ev1yFmzy9CED77Jznabs4AFiX2Ut0jk9Qq6TnFkn-1peMr6AboiXlykokMwR-MeGl9E4Epgw=="),
    ("DGA_CSOC_CyberSecurity_TOR.pdf", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH42A0pdrwReLW3KtLdpStMe8dsLhJG9dh0KE8wLso5HSHhO1kKcxl1R7k2V2xad2rYbyYU6DE2_rCt2PRiK29BSJTg3Kk_3fuluxdu-5sK7-g5yTG1dfiB-APVmhVj5Ag3UHwTYihGEOcDNFFD9irKopfSUN9ktvoevg=="),
    ("DGA_Unified_Communication_TOR.pdf", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFcJ92zRFZtfJyeRRydqxFZ8tUk8nABSe_VvKrJ61ehEzlkPGuWoFjMpvCkwFoH9ZUpDVZVYj8tBSc-wg1vr3oBjBsxRDkOIuKGf7jxAumczFEXj7E_PSIjMGRvcPLBJfpY9IovVM9R7yZMpIXicPBVBibNo2QyeK54aqtwk5RvH4js_1PtkmzW_ze2YDnMNObA0uvF0UN7TeHtV3wTbfOiPqf8ab17lGoKnxDUwkr18dZRjXz_cizUQJlnXKQKSsFHuaCvPQU=")
]

# Additional docx template links
TEMPLATE_URLS = [
    ("memo_template_dmh.docx", "https://hr.dmh.go.th/files/MDocs/px/V5-23.docx"),
    ("memo_sample_nssc.docx", "https://www.nssc.ac.th/main/wp-content/uploads/2024/10/033-%E0%B8%95%E0%B8%B1%E0%B8%A7%E0%B8%AD%E0%B8%A2%E0%B9%88%E0%B8%B2%E0%B8%87%E0%B9%81%E0%B8%9A%E0%B8%9A%E0%B8%9F%E0%B8%AD%E0%B8%A3%E0%B9%8C%E0%B8%A1%E0%B8%9A%E0%B8%B1%E0%B8%99%E0%B8%97%E0%B8%B6%E0%B8%81%E0%B8%82%E0%B9%89%E0%B8%AD%E0%B8%84%E0%B8%A7%E0%B8%B2%E0%B8%A1.docx"),
    ("tor_template_lru.docx", "https://inven.lru.ac.th/wp-content/uploads/2026/05/1-%E0%B9%81%E0%B8%9A%E0%B8%9A%E0%B8%9F%E0%B8%AD%E0%B8%A3%E0%B9%8C%E0%B8%A1-TOR-%E0%B8%A7%E0%B8%B4%E0%B8%98%E0%B8%B5%E0%B9%80%E0%B8%89%E0%B8%9E%E0%B8%B2%E0%B8%B0%E0%B8%88%E0%B8%B0%E0%B8%88%E0%B8%87-1.docx")
]

def download(name, url, folder):
    target = os.path.join(folder, name)
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = resp.read()
            with open(target, 'wb') as f:
                f.write(data)
            print(f"  [OK] Saved {target} ({len(data)} bytes)")
            return True
    except Exception as e:
        print(f"  [ERR] {e}")
        return False

def main():
    os.makedirs('data/ground_truth/tor_pdfs', exist_ok=True)
    os.makedirs('data/templates/raw', exist_ok=True)

    print("=== 1. Fetching Real Government Ground Truth TORs (PDF) ===")
    for filename, red_url in DGA_GROUNDING_REDIRECTS:
        download(filename, red_url, 'data/ground_truth/tor_pdfs')

    print("\n=== 2. Fetching Real Government Templates (.docx) ===")
    for filename, url in TEMPLATE_URLS:
        download(filename, url, 'data/templates/raw')

if __name__ == '__main__':
    main()
