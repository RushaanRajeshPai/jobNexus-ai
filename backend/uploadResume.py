import os
import tempfile
import json
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import requests
import base64

# Document processing libraries
import docx2txt
import PyPDF2
import io

# LangChain imports
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import SequentialChain, LLMChain
from langchain.prompts import PromptTemplate

# Initialize FastAPI app
app = FastAPI()

# Setup CORS to allow requests from the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up API keys
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDiUB-uN6FXNjHVTRYuZDVzS1ID4bAokUg")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "e1bc9d1d3dmshcf2c42a0dfe81e5p1d28b8jsn735aea25e6d3")
MODEL_NAME = "gemini-2.0-flash"

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    google_api_key=GOOGLE_API_KEY,
    temperature=0.2,
    convert_system_message_to_human=True
)

# Setup Parser for structured output
class ResumeParsingOutputParser(JsonOutputParser):
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            return super().parse(text)
        except Exception as e:
            print(f"Error parsing JSON output: {e}")
            print(f"Problematic text: {text}")
            # Try to clean and repair the output
            cleaned_text = self.clean_json_string(text)
            return json.loads(cleaned_text)
    
    def clean_json_string(self, text: str) -> str:
        # Extract JSON part if wrapped in ```json ... ``` or other markers
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        return text

parser = ResumeParsingOutputParser()

# Resume Parsing LLM Chain
resume_system_prompt = """
You are an expert resume analyzer specialized in extracting structured information from resumes. 
Analyze the provided resume text and extract the following information in JSON format:

1. Personal information (name, contact details)
2. Skills (technical, soft skills)
3. Education (degrees, institutions, years)
4. Work experience (positions, companies, responsibilities, achievements, years)
5. Projects (if any)
6. Certifications (if any)
7. Keywords (extract important keywords that represent the person's expertise)

Be comprehensive and accurate. Parse all relevant information but structure it carefully.
"""

resume_prompt = PromptTemplate(
    input_variables=["resume_text"],
    template="""
Carefully analyze this resume text and extract all relevant information in a structured format:

{resume_text}

Return ONLY the JSON response with no additional explanation. Follow this exact structure:
{{
    "personal_info": {{
        "name": "string",
        "contact": "string",
        "location": "string" 
    }},
    "skills": ["skill1", "skill2", ...],
    "education": [
        {{
            "degree": "string",
            "institution": "string",
            "year": "string"
        }},
        ...
    ],
    "experience": [
        {{
            "position": "string",
            "company": "string",
            "duration": "string",
            "responsibilities": ["string", "string", ...],
            "achievements": ["string", "string", ...]
        }},
        ...
    ],
    "projects": [
        {{
            "name": "string",
            "description": "string",
            "technologies": ["string", "string", ...]
        }},
        ...
    ],
    "certifications": ["string", "string", ...],
    "keywords": ["string", "string", ...]
}}
"""
)

resume_chain = (
    {"resume_text": RunnablePassthrough()}
    | resume_prompt
    | llm
    | parser
)

# Job Search Keywords Generator LLM Chain
job_search_prompt = PromptTemplate(
    input_variables=["resume_data"],
    template="""
You are a career advisor and job search expert. Based on the following parsed resume information, generate the most effective job search keywords and queries that would find the best matching jobs for this candidate.

Resume data:
{resume_data}

Generate search terms that include:
1. Job titles that match the candidate's experience level and skills
2. Key technical skills and technologies
3. Industry-specific terms
4. Alternative job titles and synonyms

Return ONLY the JSON response with no additional explanation. Follow this exact structure:
{{
    "search_keywords": [
        {{
            "primary_keyword": "string",
            "related_terms": ["string", "string", ...],
            "job_level": "entry|mid|senior",
            "locations": ["string", "string", ...]
        }},
        ...
    ]
}}

Generate 5-7 different search keyword combinations to maximize job discovery.
"""
)

job_search_chain = (
    {"resume_data": RunnablePassthrough()}
    | job_search_prompt
    | llm
    | parser
)

# Real-time job search using JSearch API (RapidAPI)
def search_jobs_jsearch(search_keywords):
    """
    Search for real jobs using JSearch API from RapidAPI
    This provides actual job listings from various job boards including LinkedIn data
    """
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    
    all_jobs = []
    
    # Search with multiple keyword combinations to get diverse results
    for keyword_set in search_keywords["search_keywords"][:3]:  # Limit to 3 searches to avoid rate limits
        query = keyword_set["primary_keyword"]
        
        querystring = {
            "query": query,
            "page": "1",
            "num_pages": "1",
            "date_posted": "week",  # Recent jobs only
            "remote_jobs_only": "false",
            "employment_types": "FULLTIME,PARTTIME,CONTRACTOR",
        }
        
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and data["data"]:
                    all_jobs.extend(data["data"][:5])  # Take top 5 from each search
            else:
                print(f"API request failed with status {response.status_code}: {response.text}")
            
            # Add delay to respect rate limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching jobs from JSearch API: {e}")
            continue
    
    # If API fails, fall back to mock data but with dynamic content based on keywords
    if not all_jobs:
        return generate_fallback_jobs(search_keywords)
    
    # Format jobs for frontend
    formatted_jobs = []
    seen_jobs = set()  # To avoid duplicates
    
    for job in all_jobs[:10]:  # Limit to top 10
        try:
            job_id = job.get("job_id", "")
            if job_id in seen_jobs:
                continue
            seen_jobs.add(job_id)
            
            # Extract company logo (try to get from various sources)
            company_logo = job.get("employer_logo") or "https://via.placeholder.com/120x120?text=" + job.get("employer_name", "Company")[:1]
            
            # Extract job details
            job_title = job.get("job_title", "Software Engineer")
            company_name = job.get("employer_name", "Tech Company")
            location = job.get("job_city", "Remote")
            if job.get("job_state"):
                location += f", {job.get('job_state')}"
            if job.get("job_country") and job.get("job_country") != "US":
                location += f", {job.get('job_country')}"
            
            # Determine work mode
            is_remote = job.get("job_is_remote", False)
            job_type = "Remote" if is_remote else "On-site"
            if "hybrid" in job.get("job_description", "").lower():
                job_type = "Hybrid"
            
            # Use the actual job apply link
            job_url = job.get("job_apply_link") or job.get("job_google_link", "https://www.linkedin.com/jobs/")
            
            # Calculate match score based on keyword relevance
            match_score = calculate_match_score(job, search_keywords)
            
            formatted_jobs.append({
                "id": job_id,
                "title": job_title,
                "company": company_name,
                "company_logo": company_logo,
                "location": location,
                "mode": job_type,
                "url": job_url,
                "description": job.get("job_description", "")[:200] + "...",
                "match_score": match_score,
                "posted_date": job.get("job_posted_at_date", "Recently")
            })
            
        except Exception as e:
            print(f"Error formatting job: {e}")
            continue
    
    # Sort by match score
    formatted_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    
    return formatted_jobs[:10]

def calculate_match_score(job, search_keywords):
    """Calculate match score based on keyword relevance"""
    score = 70  # Base score
    
    job_text = (job.get("job_title", "") + " " + 
               job.get("job_description", "") + " " + 
               job.get("employer_name", "")).lower()
    
    # Check for keyword matches
    total_keywords = 0
    matched_keywords = 0
    
    for keyword_set in search_keywords["search_keywords"]:
        primary = keyword_set["primary_keyword"].lower()
        related = [term.lower() for term in keyword_set.get("related_terms", [])]
        
        all_terms = [primary] + related
        total_keywords += len(all_terms)
        
        for term in all_terms:
            if term in job_text:
                matched_keywords += 1
    
    if total_keywords > 0:
        keyword_match_rate = matched_keywords / total_keywords
        score += int(keyword_match_rate * 25)  # Up to 25 bonus points
    
    return min(score, 98)  # Cap at 98%

def generate_fallback_jobs(search_keywords):
    """Generate fallback jobs when API is unavailable"""
    fallback_companies = [
        {"name": "TechCorp", "logo": "https://via.placeholder.com/120x120?text=TC"},
        {"name": "InnovateLabs", "logo": "https://via.placeholder.com/120x120?text=IL"},
        {"name": "DataSoft", "logo": "https://via.placeholder.com/120x120?text=DS"},
        {"name": "CloudTech", "logo": "https://via.placeholder.com/120x120?text=CT"},
        {"name": "DevSolutions", "logo": "https://via.placeholder.com/120x120?text=DS"},
    ]
    
    locations = ["San Francisco, CA", "New York, NY", "Austin, TX", "Seattle, WA", "Remote"]
    modes = ["Remote", "Hybrid", "On-site"]
    
    jobs = []
    for i, keyword_set in enumerate(search_keywords["search_keywords"][:5]):
        company = fallback_companies[i % len(fallback_companies)]
        job_title = keyword_set["primary_keyword"]
        
        jobs.append({
            "id": f"fallback_{i}",
            "title": job_title,
            "company": company["name"],
            "company_logo": company["logo"],
            "location": locations[i % len(locations)],
            "mode": modes[i % len(modes)],
            "url": f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}",
            "description": f"Exciting opportunity for a {job_title} role.",
            "match_score": 85 - (i * 5),
            "posted_date": "Recently"
        })
    
    return jobs

# Alternative job search using Adzuna API (backup option)
def search_jobs_adzuna(search_keywords):
    """
    Alternative job search using Adzuna API
    Free tier available with good coverage
    """
    app_id = os.environ.get("ADZUNA_APP_ID", "595333d0")
    app_key = os.environ.get("ADZUNA_APP_KEY", "4ab5e2aacb40f33b9197f36989e22ba6")
    
    if not app_id or not app_key or app_id == "your-adzuna-app-id":
        return generate_fallback_jobs(search_keywords)
    
    base_url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
    all_jobs = []
    
    for keyword_set in search_keywords["search_keywords"][:3]:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": keyword_set["primary_keyword"],
            "results_per_page": 5,
            "sort_by": "relevance"
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "results" in data:
                    all_jobs.extend(data["results"])
            time.sleep(0.5)
        except Exception as e:
            print(f"Error fetching from Adzuna: {e}")
            continue
    
    # Format Adzuna jobs
    formatted_jobs = []
    for i, job in enumerate(all_jobs[:10]):
        formatted_jobs.append({
            "id": job.get("id", f"adzuna_{i}"),
            "title": job.get("title", "Software Engineer"),
            "company": job.get("company", {}).get("display_name", "Company"),
            "company_logo": "https://via.placeholder.com/120x120?text=" + job.get("company", {}).get("display_name", "C")[:1],
            "location": job.get("location", {}).get("display_name", "Remote"),
            "mode": "On-site",  # Adzuna doesn't specify remote/hybrid clearly
            "url": job.get("redirect_url", "https://www.adzuna.com"),
            "description": job.get("description", "")[:200] + "...",
            "match_score": 80 - (i * 2),
            "posted_date": job.get("created", "Recently")
        })
    
    return formatted_jobs

# Function to extract text from PDF
def extract_text_from_pdf(file_content):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

# Function to extract text from DOCX
def extract_text_from_docx(file_content):
    return docx2txt.process(io.BytesIO(file_content))

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are allowed")
    
    # Read file content
    file_content = await file.read()
    
    # Extract text based on file type
    if file.filename.lower().endswith('.pdf'):
        resume_text = extract_text_from_pdf(file_content)
    else:  # .docx
        resume_text = extract_text_from_docx(file_content)
    
    if not resume_text or len(resume_text) < 100:
        raise HTTPException(status_code=400, detail="Could not extract sufficient text from the resume")
    
    try:
        # First agent: Parse resume
        parsed_resume = resume_chain.invoke(resume_text)
        
        # Second agent: Generate job search keywords
        search_keywords = job_search_chain.invoke(json.dumps(parsed_resume))
        
        # Third agent: Search for real jobs
        job_listings = search_jobs_jsearch(search_keywords)
        
        # If JSearch fails, try Adzuna as backup
        if not job_listings:
            job_listings = search_jobs_adzuna(search_keywords)
        
        # Return the full result
        return {
            "resume_analysis": parsed_resume,
            "search_keywords": search_keywords,
            "job_listings": job_listings
        }
    
    except Exception as e:
        print(f"Error processing resume: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")

# Root endpoint for testing
@app.get("/")
def read_root():
    return {"message": "AI Job Finder API is running with real-time job search"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "apis": {
            "gemini": "configured" if GOOGLE_API_KEY != "your-gemini-api-key" else "not configured",
            "jsearch": "configured" if RAPIDAPI_KEY != "your-rapidapi-key" else "not configured"
        }
    }

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)