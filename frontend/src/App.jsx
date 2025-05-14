import { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [jobListings, setJobListings] = useState([]);
  const [resumeAnalysis, setResumeAnalysis] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      // Check if file is PDF or DOCX
      const fileType = selectedFile.type;
      const validTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ];
      
      if (!validTypes.includes(fileType)) {
        setUploadError('Please upload only PDF or DOCX files');
        setFile(null);
        return;
      }
      
      setFile(selectedFile);
      setUploadError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!file) {
      setUploadError('Please select a file first');
      return;
    }
    
    setIsUploading(true);
    setUploadError('');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await axios.post('http://localhost:8000/api/upload-resume', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      setResumeAnalysis(response.data.resume_analysis);
      setJobListings(response.data.job_listings);
    } catch (error) {
      console.error('Error uploading file:', error);
      setUploadError(error.response?.data?.detail || 'Error uploading resume');
    } finally {
      setIsUploading(false);
    }
  };

  const handleViewJob = (url) => {
    window.open(url, '_blank');
  };

  // Function to display skill match tags
  const SkillMatchTags = ({ skills }) => {
    return (
      <div className="flex flex-wrap gap-1 mt-1">
        {skills.slice(0, 3).map((skill, index) => (
          <span 
            key={index} 
            className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded"
          >
            {skill}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">JobNexus AI</h1>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Resume Upload Section */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Upload Your Resume</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center justify-center w-full">
                <label className="flex flex-col items-center justify-center w-full h-64 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <svg className="w-10 h-10 mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                    <p className="mb-2 text-sm text-gray-500">
                      <span className="font-semibold">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-xs text-gray-500">PDF or DOCX only</p>
                    {file && (
                      <p className="mt-2 text-sm text-green-600">
                        Selected: {file.name}
                      </p>
                    )}
                  </div>
                  <input 
                    type="file" 
                    className="hidden" 
                    onChange={handleFileChange}
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" 
                  />
                </label>
              </div>
              
              {uploadError && (
                <p className="text-red-500 text-sm">{uploadError}</p>
              )}
              
              <div className="flex justify-center">
                <button 
                  type="submit" 
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400"
                  disabled={isUploading || !file}
                >
                  {isUploading ? (
                    <div className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Analyzing...
                    </div>
                  ) : "Find Matching Jobs"}
                </button>
              </div>
            </form>
          </div>
        </div>
        
        {/* Results Section - Job Listings */}
        {jobListings.length > 0 && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                Top Job Recommendations Based on Your Resume
              </h2>
              
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {jobListings.map((job) => (
                  <div key={job.id} className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
                    <div className="p-5">
                      <div className="flex items-center mb-4">
                        <img 
                          src={job.company_logo} 
                          alt={`${job.company} logo`} 
                          className="w-12 h-12 mr-3 object-contain"
                        />
                        <div>
                          <h3 className="text-xl font-semibold text-gray-900">{job.title}</h3>
                          <p className="text-gray-600">{job.company}</p>
                        </div>
                      </div>
                      
                      <div className="mb-4">
                        <div className="flex items-center text-gray-500 mb-1">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                          </svg>
                          {job.location}
                        </div>
                        
                        <div className="flex items-center text-gray-500">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                          </svg>
                          {job.mode}
                        </div>
                      </div>
                      
                      <div className="mb-4">
                        <div className="flex items-center">
                          <div className="text-sm font-medium text-gray-700">Match Score</div>
                          <div className="ml-auto bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded">
                            {job.match_score}%
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2.5 mt-1">
                          <div 
                            className="bg-green-600 h-2.5 rounded-full" 
                            style={{ width: `${job.match_score}%` }}
                          ></div>
                        </div>
                      </div>
                      
                      <div className="mt-4">
                        <button
                          onClick={() => handleViewJob(job.url)}
                          className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        >
                          View Job
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Resume Analysis Section - Only shown after analysis */}
        {resumeAnalysis && (
          <div className="bg-white shadow rounded-lg mt-6">
            <div className="px-4 py-5 sm:p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Resume Analysis</h2>
              
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900">Skills Identified</h3>
                <div className="flex flex-wrap gap-2 mt-2">
                  {resumeAnalysis.skills.map((skill, index) => (
                    <span 
                      key={index} 
                      className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
              
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900">Education</h3>
                <div className="mt-2 space-y-2">
                  {resumeAnalysis.education.map((edu, index) => (
                    <div key={index} className="text-sm">
                      <p className="font-medium">{edu.degree}</p>
                      <p className="text-gray-600">{edu.institution}, {edu.year}</p>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="mt-4 bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900">Experience</h3>
                <div className="mt-2 space-y-4">
                  {resumeAnalysis.experience.map((exp, index) => (
                    <div key={index} className="text-sm">
                      <p className="font-medium">{exp.position}</p>
                      <p className="text-gray-600">{exp.company}, {exp.duration}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            © 2025 AI Job Finder. Powered by LangChain and Google Gemini.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;