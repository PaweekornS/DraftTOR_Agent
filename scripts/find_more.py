import urllib.request
import urllib.parse
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def search(q):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            raw = re.findall(r'href="//duckduckgo\.com/l/\?uddg=([^&"]+)', html)
            links = []
            for r in raw:
                u = urllib.parse.unquote(r)
                if any(ext in u.lower() for ext in ['.docx', '.doc', '.pdf']):
                    links.append(u)
            return links
    except Exception as e:
        print("err:", e)
        return []

if __name__ == "__main__":
    queries = [
        ('"รายงานการประชุม" filetype:docx site:go.th OR site:ac.th'),
        ('"ระเบียบวาระ" "การประชุม" filetype:doc OR filetype:docx'),
        ('"ใบลาป่วย" OR "แบบใบลาป่วย" filetype:docx OR filetype:doc'),
        ('"ร่าง TOR" OR "ขอบเขตของงาน" "จ้างพัฒนาระบบ" filetype:pdf site:go.th'), # IT project ground truth!
        ('"ร่าง TOR" OR "ขอบเขตของงาน" "ซื้อครุภัณฑ์" filetype:pdf site:go.th') # Hardware project ground truth!
    ]
    for q in queries:
        print(f"\n--- {q} ---")
        for link in search(q)[:5]:
            print(link)
