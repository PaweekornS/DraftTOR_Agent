import sys
import time
from dotenv import dotenv_values
from openai import OpenAI

sys.stdout.reconfigure(encoding='utf-8')

vals = dotenv_values('.env')
print(f"Connecting to {vals['LLM_BASE_URL']} with model {vals['LLM_MODEL_NAME']}...", flush=True)

client = OpenAI(base_url=vals['LLM_BASE_URL'], api_key=vals['LLM_API_KEY'], timeout=60.0)

t0 = time.time()
try:
    resp = client.chat.completions.create(
        model=vals['LLM_MODEL_NAME'],
        messages=[{"role": "user", "content": "ตอบสั้นๆ: สวัสดีครับ"}],
        temperature=0.2,
        max_tokens=50
    )
    t1 = time.time()
    print(f"Success in {t1 - t0:.2f}s!", flush=True)
    print("Content:", resp.choices[0].message.content, flush=True)
except Exception as e:
    print(f"Error ({time.time() - t0:.2f}s): {e}", flush=True)
