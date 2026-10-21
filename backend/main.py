"""FastAPI service for extracting useful signals from PDF resumes."""
from datetime import datetime
from io import BytesIO
import re
from typing import List

import PyPDF2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
except Exception:
    NLP = None

SKILLS = ["python", "java", "c++", "c#", "javascript", "typescript", "react", "next.js", "node.js", "html", "css", "tailwind", "sql", "mongodb", "postgresql", "mysql", "fastapi", "flask", "django", "aws", "azure", "gcp", "docker", "kubernetes", "git", "github", "linux", "figma", "rest api", "graphql", "machine learning", "deep learning", "data analysis", "data visualization", "power bi", "tableau", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "excel", "agile", "project management", "communication", "leadership", "problem solving"]
ROLE_REQUIREMENTS = {
    "Frontend Developer": ["react", "javascript", "typescript", "html", "css", "figma", "git"],
    "Backend Developer": ["python", "node.js", "fastapi", "django", "sql", "rest api", "docker"],
    "Full Stack Developer": ["react", "javascript", "python", "node.js", "sql", "git", "docker"],
    "Data Analyst": ["python", "sql", "excel", "power bi", "tableau", "pandas", "data analysis"],
    "Machine Learning Engineer": ["python", "machine learning", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch"],
    "Cloud Engineer": ["aws", "azure", "gcp", "docker", "kubernetes", "linux", "python"],
}
PROJECT_HEADINGS = ["projects", "project experience", "personal projects", "academic projects"]
EDUCATION_HEADINGS = ["education", "academic background"]
EXPERIENCE_HEADINGS = ["experience", "work experience", "professional experience"]
CERTIFICATION_HEADINGS = ["certifications", "certificates", "licenses"]
SECTION_HEADINGS = "|".join(re.escape(name) for name in (
    EDUCATION_HEADINGS + EXPERIENCE_HEADINGS + PROJECT_HEADINGS + CERTIFICATION_HEADINGS
    + ["achievements", "skills", "technical skills", "summary"]
))
MAX_PDF_BYTES = 4 * 1024 * 1024

app = FastAPI(title="Resume Analyzer API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RoleMatch(BaseModel):
    title: str
    match: int
    matched_skills: List[str]
    missing_skills: List[str]

class JobDescriptionMatch(BaseModel):
    target_role: str | None = None
    score: int
    matched_skills: List[str]
    missing_skills: List[str]
    suggestions: List[str]

class ProjectMatch(BaseModel):
    title: str
    skills: List[str]
    matched_keywords: List[str]

class ResumeAnalysis(BaseModel):
    candidate_name: str | None = None
    skills: List[str]
    education: List[str]
    experience: List[str]
    certifications: List[str]
    recommendations: List[RoleMatch]
    score: int
    issues: List[str]
    summary: str
    job_match: JobDescriptionMatch | None = None
    related_projects: List[ProjectMatch] = []
    projects: List[ProjectMatch] = []

def extract_pdf_text(contents: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(BytesIO(contents))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"We couldn't read that PDF: {exc}") from exc
    if len(text.strip()) < 20:
        raise HTTPException(status_code=422, detail="This PDF has no readable text. Try a text-based PDF instead of a scanned image.")
    return text

def contains_skill(text: str, skill: str) -> bool:
    escaped = re.escape(skill).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])", text, re.IGNORECASE))

def extract_skills(text: str) -> List[str]:
    return [skill for skill in SKILLS if contains_skill(text, skill)]

def section_text(text: str, names: List[str]) -> str:
    name_pattern = "|".join(re.escape(name) for name in names)
    pattern = rf"(?im)^[ \t]*(?:{name_pattern})[ \t]*:?[ \t]*\r?$([\s\S]*?)(?=^[ \t]*(?:{SECTION_HEADINGS})[ \t]*:?[ \t]*\r?$|\Z)"
    match = re.search(pattern, text)
    return match.group(1) if match else ""

def get_section(text: str, names: List[str]) -> List[str]:
    lines = [re.sub(r"^[•·▪\-–]\s*", "", line).strip() for line in section_text(text, names).splitlines()]
    return [line for line in lines if len(line) > 2][:6]

def candidate_name(text: str) -> str | None:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{2,50}", first_line) and "resume" not in first_line.lower(): return first_line.title()
    if NLP:
        doc = NLP(text[:800])
        return next((ent.text for ent in doc.ents if ent.label_ == "PERSON"), None)
    return None

def role_matches(skills: List[str]) -> List[RoleMatch]:
    skill_set, matches = set(skills), []
    for title, requirements in ROLE_REQUIREMENTS.items():
        matched = [skill for skill in requirements if skill in skill_set]
        missing = [skill for skill in requirements if skill not in skill_set]
        matches.append(RoleMatch(title=title, match=round(len(matched) / len(requirements) * 100), matched_skills=matched, missing_skills=missing[:3]))
    return sorted(matches, key=lambda item: item.match, reverse=True)[:3]

def target_role_from_description(description: str) -> str | None:
    normalized = description.lower()
    for role in ROLE_REQUIREMENTS:
        if role.lower() in normalized:
            return role
    aliases = {
        "machine learning": "Machine Learning Engineer",
        "frontend": "Frontend Developer",
        "front end": "Frontend Developer",
        "backend": "Backend Developer",
        "back end": "Backend Developer",
        "full stack": "Full Stack Developer",
        "data analyst": "Data Analyst",
        "cloud engineer": "Cloud Engineer",
    }
    return next((role for phrase, role in aliases.items() if phrase in normalized), None)

def match_job_description(skills: List[str], description: str, experience: List[str]) -> JobDescriptionMatch:
    target_role = target_role_from_description(description)
    required_skills = extract_skills(description) or ROLE_REQUIREMENTS.get(target_role, [])
    skill_set = set(skills)
    matched = [skill for skill in required_skills if skill in skill_set]
    missing = [skill for skill in required_skills if skill not in skill_set]
    score = round(len(matched) / len(required_skills) * 100) if required_skills else 0
    suggestions = []
    if not required_skills:
        suggestions.append("We couldn't calculate a keyword match. Add specific skill requirements or a recognizable role title to the job description.")
        return JobDescriptionMatch(target_role=target_role, score=score, matched_skills=matched, missing_skills=missing, suggestions=suggestions)
    if missing:
        suggestions.append(f"Add evidence of {', '.join(missing[:3])} if you have used these skills.")
    if not experience:
        suggestions.append("Mirror the job description with achievement-focused project or work-experience bullets.")
    if score < 70:
        suggestions.append("Use the job description's exact relevant keywords naturally in your summary and skills section.")
    if not suggestions:
        suggestions.append("You have strong keyword alignment—tailor your opening summary to this specific role.")
    return JobDescriptionMatch(target_role=target_role, score=score, matched_skills=matched, missing_skills=missing, suggestions=suggestions)

def extract_projects(text: str, description: str | None = None, job_match: JobDescriptionMatch | None = None) -> List[ProjectMatch]:
    project_lines = section_text(text, PROJECT_HEADINGS).splitlines()
    keywords = []
    if job_match and description:
        keywords = extract_skills(description) or ROLE_REQUIREMENTS.get(job_match.target_role, [])
    projects = []
    current_title, current_content = None, []

    def save_project():
        if not current_title:
            return
        content = " ".join(current_content)
        matched = [keyword for keyword in keywords if contains_skill(content, keyword)]
        projects.append(ProjectMatch(title=current_title, skills=extract_skills(content), matched_keywords=matched))

    for raw_line in project_lines:
        line = raw_line.strip()
        # PDF text has no font hierarchy. Accept short, standalone title lines as
        # well as the common "Project | Technologies" format, excluding bullets,
        # labels, dates, links, and achievement sentences.
        is_title = bool(line) and not re.match(r"^[•·▪\-–]", line) and (
            "|" in line or (
                len(line) <= 100 and len(line.split()) <= 12
                and not re.search(r"[.!?:;]$", line)
                and not re.match(r"(?i)^(?:built|developed|created|implemented|designed|used|using|led|improved|deployed|achieved|increased|reduced|technologies|tech stack|stack|tools|https?://|www\.|\d)", line)
            )
        )
        if is_title:
            save_project()
            current_title = line.split("|", 1)[0].strip()
            current_content = [line]
        elif current_title and line:
            current_content.append(line)
    save_project()
    return projects[:8]

def analyze(text: str, job_description: str | None = None) -> ResumeAnalysis:
    skills = extract_skills(text)
    education = get_section(text, EDUCATION_HEADINGS)
    experience = get_section(text, EXPERIENCE_HEADINGS) or get_section(text, PROJECT_HEADINGS)
    certifications = get_section(text, CERTIFICATION_HEADINGS)
    issues = []
    if len(skills) < 5: issues.append("Add more role-specific technical skills so recruiters can find you more easily.")
    if not education: issues.append("Include a clearly labelled education section with your degree and institution.")
    if not experience: issues.append("Add project or experience bullets that show impact with measurable outcomes.")
    if not certifications: issues.append("Consider adding relevant certifications, coursework, or credentials.")
    score = min(100, 35 + min(len(skills), 12) * 4 + (10 if education else 0) + (15 if experience else 0) + (8 if certifications else 0))
    job_match = match_job_description(skills, job_description, experience) if job_description and job_description.strip() else None
    projects = extract_projects(text, job_description, job_match)
    project_matches = [project for project in projects if project.matched_keywords]
    top = role_matches(skills)
    if job_match and job_match.target_role:
        top = [RoleMatch(title=job_match.target_role, match=job_match.score, matched_skills=job_match.matched_skills, missing_skills=job_match.missing_skills[:3])]
    role_label = "role match" if len(top) == 1 else "role matches"
    summary = f"Detected {len(skills)} relevant skills and identified {len(top)} {role_label}."
    if job_match:
        if job_match.matched_skills or job_match.missing_skills:
            summary += f" Your job-description ATS match is {job_match.score}%."
        else:
            summary += " We couldn't calculate a job-description keyword match because no skill requirements or recognizable role were detected."
    return ResumeAnalysis(candidate_name=candidate_name(text), skills=skills, education=education, experience=experience, certifications=certifications, recommendations=top, score=score, issues=issues, summary=summary, job_match=job_match, related_projects=project_matches, projects=projects)

@app.post("/api/analyze", response_model=ResumeAnalysis)
async def analyze_resume(file: UploadFile = File(...), job_description: str | None = Form(None, max_length=20000)):
    if not (file.filename or "").lower().endswith(".pdf"): raise HTTPException(status_code=400, detail="Please upload a PDF resume.")
    contents = await file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES: raise HTTPException(status_code=400, detail="Please upload a PDF smaller than 4 MB.")
    return analyze(extract_pdf_text(contents), job_description)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "nlp_model_loaded": NLP is not None}
