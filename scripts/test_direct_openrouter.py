import urllib.request
import json
import sys
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding='utf-8')
vals = dotenv_values('.env')
url = 'https://openrouter.ai/api/v1/chat/completions'
model = vals.get('LLM_MODEL_NAME')

body = {
    'model': model,
    'messages': [{'role': 'user', 'content': 'ตอบ 1 คำเท่านั้น: สวัสดี'}],
    'max_tokens': 2048
}
req = urllib.request.Request(
    url,
    data=json.dumps(body).encode('utf-8'),
    headers={
        'Authorization': f"Bearer {vals['LLM_API_KEY']}",
        'Content-Type': 'application/json'
    }
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        msg = data['choices'][0]['message']
        print(f"content: '{msg.get('content')}'")
        print(f"reasoning len: {len(msg.get('reasoning') or '')}")
except Exception as e:
    print(f"Error: {e}")
