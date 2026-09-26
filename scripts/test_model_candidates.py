import sys
from dotenv import dotenv_values
from openai import OpenAI

sys.stdout.reconfigure(encoding='utf-8')
vals = dotenv_values('.env')
client = OpenAI(base_url=vals['LLM_BASE_URL'], api_key=vals['LLM_API_KEY'], timeout=15.0)

for m in [vals.get('LLM_MODEL_NAME'), "qwen/qwen-2.5-7b-instruct"]:
    print(f"Testing model: {m}...")
    try:
        resp = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "ขอ 1 ประโยคสั้นๆ แนะนำตัวเอง"}],
            max_tokens=100,
            temperature=0.2
        )
        msg = resp.choices[0].message
        content = msg.content
        reasoning = getattr(msg, 'reasoning', None)
        print(f"  Result for {m}: content='{content}', reasoning_len={len(reasoning or '')}")
    except Exception as e:
        print(f"  Error for {m}: {e}")
