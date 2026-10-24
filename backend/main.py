"""FastAPI service for extracting useful signals from PDF resumes."""
from datetime import datetime, timezone
from io import BytesIO
import re
from typing import List

import PyPDF2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
except Exception:
    NLP = None

if __package__:
    from .roles import (
        SKILLS, ROLE_REQUIREMENTS, ROLE_ALIASES, extract_skills as canonical_extract_skills,
        detect_role, get_role_catalog, rank_role_matches, suggest_projects, training_metadata,
    )
else:
    from roles import (
        SKILLS, ROLE_REQUIREMENTS, ROLE_ALIASES, extract_skills as canonical_extract_skills,
        detect_role, get_role_catalog, rank_role_matches, suggest_projects, training_metadata,
    )

PROJECT_HEADINGS = ["projects", "project experience", "personal projects", "academic projects", "selected projects", "key projects", "relevant projects", "technical projects"]
EDUCATION_HEADINGS = ["education", "academic background", "education and training", "education & training", "academic qualifications", "educational qualifications"]
EXPERIENCE_HEADINGS = ["experience", "work experience", "professional experience", "employment history", "work history", "internships", "internship experience"]
CERTIFICATION_HEADINGS = ["certifications", "certificates", "licenses", "certifications and courses", "certifications & courses", "courses and certifications"]
SKILL_HEADINGS = ["skills", "technical skills", "core skills", "key skills", "professional skills", "skills and tools", "skills & tools", "technical competencies", "core competencies"]
SUMMARY_HEADINGS = ["summary", "professional summary", "profile", "professional profile", "career objective", "objective", "about me"]
OTHER_HEADINGS = ["achievements", "awards", "awards and achievements", "hackathons", "hackathon experience", "publications", "interests", "languages", "volunteering", "volunteer experience", "activities", "extracurricular activities", "references"]
ALL_SECTION_HEADINGS = EDUCATION_HEADINGS + EXPERIENCE_HEADINGS + PROJECT_HEADINGS + CERTIFICATION_HEADINGS + SKILL_HEADINGS + SUMMARY_HEADINGS + OTHER_HEADINGS
SECTION_HEADINGS = "|".join(re.escape(name) for name in ALL_SECTION_HEADINGS)
# Stack annotations contain file formats and tools beyond the scoring vocabulary.
# These terms help identify layout; they do not add skills to the returned analysis.
PROJECT_STACK_TERMS = ["React.js", "ReactJS", "Next.js", "Node.js", "NLP", "OCR", "RAG", "Generative AI", "Streamlit", "JSON", "XML", "YAML", "ZIP/7Z", "ELK Stack", "Elasticsearch", "Kibana", "Figma", "FigJam", "Jupyter Notebook", "VS Code", "REST APIs", "Rule-Based Validation", "Scikit-learn"]
BULLET_PATTERN = r"^[ \t]*[•·▪●◦‣\-–—][ \t]*"
PROJECT_ACTION_PATTERN = r"(?i)^(?:built|developed|created|implemented|designed|used|using|led|improved|deployed|achieved|increased|reduced|automated|analyzed|analysed|configured|integrated|added|performed|calculated|validated|loaded|collaborated|worked|maintained|documented|planned|scoped|curated|mapped|grouped|extracted|supported|delivered|engineered|optimized|tested|wrote|generated|processed|enabled|provided|responsible|worked|this|the|a|an)\b"
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
    domain: str | None = None
    profile_examples: int = 0
    explanation: str = ""

class TrainingInfo(BaseModel):
    method: str
    source_count: int
    unique_count: int
    duplicate_count: int
    trained_roles: List[str]
    limitations: List[str]

class RoleOption(BaseModel):
    title: str
    domain: str
    profile_examples: int

class RoleCatalog(BaseModel):
    roles: List[RoleOption]
    training: TrainingInfo

class SuggestedProject(BaseModel):
    title: str
    description: str
    skills: List[str]
    missing_skills: List[str]

class JobDescriptionMatch(BaseModel):
    target_role: str | None = None
    score: int
    matched_skills: List[str]
    missing_skills: List[str]
    suggestions: List[str]
    basis: str = "job_description"

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
    score_basis: str = "section_completeness"
    structure_checks: dict[str, bool] = Field(default_factory=dict)
    issues: List[str]
    summary: str
    job_match: JobDescriptionMatch | None = None
    related_projects: List[ProjectMatch] = Field(default_factory=list)
    projects: List[ProjectMatch] = Field(default_factory=list)
    selected_role: str | None = None
    role_source: str = "automatic"
    domain: str | None = None
    training: TrainingInfo
    recommended_projects: List[SuggestedProject] = Field(default_factory=list)

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
    if skill in SKILLS:
        return skill in canonical_extract_skills(text)
    escaped = re.escape(skill).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9+#]){escaped}(?![a-z0-9+#])", text, re.IGNORECASE))

def extract_skills(text: str) -> List[str]:
    return canonical_extract_skills(text)

def _clean_heading(line: str) -> str:
    """Recognize standalone headings despite PDF spacing and Markdown decoration."""
    line = re.sub(BULLET_PATTERN, "", line.strip())
    line = re.sub(r"^#{1,6}\s*", "", line).strip(" *_:\t")
    return re.sub(r"\s+", " ", line).casefold()


def section_text(text: str, names: List[str]) -> str:
    requested = {_clean_heading(name) for name in names}
    headings = {_clean_heading(name) for name in ALL_SECTION_HEADINGS} | requested
    blocks, current = [], None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        heading = _clean_heading(line)
        inline_content = ""
        if heading not in headings and ":" in line:
            label, content = line.split(":", 1)
            if _clean_heading(label) in headings:
                heading, inline_content = _clean_heading(label), content.strip()
        if heading in headings:
            if current is not None:
                blocks.append("\n".join(current))
            current = [] if heading in requested else None
            if current is not None and inline_content:
                current.append(inline_content)
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append("\n".join(current))
    return "\n".join(blocks)


def get_section(text: str, names: List[str]) -> List[str]:
    lines, inside_bullet = [], False
    for raw_line in section_text(text, names).splitlines():
        line = raw_line.strip()
        if not line or re.fullmatch(r"(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?", line, re.IGNORECASE):
            continue
        bullet = bool(re.match(BULLET_PATTERN, line))
        line = re.sub(BULLET_PATTERN, "", line).strip()
        if len(line) <= 2:
            continue
        new_entry = (
            inside_bullet and re.search(r"[.!?]$", lines[-1])
            and not re.search(r"[.!?]$", line)
            and all(word[0].isupper() or not word[0].isalpha() for word in line.split())
        )
        if inside_bullet and not bullet and not new_entry:
            lines[-1] += " " + line
        else:
            lines.append(line)
        inside_bullet = bullet or (inside_bullet and not new_entry)
    return lines[:20]


def candidate_name(text: str) -> str | None:
    headings = set(ALL_SECTION_HEADINGS) | {"resume", "curriculum vitae", "cv"}
    for raw_line in text.splitlines()[:6]:
        line = re.sub(r"(?i)^name\s*:\s*", "", raw_line.strip()).split("|", 1)[0].strip()
        if not line or _clean_heading(line) in {"resume", "curriculum vitae", "cv"}:
            continue
        if _clean_heading(line) in headings:
            break
        words = line.split()
        if 2 <= len(words) <= 6 and len(line) <= 70 and all(
            any(char.isalpha() for char in word)
            and all(char.isalpha() or char in ".'-’" for char in word)
            for word in words
        ) and not re.search(r"(?i)\b(?:developer|engineer|analyst|designer|university|college|intern|manager|linkedin|github)\b", line):
            return line.title() if line.isupper() or line.islower() else line
    if NLP:
        doc = NLP(text[:800])
        return next((ent.text for ent in doc.ents if ent.label_ == "PERSON"), None)
    return None


def role_matches(skills: List[str], text: str = "") -> List[RoleMatch]:
    return [RoleMatch(**match) for match in rank_role_matches(skills, text)]


def target_role_from_description(description: str) -> str | None:
    return detect_role(description)


def _focus_match(role: str, skills: List[str], text: str) -> RoleMatch:
    ranked = rank_role_matches(skills, text, limit=len(ROLE_REQUIREMENTS))
    existing = next((item for item in ranked if item["title"] == role), None)
    if existing:
        return RoleMatch(**existing)
    catalog_entry = next(item for item in get_role_catalog() if item["title"] == role)
    return RoleMatch(
        title=role, match=0, matched_skills=[], missing_skills=ROLE_REQUIREMENTS[role][:3],
        domain=catalog_entry["domain"], profile_examples=catalog_entry["profile_examples"],
        explanation="No recognized requirements for this role were detected in the resume.",
    )


def match_job_description(skills: List[str], description: str, experience: List[str]) -> JobDescriptionMatch:
    target_role = target_role_from_description(description)
    normalized = re.sub(r"\s+", " ", description).strip(" .:;\t\r\n").casefold()
    title_only = target_role and normalized in {
        alias.casefold() for alias in [target_role] + ROLE_ALIASES.get(target_role, [])
    }
    description_skills = [] if title_only else extract_skills(description)
    required_skills = description_skills or ROLE_REQUIREMENTS.get(target_role, [])
    basis = "role_requirements" if not description_skills and required_skills else "job_description"
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
    if basis == "role_requirements":
        suggestions.insert(0, "No specific job skill list was supplied; this comparison uses the role's curated requirements.")
    return JobDescriptionMatch(target_role=target_role, score=score, matched_skills=matched, missing_skills=missing, suggestions=suggestions, basis=basis)

def _is_technology_line(line: str) -> bool:
    """Distinguish a stack annotation from a project title or achievement."""
    remaining = re.sub(r"(?i)^(?:technologies(?: used)?|tech stack|stack|tools|built with)\s*:\s*", "", line.strip())
    if not remaining or re.match(PROJECT_ACTION_PATTERN, remaining):
        return False
    terms = set(PROJECT_STACK_TERMS + extract_skills(remaining))
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.escape(term).replace(r"\ ", r"\s+")
        remaining = re.sub(rf"(?<![a-z0-9+#]){pattern}(?![a-z0-9+#])", " ", remaining, flags=re.IGNORECASE)
    remaining = re.sub(r"(?i)\b(?:and|with|v?\d+(?:\.\d+)*)\b", " ", remaining)
    return not re.sub(r"[\s,|/&()+.\-–—:]+", "", remaining)


def _project_title(line: str) -> str:
    line = re.sub(BULLET_PATTERN, "", line.strip())
    line = re.sub(r"^#{1,6}\s*|^\d+[.)]\s+", "", line).strip(" *")
    title = line.split("|", 1)[0].strip()
    # Dates are metadata whether on their own row or after the project title.
    title = re.sub(r"(?i)\s+(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+)?(?:19|20)\d{2}\b.*$", "", title).strip(" -–—|")
    if "|" not in line:
        for match in re.finditer(r"\s+", title):
            prefix, suffix = title[:match.start()].strip(), title[match.end():].strip()
            if len(prefix.split()) >= 2 and _is_technology_line(suffix) and not _is_technology_line(prefix):
                title = prefix
                break
    return title


def _is_project_date(line: str) -> bool:
    month = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
    date = rf"(?:{month}\s+)?(?:19|20)\d{{2}}"
    return bool(re.fullmatch(rf"(?i){date}(?:\s*[-–—]\s*(?:{date}|present|current|ongoing))?", line.strip()))


def _looks_like_project_title(line: str, following: str = "") -> bool:
    if _is_project_date(line):
        return False
    title = _project_title(line)
    if not title or len(title) > 150 or len(title.split()) > 18 or _is_technology_line(title):
        return False
    if re.match(PROJECT_ACTION_PATTERN, title) or re.search(r"[.!?:;]$", title):
        return False
    if re.match(r"(?i)^(?:technologies|tech stack|stack|tools|https?://|www\.|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+\d|\d)", title):
        return False
    if "|" in line:
        return True
    words = re.findall(r"[\w+#][\w+.#’'-]*", title)
    connectors = {"and", "or", "for", "of", "to", "in", "with", "a", "an", "the", "on", "by", "as"}
    if not words or not words[0][0].isupper():
        return False
    title_case = all(word[0].isupper() or word.casefold() in connectors for word in words)
    # Sentence-case names are common too. A following stack annotation or
    # achievement supplies the layout signal that capitalization cannot.
    followed_by_evidence = bool(following) and (
        _is_technology_line(following)
        or bool(re.match(BULLET_PATTERN, following))
        or bool(re.match(PROJECT_ACTION_PATTERN, following))
    )
    return title_case or (len(words) <= 12 and followed_by_evidence)


def extract_projects(text: str, description: str | None = None, job_match: JobDescriptionMatch | None = None, target_skills: List[str] | None = None) -> List[ProjectMatch]:
    project_lines = section_text(text, PROJECT_HEADINGS).splitlines()
    keywords = target_skills if target_skills is not None else []
    if target_skills is None and job_match and description:
        keywords = extract_skills(description) or ROLE_REQUIREMENTS.get(job_match.target_role, [])
    projects = []
    current_title, current_content, has_description = None, [], False

    def save_project():
        if not current_title:
            return
        content = " ".join(current_content)
        matched = [keyword for keyword in keywords if contains_skill(content, keyword)]
        projects.append(ProjectMatch(title=current_title, skills=extract_skills(content), matched_keywords=matched))

    for index, raw_line in enumerate(project_lines):
        line = raw_line.strip()
        if not line or re.fullmatch(r"(?i)(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?", line):
            continue
        following = next((part.strip() for part in project_lines[index + 1:] if part.strip()), "")
        wrapped_sentence = (
            current_title and has_description and "|" not in line
            and current_content and not re.search(r"[.!?;:]$", current_content[-1])
            and following and following[0].islower()
            and not re.match(BULLET_PATTERN, following)
        )
        if not wrapped_sentence and _looks_like_project_title(line, following):
            title = _project_title(line)
            if current_title and not has_description and not any(_is_technology_line(part) for part in current_content[1:]):
                # A long title may wrap before its stack or its first bullet.
                current_title += " " + title
                current_content.append(line)
            else:
                save_project()
                current_title, current_content, has_description = title, [line], False
        elif current_title:
            current_content.append(line)
            if not _is_technology_line(line) and not _is_project_date(line):
                has_description = True
    save_project()
    return projects[:8]


def analyze(text: str, job_description: str | None = None, target_role: str | None = None) -> ResumeAnalysis:
    target_role = target_role.strip() if target_role else None
    if target_role and target_role not in ROLE_REQUIREMENTS:
        raise HTTPException(status_code=422, detail="Choose a supported target role from the role selector.")
    skills = extract_skills(text)
    education = get_section(text, EDUCATION_HEADINGS)
    experience = get_section(text, EXPERIENCE_HEADINGS) or get_section(text, PROJECT_HEADINGS)
    certifications = get_section(text, CERTIFICATION_HEADINGS)
    job_match = match_job_description(skills, job_description, experience) if job_description and job_description.strip() else None
    top = role_matches(skills, text)
    active_role = target_role or (job_match.target_role if job_match else None) or (top[0].title if top else None)
    role_source = "selected" if target_role else "job_description" if job_match and job_match.target_role else "automatic"
    focus = _focus_match(active_role, skills, text) if active_role else None
    if focus and role_source != "automatic":
        top = [focus] + [item for item in top if item.title != active_role][:2]

    # Career goals and supplied job requirements are independent comparisons.
    # A selected goal controls project evidence and learning ideas even when a
    # pasted job description names a different role.
    if target_role:
        project_keywords = ROLE_REQUIREMENTS[active_role]
    elif job_match and (job_match.matched_skills or job_match.missing_skills):
        project_keywords = job_match.matched_skills + job_match.missing_skills
    else:
        project_keywords = ROLE_REQUIREMENTS.get(active_role, [])
    projects = extract_projects(text, job_description, job_match, target_skills=project_keywords)
    project_matches = [project for project in projects if project.matched_keywords]
    issues = []
    if len(skills) < 5:
        issues.append("Add more role-specific technical skills so recruiters can find relevant evidence.")
    if not education:
        issues.append("Include a clearly labelled education section with your degree and institution.")
    if not experience:
        issues.append("Add project or experience bullets that show impact with measurable outcomes.")
    if focus and focus.missing_skills:
        issues.append(f"For {active_role}, build and document evidence of {', '.join(focus.missing_skills)} where relevant to your goal.")
    if not projects and active_role:
        issues.append("Use a clear Projects heading and a separate title for each project so relevant work can be identified.")
    if not certifications:
        issues.append("Relevant coursework or credentials can add supporting context when useful for your target role.")
    structure_checks = {
        "skills": bool(skills),
        "education": bool(education),
        "experience_or_project_evidence": bool(experience),
        "project_details": bool(projects),
        "summary": bool(section_text(text, SUMMARY_HEADINGS).strip()),
    }
    # Section completeness is deliberately separate from role coverage. A long
    # keyword list cannot earn credit for absent education, evidence or summary.
    score = sum(structure_checks.values()) * 20
    role_label = "role match" if len(top) == 1 else "role matches"
    summary = f"Detected {len(skills)} relevant skills and identified {len(top)} {role_label}."
    if active_role:
        summary += f" Analysis focus: {active_role}."
    if job_match:
        if job_match.matched_skills or job_match.missing_skills:
            if job_match.basis == "role_requirements":
                summary += f" Curated role requirement coverage is {job_match.score}%; no specific job skill list was supplied."
            else:
                summary += f" Job-description keyword coverage is {job_match.score}%."
        else:
            summary += " We couldn't calculate a job-description keyword match because no skill requirements or recognizable role were detected."
    return ResumeAnalysis(
        candidate_name=candidate_name(text), skills=skills, education=education,
        experience=experience, certifications=certifications, recommendations=top,
        score=score, structure_checks=structure_checks, issues=issues, summary=summary, job_match=job_match,
        related_projects=project_matches, projects=projects, selected_role=active_role,
        role_source=role_source, domain=focus.domain if focus else None,
        training=TrainingInfo(**training_metadata()),
        recommended_projects=[SuggestedProject(**project) for project in suggest_projects(active_role, skills)],
    )


@app.get("/api/roles", response_model=RoleCatalog)
async def available_roles():
    return RoleCatalog(roles=[RoleOption(**role) for role in get_role_catalog()], training=TrainingInfo(**training_metadata()))


@app.post("/api/analyze", response_model=ResumeAnalysis)
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str | None = Form(None, max_length=20000),
    target_role: str | None = Form(None, max_length=100),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF resume.")
    contents = await file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="Please upload a PDF smaller than 4 MB.")
    return analyze(extract_pdf_text(contents), job_description, target_role)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat(), "nlp_model_loaded": NLP is not None, "supported_roles": len(ROLE_REQUIREMENTS), "role_profiles_loaded": training_metadata()["unique_count"] > 0}
