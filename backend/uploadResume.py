import os
import tempfile
import json
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

# Set up Google Gemini API
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDiUB-uN6FXNjHVTRYuZDVzS1ID4bAokUg")
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

# Job Recommendation LLM Chain
job_recommendation_prompt = PromptTemplate(
    input_variables=["resume_data"],
    template="""
You are a career advisor and job matching expert. Based on the following parsed resume information, recommend the top 10 job positions that would be the best match for this candidate.

Resume data:
{resume_data}

For each recommended job position, provide the following details:
1. Job title/role
2. Required skills and how they match the candidate's profile
3. Industry
4. Suggested job level (entry, mid, senior)
5. Keywords to search on LinkedIn

Return ONLY the JSON response with no additional explanation. Follow this exact structure:
{{
    "job_recommendations": [
        {{
            "title": "string",
            "matching_skills": ["string", "string", ...],
            "industry": "string",
            "level": "string",
            "search_keywords": ["string", "string", ...]
        }},
        ...
    ]
}}
"""
)

job_recommendation_chain = (
    {"resume_data": RunnablePassthrough()}
    | job_recommendation_prompt
    | llm
    | parser
)

# LinkedIn Search LLM Chain
linkedin_search_prompt = PromptTemplate(
    input_variables=["job_recommendations"],
    template="""
You are tasked with constructing search queries for LinkedIn job listings based on job recommendations. For each recommended job, create an effective search query that would yield relevant results on LinkedIn.

Job recommendations:
{job_recommendations}

For each job recommendation, create a search strategy that includes:
1. Primary search terms (job title, required skills)
2. Secondary search terms (industry, level)
3. Any filters that should be applied

Return the JSON with search queries for each job. Follow this exact structure:
{{
    "search_queries": [
        {{
            "job_title": "string",
            "search_query": "string",
            "filters": {{
                "experience_level": "string",
                "job_type": "string",
                "location": "optional string"
            }}
        }},
        ...
    ]
}}
"""
)

linkedin_search_chain = (
    {"job_recommendations": RunnablePassthrough()}
    | linkedin_search_prompt
    | llm
    | parser
)

# Mock LinkedIn API function (since we don't have a LinkedIn API key)
def mock_linkedin_job_search(search_queries):
    """
    This function simulates getting job listings from LinkedIn.
    In a production environment, you would replace this with actual LinkedIn API calls
    or web scraping with proper authorization.
    """
    job_listings = []
    
    # Template for mock job data
    companies = [
        {"name": "Google", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Google_%22G%22_Logo.svg/120px-Google_%22G%22_Logo.svg.png"},
        {"name": "Microsoft", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Microsoft_logo.svg/120px-Microsoft_logo.svg.png"},
        {"name": "Amazon", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/120px-Amazon_logo.svg.png"},
        {"name": "Apple", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Apple_logo_black.svg/120px-Apple_logo_black.svg.png"},
        {"name": "Meta", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/120px-Meta_Platforms_Inc._logo.svg.png"},
        {"name": "Netflix", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Netflix_2015_logo.svg/120px-Netflix_2015_logo.svg.png"},
        {"name": "IBM", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/IBM_logo.svg/120px-IBM_logo.svg.png"},
        {"name": "Salesforce", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Salesforce.com_logo.svg/120px-Salesforce.com_logo.svg.png"},
        {"name": "Oracle", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Oracle_logo.svg/120px-Oracle_logo.svg.png"},
        {"name": "Intel", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Intel_logo_%282006-2020%29.svg/120px-Intel_logo_%282006-2020%29.svg.png"},
        {"name": "Adobe", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Adobe_Corporate_logo.svg/120px-Adobe_Corporate_logo.svg.png"},
        {"name": "Tesla", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Tesla_Motors.svg/120px-Tesla_Motors.svg.png"}
    ]
    
    locations = ["San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX", "Boston, MA", 
                "Chicago, IL", "Los Angeles, CA", "Denver, CO", "Atlanta, GA", "Remote"]
    
    modes = ["Remote", "Hybrid", "On-site"]
    
    # Generate 10 mock job listings based on search queries
    for i, query in enumerate(search_queries["search_queries"][:10]):
        company_idx = i % len(companies)
        location_idx = i % len(locations)
        mode_idx = i % len(modes)
        
        job_url = f"https://www.linkedin.com/jobs/search/?keywords={query['search_query'].replace(' ', '%20')}"
        
        job_listings.append({
            "id": f"job_{i+1}",
            "title": query["job_title"],
            "company": companies[company_idx]["name"],
            "company_logo": companies[company_idx]["logo"],
            "location": locations[location_idx],
            "mode": modes[mode_idx],
            "url": job_url,
            "description": f"A great opportunity for a {query['job_title']} role at {companies[company_idx]['name']}.",
            "match_score": 95 - (i * 5) if i < 5 else 70 - ((i-5) * 5)  # Decreasing match scores
        })
    
    return job_listings

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
        
        # Second agent: Generate job recommendations
        job_recommendations = job_recommendation_chain.invoke(json.dumps(parsed_resume))
        
        # Third agent: Create LinkedIn search queries
        search_queries = linkedin_search_chain.invoke(json.dumps(job_recommendations))
        
        # Fourth agent: Get job listings (mock LinkedIn API)
        job_listings = mock_linkedin_job_search(search_queries)
        
        # Return the full result
        return {
            "resume_analysis": parsed_resume,
            "job_recommendations": job_recommendations,
            "job_listings": job_listings
        }
    
    except Exception as e:
        print(f"Error processing resume: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")

# Root endpoint for testing
@app.get("/")
def read_root():
    return {"message": "Resume Analysis API is running"}

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)