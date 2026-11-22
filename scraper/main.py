import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Setup Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_html(html_text):
    if not html_text: return ""
    soup = BeautifulSoup(html_text, "html.parser")
    return soup.get_text(separator="\n").strip()[:5000] # Keep DB small

def fetch_remoteok():
    print("Fetching RemoteOK...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get("https://remoteok.com/api", headers=headers)
    if res.status_code != 200: return []
    
    data = res.json()
    jobs = []
    for job in data[1:]: 
        if not job.get("id"): continue
        jobs.append({
            "source": "remoteok",
            "external_id": str(job.get("id")),
            "title": job.get("position", "Unknown"),
            "company": job.get("company", "Unknown"),
            "location": job.get("location") or "Remote",
            "description": clean_html(job.get("description")),
            "apply_url": job.get("url"),
            "posted_at": job.get("date"),
            "country_code": "GLOBAL"
        })
    return jobs

def fetch_greenhouse(company_token):
    print(f"Fetching Greenhouse for {company_token}...")
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs?content=true"
    res = requests.get(url)
    if res.status_code != 200: return []
    
    data = res.json()
    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "source": "greenhouse",
            "external_id": str(job.get("id")),
            "title": job.get("title", "Unknown"),
            "company": company_token.capitalize(),
            "location": job.get("location", {}).get("name", "Unknown"),
            "description": clean_html(job.get("content", "")),
            "apply_url": job.get("absolute_url"),
            "posted_at": job.get("updated_at"),
            "country_code": "GLOBAL" 
        })
    return jobs

def main():
    all_jobs = []
    all_jobs.extend(fetch_remoteok())
    
    # Add as many companies as you want here!
    greenhouse_tokens = ["canonical", "figma", "discord", "stripe"] 
    for token in greenhouse_tokens:
        all_jobs.extend(fetch_greenhouse(token))

    print(f"Found {len(all_jobs)} total jobs. Saving to database...")

    # Upload to Supabase in batches of 100
    for i in range(0, len(all_jobs), 100):
        batch = all_jobs[i:i+100]
        try:
            # upsert means: if it exists, update. If not, insert.
            supabase.table("jobs").upsert(batch, on_conflict="source,external_id").execute()
            print(f"Saved batch {i} to {i+len(batch)}")
        except Exception as e:
            print(f"Error saving batch: {e}")

if __name__ == "__main__":
    main()
