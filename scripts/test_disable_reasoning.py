import urllib.request
import json
import sys
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding='utf-8')
vals = dotenv_values('.env')
url = 'https://openrouter.ai/api/v1/chat/completions'

body = {
    'model': vals.get('LLM_MODEL_NAME'),
    'messages': [{'role': 'user', 'content': 'ตอบ 1 คำเท่านั้น: สวัสดี'}],
    'reasoning': {'effort': 'none'}
}
req = urllib.request.Request(
    url,
    data=json.dumps(body).encode('utf-8'),
    headers={'Authorization': f"Bearer {vals['LLM_API_KEY']}", 'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print('result:', data['choices'][0]['message'])
except Exception as e:
    print('Error:', e)
