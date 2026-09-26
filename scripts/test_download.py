import urllib.request
import ssl
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def download_file(url, target_path):
    print(f"Downloading: {url} -> {target_path}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            content = resp.read()
            with open(target_path, 'wb') as f:
                f.write(content)
            print(f"Saved {len(content)} bytes to {target_path}")
            return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

if __name__ == '__main__':
    os.makedirs('data/downloads', exist_ok=True)
    # Test memo docx from Health Department
    url_memo = 'https://hr.dmh.go.th/files/MDocs/px/V5-23.docx'
    download_file(url_memo, 'data/downloads/memo_sample.docx')
