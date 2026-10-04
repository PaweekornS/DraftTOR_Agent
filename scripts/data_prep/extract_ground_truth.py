import pypdf
import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def extract_pdf_sections(pdf_path):
    reader = pypdf.PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"

    # Normalize whitespace
    full_text = re.sub(r'[ \t]+', ' ', full_text)
    
    # Basic extraction heuristics
    data = {
        "filename": os.path.basename(pdf_path),
        "total_pages": len(reader.pages),
        "raw_text_length": len(full_text),
        "extracted_sample_text": full_text[:4000]
    }
    
    # Try to extract project title
    title_match = re.search(r'(?:งานจ้าง|โครงการ|ข้อกำหนดขอบเขตของงาน)\s*(?:เรื่อง|:\s*TOR)?\s*([^\n\r]+)', full_text)
    if title_match:
        data["project_name"] = title_match.group(0).strip()
    else:
        data["project_name"] = os.path.splitext(os.path.basename(pdf_path))[0]

    # Look for standard headers
    headers = [
        ("background_and_rationale", r'1\.\s*ความเป็นมา(.*?)(?=2\.\s*วัตถุประสงค์)'),
        ("objectives", r'2\.\s*วัตถุประสงค์(.*?)(?=3\.\s*คุณสมบัติ)'),
        ("vendor_qualifications", r'3\.\s*คุณสมบัติของผู้ยื่นข้อเสนอ(.*?)(?=4\.\s*ขอบเขต)'),
        ("scope_of_work", r'4\.\s*ขอบเขตของงาน(.*?)(?=5\.\s*ระยะเวลา|5\.\s*งวดงาน)'),
    ]

    for key, pattern in headers:
        match = re.search(pattern, full_text, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
            data[key] = cleaned[:2500]  # Cap to reasonable size for structured dataset
            
    return data

def main():
    pdf_dir = 'data/ground_truth/tor_pdfs'
    out_dir = 'data/ground_truth/parsed_json'
    os.makedirs(out_dir, exist_ok=True)
    
    summary = []
    for f in os.listdir(pdf_dir):
        if f.endswith('.pdf'):
            path = os.path.join(pdf_dir, f)
            print(f"Parsing {f}...")
            item = extract_pdf_sections(path)
            json_name = os.path.splitext(f)[0] + '.json'
            with open(os.path.join(out_dir, json_name), 'w', encoding='utf-8') as out_f:
                json.dump(item, out_f, ensure_ascii=False, indent=2)
            summary.append({
                "file": f,
                "pages": item["total_pages"],
                "has_background": "background_and_rationale" in item,
                "has_objectives": "objectives" in item,
                "has_qualifications": "vendor_qualifications" in item,
                "has_scope": "scope_of_work" in item
            })
            
    print("\n--- Parsed Ground Truth Summary ---")
    for s in summary:
        print(f"✓ {s['file']} ({s['pages']} pages) - BG:{s['has_background']} OBJ:{s['has_objectives']} QUAL:{s['has_qualifications']} SCOPE:{s['has_scope']}")

if __name__ == '__main__':
    main()
