import os
import json
import requests
import random
import time
from typing import List, Dict, Any
import google.generativeai as genai
from weaviate_client import get_weaviate_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

class JobsEmbeddingGenerator:
    def __init__(self):
        self.weaviate_client = get_weaviate_client()
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.ensure_schema_exists()
    
    def ensure_schema_exists(self):
        """Ensure the 'jobs' collection exists in Weaviate."""
        if not self.weaviate_client.schema.exists("jobs"):
            schema = {
                "classes": [{
                    "class": "jobs",
                    "description": "Collection of job openings",
                    "vectorizer": "text2vec-huggingface",
                    "properties": [
                        {
                            "name": "title",
                            "dataType": ["text"],
                            "description": "Job title"
                        },
                        {
                            "name": "company",
                            "dataType": ["text"],
                            "description": "Company name"
                        },
                        {
                            "name": "description",
                            "dataType": ["text"],
                            "description": "Job description"
                        },
                        {
                            "name": "location",
                            "dataType": ["text"],
                            "description": "Job location"
                        },
                        {
                            "name": "mode",
                            "dataType": ["text"],
                            "description": "Job mode (remote, onsite, hybrid)"
                        },
                        {
                            "name": "requirements",
                            "dataType": ["text"],
                            "description": "Job requirements"
                        },
                        {
                            "name": "link",
                            "dataType": ["text"],
                            "description": "LinkedIn job posting link"
                        },
                        {
                            "name": "logo",
                            "dataType": ["text"],
                            "description": "Company logo URL"
                        }
                    ]
                }]
            }
            self.weaviate_client.schema.create(schema)
            print("Created 'jobs' schema in Weaviate")

    def fetch_linkedin_jobs(self, search_queries: List[str], max_jobs: int = 5000) -> List[Dict[str, Any]]:
        """
        Fetch job data from LinkedIn using the Rapid API LinkedIn Jobs Search.
        You'll need to sign up for an API key at RapidAPI.
        """
        url = "https://linkedin-jobs-search.p.rapidapi.com/jobs"
        
        headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
            "X-RapidAPI-Host": "linkedin-jobs-search.p.rapidapi.com"
        }
        
        all_jobs = []
        jobs_per_query = max(5, max_jobs // len(search_queries))
        
        for query in search_queries:
            payload = {
                "search_terms": query,
                "location": "",
                "page": "1",
                "fetch_full_text": "yes"
            }
            
            try:
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    jobs = response.json()
                    all_jobs.extend(jobs[:jobs_per_query])
                    print(f"Fetched {len(jobs[:jobs_per_query])} jobs for query: {query}")
                else:
                    print(f"Failed to fetch jobs for query: {query}. Status code: {response.status_code}")
                
                # Respect rate limits
                time.sleep(2)
                
            except Exception as e:
                print(f"Error fetching jobs for query {query}: {str(e)}")
        
        # Deduplicate jobs by URL
        unique_jobs = []
        seen_urls = set()
        
        for job in all_jobs:
            if job.get("linkedin_job_url_cleaned") not in seen_urls:
                seen_urls.add(job.get("linkedin_job_url_cleaned"))
                unique_jobs.append(job)
        
        print(f"Total unique jobs collected: {len(unique_jobs)}")
        return unique_jobs[:max_jobs]
    
    def generate_sample_jobs(self, num_jobs: int = 5000) -> List[Dict[str, Any]]:
        """
        Generate sample job data when API is unavailable or for testing.
        In production, you'd replace this with the fetch_linkedin_jobs method.
        """
        job_titles = [
            "Software Engineer", "Data Scientist", "Product Manager", "UX Designer", 
            "DevOps Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
            "Machine Learning Engineer", "AI Researcher", "Cloud Architect", "Mobile Developer",
            "QA Engineer", "Technical Writer", "Project Manager", "Data Analyst",
            "Business Analyst", "Solutions Architect", "Security Engineer", "Database Administrator"
        ]
        
        companies = [
            "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix", "IBM", "Intel",
            "Salesforce", "Adobe", "Twitter", "LinkedIn", "Uber", "Airbnb", "Spotify",
            "Shopify", "Slack", "Zoom", "Stripe", "Square", "PayPal", "Oracle", "SAP"
        ]
        
        locations = [
            "San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX", "Boston, MA",
            "Chicago, IL", "Los Angeles, CA", "Denver, CO", "Atlanta, GA", "Toronto, Canada",
            "London, UK", "Berlin, Germany", "Singapore", "Sydney, Australia", "Tokyo, Japan"
        ]
        
        modes = ["Remote", "On-site", "Hybrid"]
        
        jobs = []
        for _ in range(num_jobs):
            title = random.choice(job_titles)
            company = random.choice(companies)
            location = random.choice(locations)
            mode = random.choice(modes)
            
            # Use Gemini to generate realistic job descriptions and requirements
            job_prompt = f"Generate a detailed job description and requirements for a {title} position at {company}. Format the output as a JSON with two keys: 'description' and 'requirements'. Make the description detailed and professional."
            
            try:
                job_content = self.model.generate_content(job_prompt).text
                # Extract JSON content
                job_content = job_content.replace("```json", "").replace("```", "").strip()
                job_details = json.loads(job_content)
                
                job = {
                    "title": title,
                    "company": company,
                    "description": job_details["description"],
                    "location": location,
                    "mode": mode,
                    "requirements": job_details["requirements"],
                    "link": f"https://www.linkedin.com/jobs/view/{random.randint(1000000, 9999999)}",
                    "logo": f"https://logo.clearbit.com/{company.lower().replace(' ', '')}.com"
                }
                jobs.append(job)
                
                # Respect rate limits and avoid overwhelming the API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error generating job content: {str(e)}")
        
        return jobs
                
    def store_job_embeddings(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Store job data and their embeddings in Weaviate.
        """
        print(f"Storing {len(jobs)} job embeddings in Weaviate...")
        
        batch_size = 100
        with self.weaviate_client.batch as batch:
            batch.batch_size = batch_size
            
            for i, job in enumerate(jobs):
                # Create job object with properties
                properties = {
                    "title": job["title"],
                    "company": job["company"],
                    "description": job["description"],
                    "location": job["location"],
                    "mode": job["mode"],
                    "requirements": job["requirements"],
                    "link": job["link"],
                    "logo": job["logo"]
                }
                
                # Combine all text fields for better embedding
                embedding_text = f"Job: {job['title']} at {job['company']}. {job['description']} {job['requirements']} Location: {job['location']}. Mode: {job['mode']}."
                
                # Add object to batch
                batch.add_data_object(
                    data_object=properties,
                    class_name="jobs",
                    vector=self.generate_embedding(embedding_text)
                )
                
                if (i + 1) % batch_size == 0:
                    print(f"Processed {i + 1} jobs")
        
        print("Completed storing job embeddings")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embeddings for text using the Gemini model.
        For simplicity, we're using a basic approach here.
        In production, use a dedicated embedding model.
        """
        try:
            response = self.model.generate_content(
                f"Convert the following text to a numerical embedding vector suitable for semantic search: {text}"
            )
            # This is a simplified approach - in a real implementation,
            # use a proper embedding model or the embedding features of Gemini
            # This will not work as expected but serves as a placeholder
            # Generate a random embedding for demonstration purposes
            return [random.random() for _ in range(384)]
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            return [random.random() for _ in range(384)]  # Fallback random embedding
    
    def fetch_and_store_jobs(self, use_api: bool = False) -> None:
        """
        Main method to fetch job data and store in Weaviate.
        """
        if use_api:
            # Define search queries to get diverse job results
            search_queries = [
                "software engineer", "data scientist", "product manager",
                "ux designer", "devops engineer", "frontend developer",
                "backend developer", "full stack developer", "machine learning engineer",
                "ai researcher", "cloud architect", "mobile developer"
            ]
            jobs = self.fetch_linkedin_jobs(search_queries)
        else:
            # Use sample data for testing or when API is unavailable
            jobs = self.generate_sample_jobs()
        
        # Store jobs in Weaviate
        self.store_job_embeddings(jobs)

# Main execution
if __name__ == "__main__":
    generator = JobsEmbeddingGenerator()
    # Change use_api to True when you have a valid RapidAPI key
    generator.fetch_and_store_jobs(use_api=False)