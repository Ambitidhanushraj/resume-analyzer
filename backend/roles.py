"""Curated skill coverage with small, optional, locally learned ranking profiles.

Role percentages always mean canonical requirement coverage. Labeled example
frequencies influence ordering, not the reported coverage or candidate history.
"""
import json
import math
from pathlib import Path
import re


# Canonical strings are the only vocabulary allowed in the persisted profiles.
SKILL_ALIASES = {
    "python": [], "java": [], "c++": ["cpp", "c++11", "c++14", "c++17", "c++20", "c++23"],
    "c#": ["csharp", "c sharp"], "c": [],
    "javascript": ["java script", "js"], "typescript": ["type script", "ts"],
    "react": ["react.js", "reactjs"], "next.js": ["nextjs", "next js"],
    "node.js": ["nodejs", "node js"], "html": ["html5"], "css": ["css3"],
    "tailwind": ["tailwindcss", "tailwind css"],
    "sql": [], "mongodb": ["mongo db"], "postgresql": ["postgres"], "mysql": [],
    "fastapi": ["fast api"], "flask": [], "django": [],
    "aws": ["amazon web services"], "azure": ["microsoft azure"],
    "gcp": ["google cloud", "google cloud platform"], "docker": [],
    "kubernetes": ["k8s"], "git": [], "github": [], "linux": ["unix", "linux/unix"],
    "figma": [], "figjam": ["fig jam"], "rest api": ["rest apis", "restful api", "restful apis", "rest endpoints"],
    "graphql": [], "machine learning": ["ml"], "deep learning": [],
    "data analysis": ["data analytics"], "data visualization": ["data visualisation"],
    "power bi": ["powerbi", "microsoft power bi"], "tableau": [],
    "pandas": [], "numpy": [], "scikit-learn": ["scikit learn", "sklearn"],
    "tensorflow": [], "pytorch": [], "excel": ["microsoft excel", "ms excel"],
    "agile": ["scrum"], "project management": [], "communication": [],
    "leadership": [], "problem solving": ["problem-solving"],
    "data structures": ["dsa", "data structures and algorithms"], "algorithms": ["dsa"],
    "object-oriented programming": ["oop", "object oriented programming"],
    "design patterns": [], "multithreading": ["multi-threading", "multi threading"],
    "memory management": [], "stl": ["standard template library"], "boost": [],
    "rtos": ["real-time operating system", "real time operating system"],
    "tcp/ip": ["tcp ip"], "udp": [], "embedded systems": ["embedded development"],
    "unit testing": ["unit tests"], "automated testing": ["test automation", "automation testing"],
    "selenium": [], "playwright": [], "pytest": [], "junit": [],
    "ci/cd": ["ci cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "jenkins": [], "azure devops": [], "bamboo": [], "terraform": [],
    "ansible": [], "bash": ["shell scripting"],
    "elasticsearch": ["elastic search"], "kibana": [], "elk stack": ["elk"],
    "logstash": [], "log analysis": ["production log analysis", "production logs"],
    "monitoring": ["observability", "application monitoring", "production monitoring"],
    "alerting": ["alerts", "monitoring rules"], "prometheus": [], "grafana": [],
    "opentelemetry": ["open telemetry", "otel"],
    "automation": ["workflow automation", "automations", "automated workflows"],
    "data validation": ["data-quality checks", "data quality checks", "rule-based validation", "workflow validation"],
    "data cleaning": ["data cleansing"], "streamlit": [], "json": [],
    "etl": ["extract transform load", "extract, transform, load"],
    "airflow": ["apache airflow"], "spark": ["apache spark", "pyspark"],
    "dbt": [], "data modeling": ["data modelling", "dimensional modeling", "dimensional modelling"],
    "data warehousing": ["data warehouse", "data warehouses"], "snowflake": [], "bigquery": ["big query"],
    "dax": ["data analysis expressions"], "power query": [],
    "business intelligence": ["bi"], "kpi": ["kpis", "key performance indicators", "key business metrics"],
    "statistics": ["statistical analysis"], "a/b testing": ["ab testing", "a-b testing", "a/b tests"],
    "product analytics": ["product analysis"], "requirements analysis": ["requirements gathering", "business requirements"],
    "stakeholder management": [], "process mapping": ["business process mapping"],
    "user research": ["ux research", "usability research"], "user flows": ["user flow", "flow mapping"],
    "wireframing": ["wireframes", "wireframe"], "prototyping": ["prototypes", "prototype"],
    "usability testing": ["usability tests"], "accessibility": ["wcag"],
    "ui design": ["user interface design", "interface design"],
    "content analysis": ["content analyst", "web app breakdown", "web application analysis"],
    "screenshot curation": [], "ui pattern tagging": ["ui element tagging", "ui element tags", "ui pattern collection"],
    "quality assurance": ["quality checks", "qa"], "test planning": ["test plans", "test cases"],
    "nlp": ["natural language processing"],
    "rag": ["retrieval-augmented generation", "retrieval augmented generation"],
    "generative ai": ["generativeai", "gen ai", "genai"], "llm": ["llms", "large language model", "large language models"],
    "ocr": ["optical character recognition"], "prompt engineering": [],
    "model evaluation": ["llm evaluation"], "vector databases": ["vector database", "vector search"],
    "cybersecurity": ["cyber security", "information security"],
    "siem": ["security information and event management"],
    "iam": ["identity and access management"], "networking": ["computer networks"],
    "incident response": [], "threat detection": [],
}
SKILLS = list(SKILL_ALIASES)

# Keep the six original requirement sets stable: existing coverage scores retain
# their meaning when no profile was trained for that role.
ROLE_REQUIREMENTS = {
    "Frontend Developer": ["react", "javascript", "typescript", "html", "css", "figma", "git"],
    "Backend Developer": ["python", "node.js", "fastapi", "django", "sql", "rest api", "docker"],
    "Full Stack Developer": ["react", "javascript", "python", "node.js", "sql", "git", "docker"],
    "Data Analyst": ["python", "sql", "excel", "power bi", "tableau", "pandas", "data analysis"],
    "Machine Learning Engineer": ["python", "machine learning", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch"],
    "Cloud Engineer": ["aws", "azure", "gcp", "docker", "kubernetes", "linux", "python"],
    "Software Engineer": ["python", "java", "data structures", "algorithms", "object-oriented programming", "git", "unit testing", "rest api"],
    "C++ / Embedded Developer": ["c++", "stl", "object-oriented programming", "data structures", "multithreading", "memory management", "linux", "rtos"],
    "UI/UX Designer": ["figma", "user research", "user flows", "wireframing", "prototyping", "usability testing", "accessibility", "ui design"],
    "Content Analyst": ["content analysis", "screenshot curation", "user flows", "ui pattern tagging", "figma", "data validation", "quality assurance"],
    "Business Intelligence Developer": ["sql", "power bi", "tableau", "dax", "data modeling", "etl", "kpi", "business intelligence"],
    "Observability Engineer": ["elasticsearch", "kibana", "elk stack", "log analysis", "monitoring", "alerting", "prometheus", "grafana"],
    "Automation Engineer": ["python", "automation", "data validation", "json", "streamlit", "automated testing", "ci/cd"],
    "AI Engineer": ["python", "nlp", "rag", "generative ai", "fastapi", "prompt engineering", "model evaluation", "vector databases"],
    "Data Engineer": ["python", "sql", "etl", "airflow", "spark", "data modeling", "data warehousing", "data validation"],
    "QA Engineer": ["quality assurance", "test planning", "automated testing", "selenium", "playwright", "pytest", "unit testing", "git"],
    "DevOps Engineer": ["linux", "docker", "kubernetes", "ci/cd", "terraform", "jenkins", "monitoring", "bash"],
    "Product Analyst": ["sql", "product analytics", "statistics", "a/b testing", "kpi", "data visualization", "excel"],
    "Business Analyst": ["requirements analysis", "stakeholder management", "process mapping", "excel", "sql", "communication", "business intelligence"],
    "Security Analyst": ["cybersecurity", "siem", "iam", "networking", "incident response", "threat detection", "log analysis"],
}
ROLE_DOMAINS = {
    "Frontend Developer": "Web development", "Backend Developer": "Web development",
    "Full Stack Developer": "Web development", "Data Analyst": "Data and analytics",
    "Machine Learning Engineer": "AI and machine learning", "Cloud Engineer": "Cloud and infrastructure",
    "Software Engineer": "Software engineering", "C++ / Embedded Developer": "Systems and embedded",
    "UI/UX Designer": "Design", "Content Analyst": "Content and interface analysis",
    "Business Intelligence Developer": "Data and analytics", "Observability Engineer": "Reliability and monitoring",
    "Automation Engineer": "Automation and validation", "AI Engineer": "AI and machine learning",
    "Data Engineer": "Data engineering", "QA Engineer": "Software quality",
    "DevOps Engineer": "Cloud and infrastructure", "Product Analyst": "Product analytics",
    "Business Analyst": "Business analysis", "Security Analyst": "Cybersecurity",
}
ROLE_ALIASES = {
    "Frontend Developer": ["frontend", "front end", "front-end developer", "frontend engineer"],
    "Backend Developer": ["backend developer", "back end developer", "back-end developer", "backend engineer"],
    "Full Stack Developer": ["full stack", "full-stack", "fullstack"],
    "Data Analyst": ["data analytics", "data analyst"],
    "Machine Learning Engineer": ["machine learning engineer", "ml engineer"],
    "Cloud Engineer": ["cloud engineer", "cloud engineering"],
    "Software Engineer": ["software engineer", "software developer", "software engineering"],
    "C++ / Embedded Developer": ["c++ developer", "c++ software", "cpp developer", "embedded developer", "embedded engineer", "embedded development"],
    "UI/UX Designer": ["ui/ux designer", "ui ux designer", "ux designer", "ui designer", "product designer", "ux design"],
    "Content Analyst": ["content analyst", "content analysis"],
    "Business Intelligence Developer": ["business intelligence", "bi developer", "bi analyst"],
    "Observability Engineer": ["observability engineer", "observability", "elk engineer", "production monitoring", "application monitoring"],
    "Automation Engineer": ["automation engineer", "python automation", "workflow automation", "python automations"],
    "AI Engineer": ["ai engineer", "ai engineering", "ai systems", "generative ai engineer"],
    "Data Engineer": ["data engineer", "data engineering"],
    "QA Engineer": ["qa engineer", "quality assurance engineer", "test engineer", "sdet"],
    "DevOps Engineer": ["devops engineer", "devops engineering", "site reliability engineer", "sre"],
    "Product Analyst": ["product analyst", "product analytics"],
    "Business Analyst": ["business analyst", "business analysis"],
    "Security Analyst": ["security analyst", "soc analyst", "cybersecurity analyst", "security operations"],
}
MODEL_PATH = Path(__file__).parent / "data" / "role_profiles.json"
PROFILE_METHOD = "Deduplicated, labeled canonical-skill frequency profiles with curated role requirements"
PROFILE_LIMITATIONS = [
    "Small sample of tailored resume variants from one candidate; examples are not independent career histories.",
    "No held-out evaluation or broad model generalization is claimed.",
    "Keyword coverage and learned ranking are guidance, not hiring probabilities or verified experience.",
    "Roles without labeled examples use curated requirements only.",
]


def _phrase_pattern(phrase):
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return rf"(?<![a-z0-9+#.]){escaped}(?![a-z0-9+#])"


_SKILL_PATTERNS = {
    skill: re.compile("|".join(_phrase_pattern(alias) for alias in [skill] + aliases), re.I)
    for skill, aliases in SKILL_ALIASES.items()
}


def extract_skills(text):
    """Match canonical names and aliases without substring matches for C/JS/ML/etc."""
    return [skill for skill, pattern in _SKILL_PATTERNS.items() if pattern.search(text or "")]


def _role_scope(text):
    # A resume project named "AI Engineer" is not a career objective. Prefer the
    # summary when present and otherwise consider only the introductory text.
    summary = re.search(r"(?im)^[ \t]*(?:professional summary|summary|profile|career objective|objective)[ \t]*:?[ \t]*$", text)
    scope = text[summary.end():] if summary else text
    scope = re.split(r"(?im)^[ \t]*(?:education(?: and training)?|technical skills|skills|experience|work experience|projects|personal projects|academic projects|certifications)[ \t]*:?[ \t]*$", scope, maxsplit=1)[0]
    return scope[:1800]


def detect_role(text):
    scope = _role_scope(text or "")
    candidates = []
    for index, (role, aliases) in enumerate(ROLE_ALIASES.items()):
        for alias in [role] + aliases:
            for match in re.finditer(_phrase_pattern(alias), scope, re.I):
                # Job-seeking intent outweighs past internship titles or tool
                # mentions in the summary, without reading project titles.
                preceding = scope[max(0, match.start() - 120):match.start()]
                intent = bool(re.search(r"(?i)(?:seeking|targeting|interested in|aspiring|candidate for|apply(?:ing)? for)[^.\n]*$", preceding.replace("\n", " ")))
                score = (10 if intent else 0) + (3 if alias.lower() == role.lower() else 1)
                candidates.append((score, -match.start(), -index, role))
    return max(candidates)[3] if candidates else None


def _load_profiles():
    """Reject missing/malformed artifacts atomically and use curated fallbacks."""
    try:
        data = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return None
        counts = [data.get(key) for key in ("source_count", "unique_count", "duplicate_count")]
        if any(type(value) is not int or value < 0 for value in counts):
            return None
        if counts[0] != counts[1] + counts[2]:
            return None
        profiles = data.get("roles")
        if not isinstance(profiles, dict):
            return None
        for role, profile in profiles.items():
            if role not in ROLE_REQUIREMENTS or not isinstance(profile, dict):
                return None
            total = profile.get("example_count")
            frequencies = profile.get("skill_counts")
            if type(total) is not int or not 0 < total <= counts[1] or not isinstance(frequencies, dict):
                return None
            if not frequencies or any(skill not in ROLE_REQUIREMENTS[role] or type(count) is not int or not 0 < count <= total for skill, count in frequencies.items()):
                return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def training_metadata():
    data = _load_profiles()
    if not data:
        return {
            "method": "Curated canonical-skill coverage; no learned profile available",
            "source_count": 0, "unique_count": 0, "duplicate_count": 0,
            "trained_roles": [], "limitations": list(PROFILE_LIMITATIONS),
        }
    return {
        "method": PROFILE_METHOD,
        "source_count": data["source_count"], "unique_count": data["unique_count"],
        "duplicate_count": data["duplicate_count"],
        "trained_roles": [role for role in ROLE_REQUIREMENTS if role in data["roles"]],
        "limitations": list(PROFILE_LIMITATIONS),
    }


def get_role_catalog():
    profiles = (_load_profiles() or {}).get("roles", {})
    return [{"title": role, "domain": ROLE_DOMAINS[role], "profile_examples": profiles.get(role, {}).get("example_count", 0)} for role in ROLE_REQUIREMENTS]


def rank_role_matches(skills, text="", limit=3):
    known = set(skills)
    profiles = (_load_profiles() or {}).get("roles", {})
    intended = detect_role(text)
    frequency = {skill: sum(skill in requirements for requirements in ROLE_REQUIREMENTS.values()) for skill in SKILLS}
    results = []
    for role, requirements in ROLE_REQUIREMENTS.items():
        matched = [skill for skill in requirements if skill in known]
        if not matched:
            continue
        missing = [skill for skill in requirements if skill not in known]
        coverage = len(matched) / len(requirements)
        # Common Python/Git evidence contributes less to ranking than domain
        # tools. Keep the displayed match strictly unweighted coverage.
        weights = {skill: 1 + math.log((1 + len(ROLE_REQUIREMENTS)) / (1 + frequency[skill])) for skill in requirements}
        domain_coverage = sum(weights[skill] for skill in matched) / sum(weights.values())
        ranking = .55 * coverage + .45 * domain_coverage
        profile = profiles.get(role, {})
        learned_counts = profile.get("skill_counts", {})
        if learned_counts and matched:
            # Only this role's canonical requirements are present in a learned
            # profile. Shared internship skills cannot expand its requirements.
            learned_coverage = sum(count * weights[skill] for skill, count in learned_counts.items() if skill in known) / sum(count * weights[skill] for skill, count in learned_counts.items())
            ranking += .12 * learned_coverage
        if intended == role and matched:
            ranking += .18
        explanation = f"{len(matched)} of {len(requirements)} curated requirements found; domain-specific skills influence ranking."
        if learned_counts:
            explanation += f" Ranking also uses canonical-skill frequencies from {profile['example_count']} labeled example(s)."
        if intended == role:
            explanation += " Introductory career intent matches this role."
        result = {
            "title": role, "match": round(coverage * 100), "matched_skills": matched,
            "missing_skills": missing[:3], "domain": ROLE_DOMAINS[role],
            "profile_examples": profile.get("example_count", 0), "explanation": explanation,
        }
        results.append((ranking, len(matched), result))
    results.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [result for _, _, result in results[:max(0, limit)]]


# These are future project ideas, never statements about the uploaded resume.
PROJECT_TEMPLATES = {
    "Frontend Developer": [("Accessible component gallery", "Build responsive components and test keyboard interaction.", ["react", "typescript", "css"]), ("Responsive task interface", "Implement a task board with filtering and clear empty states.", ["javascript", "html", "css"])],
    "Backend Developer": [("Validated task API", "Build documented CRUD endpoints with validation and database persistence.", ["python", "fastapi", "sql"]), ("Containerized service", "Add health checks and reproducible startup to a small API.", ["rest api", "docker"])],
    "Full Stack Developer": [("Issue tracking application", "Connect a React interface to a documented database-backed API.", ["react", "javascript", "python", "sql"]), ("Team workflow portal", "Create a small portal with API validation and a repeatable deployment.", ["node.js", "git", "docker"])],
    "Data Analyst": [("Public dataset quality audit", "Clean a public dataset and explain missing values, duplicates, and analytical limits.", ["python", "pandas", "data analysis"]), ("Business metrics dashboard", "Compute documented metrics and reconcile dashboard totals with SQL.", ["sql", "excel", "tableau"])],
    "Machine Learning Engineer": [("Reproducible prediction baseline", "Compare a simple baseline with a trained model using a held-out dataset.", ["python", "pandas", "scikit-learn"]), ("Model evaluation report", "Measure model errors and document dataset limitations and leakage checks.", ["machine learning", "numpy", "pytorch"])],
    "Cloud Engineer": [("Cloud service deployment lab", "Deploy a containerized service with health checks and a documented rollback.", ["aws", "docker", "linux"]), ("Cluster operations lab", "Practice resource limits, service discovery, and failure recovery in a test cluster.", ["kubernetes", "python"])],
    "Software Engineer": [("Tested service library", "Implement a small library with clear interfaces and automated unit tests.", ["python", "object-oriented programming", "unit testing"]), ("Algorithm tradeoff explorer", "Compare data structures with reproducible correctness and performance checks.", ["java", "data structures", "algorithms"])],
    "C++ / Embedded Developer": [("Bounded sensor buffer", "Implement a bounded buffer with explicit ownership and concurrency tests.", ["c++", "stl", "memory management", "multithreading"]), ("Embedded scheduler simulation", "Simulate periodic tasks and document timing and resource constraints.", ["c++", "rtos", "linux"])],
    "UI/UX Designer": [("Accessible onboarding prototype", "Research an onboarding problem, map user flows, and test a prototype with consent.", ["figma", "user research", "user flows", "prototyping"]), ("Usability review case study", "Document evidence, accessibility checks, and iteration decisions for a sample interface.", ["wireframing", "usability testing", "accessibility"])],
    "Content Analyst": [("Interface pattern evidence library", "Curate permitted screenshots, tag UI patterns, and record missing states honestly.", ["screenshot curation", "ui pattern tagging", "figma"]), ("Content consistency audit", "Review a public sample flow for labeling, sequence, and evidence consistency.", ["content analysis", "user flows", "quality assurance"])],
    "Business Intelligence Developer": [("Reconciled KPI model", "Model a public dataset and reconcile dashboard metrics against SQL queries.", ["sql", "data modeling", "power bi", "dax"]), ("Reporting pipeline lab", "Build a repeatable load and document metric definitions and refresh checks.", ["etl", "tableau", "kpi"])],
    "Observability Engineer": [("Application monitoring lab", "Instrument a sample application and create dashboards and actionable alerts.", ["elasticsearch", "kibana", "monitoring", "alerting"]), ("Incident investigation exercise", "Generate synthetic service failures and document evidence and alert quality.", ["log analysis", "prometheus", "grafana"])],
    "Automation Engineer": [("Structured data validation pipeline", "Automate validation of synthetic JSON inputs and report clear failure reasons.", ["python", "json", "data validation", "automation"]), ("Repeatable workflow test harness", "Add regression checks and a simple inspection interface to an automated workflow.", ["automated testing", "ci/cd", "streamlit"])],
    "AI Engineer": [("Grounded document assistant", "Build retrieval over public documents and evaluate answer grounding and abstention.", ["python", "rag", "fastapi", "model evaluation"]), ("Prompt evaluation bench", "Compare prompts against a fixed test set and document failure modes.", ["generative ai", "prompt engineering", "nlp"])],
    "Data Engineer": [("Validated batch data pipeline", "Load public data with schema checks, deduplication, and documented lineage.", ["python", "sql", "etl", "data validation"]), ("Warehouse modeling lab", "Create a small dimensional model with scheduled transformations and checks.", ["airflow", "data modeling", "data warehousing"])],
    "QA Engineer": [("Web application regression suite", "Write risk-based test cases and browser checks for a sample application.", ["test planning", "playwright", "automated testing"]), ("API quality test harness", "Test validation failures, boundary cases, and deterministic API behavior.", ["pytest", "unit testing", "quality assurance"])],
    "DevOps Engineer": [("Deployment and recovery lab", "Create a container pipeline and practice rollback and failed health checks.", ["docker", "ci/cd", "jenkins", "linux"]), ("Infrastructure reproducibility lab", "Provision a disposable environment and document monitoring and cleanup.", ["terraform", "kubernetes", "monitoring"])],
    "Product Analyst": [("Product funnel investigation", "Analyze a public or synthetic event dataset and document metric definitions.", ["sql", "product analytics", "kpi"]), ("Experiment analysis notebook", "Simulate an A/B experiment with assumptions and uncertainty clearly stated.", ["a/b testing", "statistics", "data visualization"])],
    "Business Analyst": [("Requirements and process case study", "Map a sample process, define requirements, and trace them to acceptance checks.", ["requirements analysis", "process mapping", "communication"]), ("Decision-support workbook", "Document stakeholder questions, metric definitions, and evidence limitations.", ["excel", "sql", "stakeholder management"])],
    "Security Analyst": [("Synthetic security log investigation", "Analyze synthetic logs in a safe lab and document evidence and escalation criteria.", ["siem", "log analysis", "threat detection"]), ("Access review exercise", "Review fictional access records against a documented least-privilege policy.", ["iam", "cybersecurity", "incident response"])],
}


def suggest_projects(role, skills):
    known = set(skills)
    return [{"title": title, "description": "Suggested learning project: " + description, "skills": list(required), "missing_skills": [skill for skill in required if skill not in known]} for title, description, required in PROJECT_TEMPLATES.get(role, [])]
