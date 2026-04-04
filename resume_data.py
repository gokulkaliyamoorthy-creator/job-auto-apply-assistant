RESUME = {
    "name": "Gokul Kaliyamoorthy",
    "email": "gokulkaliyamoorthy@gmail.com",
    "phone": "+91 8489122277",
    "phone_alt": "8489122277",
    "location": "Villupuram, Tamil Nadu, India",
    "current_city": "Bangalore",
    "preferred_locations": "Chennai, Bangalore",
    "title": "AI/ML Engineer",
    "total_experience": "9",
    "relevant_experience": "5",
    "current_company": "Boeing India Private Limited",
    "current_designation": "Programmer Analyst Level 3",
    "previous_company": "BNP Paribas India",
    "previous_designation": "Software Engineer",
    "education": "B.E. Computer Science and Engineering",
    "college": "Sri Sairam Engineering College, Chennai",
    "graduation_year": "2017",
    "notice_period": "2 Months",
    "notice_period_days": "60",
    "current_ctc": "30",
    "current_ctc_lpa": "30 LPA",
    "fixed_ctc": "28.7",
    "variable_ctc": "1.3",
    "expected_ctc": "40",
    "expected_ctc_lpa": "40 LPA",
    "gender": "Male",
    "marital_status": "Single",
    "dob": "",
    "languages": "English, Tamil",
    "willing_to_relocate": "Yes",
    "linkedin": "linkedin.com/in/gokul-kaliyamoorthy-952a1a123",
    "github": "",
    "portfolio": "",
    "skills": [
        "Generative AI", "Deep Learning", "Machine Learning",
        "Natural Language Processing", "Large Language Models", "STT",
        "AWS Sagemaker", "AWS Bedrock", "AWS Terraform", "FastAPI", "RAG",
        "Prompt Engineering", "Langchain", "Python", "Pandas", "NumPy",
        "TensorFlow", "Keras", "Java", "Spring Boot", "Microservices",
        "ChromaDB", "Sybase", "Gemfire", "MarkLogic DB",
        "Model Context Protocol", "Amazon Q Developer", "Claude Computer Use",
        "Azure EEC", "AWS EKS",
    ],
    "summary": (
        "AI/ML Engineer with 9 years of total experience and 5 years in AI/ML and "
        "Generative AI. Experienced in designing and deploying production grade AI systems, "
        "Generative AI solutions, and RAG pipelines. Proficient in building end to end "
        "solutions from ML model development and prompt engineering to scalable microservices. "
        "Currently at Boeing India as Programmer Analyst Level 3."
    ),
}

# ══════════════════════════════════════════════════════════════════════
#  ORDER MATTERS — first match wins. CTC/salary BEFORE experience
#  so "CTC" never returns "9"
# ══════════════════════════════════════════════════════════════════════
_QA_MAP = [
    # ── CTC / Salary (MUST be before experience) ──
    (["expected ctc", "expected salary", "expected annual", "expected compensation",
      "desired salary", "desired ctc", "expectation", "expected package"], RESUME["expected_ctc"]),
    (["current ctc", "current salary", "current annual", "present salary",
      "present ctc", "last drawn", "annual ctc", "yearly salary",
      "current package", "present package"], RESUME["current_ctc"]),
    (["fixed ctc", "fixed salary", "fixed component", "base salary", "base ctc"], RESUME["fixed_ctc"]),
    (["variable ctc", "variable salary", "variable component", "bonus", "incentive"], RESUME["variable_ctc"]),
    # Catch-all for any CTC/salary/package/lpa/lakhs question
    (["ctc", "salary", "compensation", "package", "lpa", "lakhs", "lakh",
      "annual income", "remuneration", "pay", "stipend"], RESUME["current_ctc"]),

    # ── Notice period ──
    (["notice period", "notice", "joining time", "when can you join", "earliest joining",
      "how soon can you join", "availability to join", "joining date"], RESUME["notice_period"]),

    # ── Name ──
    (["full name", "your name", "candidate name", "applicant name"], RESUME["name"]),

    # ── Contact ──
    (["email", "e-mail", "mail id", "email id", "email address"], RESUME["email"]),
    (["phone", "mobile", "contact number", "cell", "telephone", "whatsapp"], RESUME["phone_alt"]),

    # ── Location ──
    (["preferred location", "location preference", "preferred city"], RESUME["preferred_locations"]),
    (["current location", "current city", "city you live", "residing", "based in"], RESUME["current_city"]),
    (["hometown", "native", "permanent address", "home town"], RESUME["location"]),
    (["relocat"], "Yes"),

    # ── Experience (AFTER CTC so salary questions don't land here) ──
    (["relevant experience", "ai experience", "ml experience", "genai experience",
      "generative ai experience", "related experience", "experience in ai",
      "experience in ml", "experience in gen", "experience in deep",
      "experience in nlp", "experience in machine"], RESUME["relevant_experience"]),
    (["total experience", "years of experience", "total years", "overall experience",
      "how many year", "work experience", "professional experience", "experience in year",
      "total work", "it experience"], RESUME["total_experience"]),

    # ── Company / Role ──
    (["current company", "present company", "current employer", "current organization",
      "company name", "employer", "organisation"], RESUME["current_company"]),
    (["current designation", "current role", "current title", "job title",
      "current position", "designation", "role"], RESUME["current_designation"]),

    # ── Education ──
    (["education", "qualification", "degree", "highest qualification"], RESUME["education"]),
    (["college", "university", "institute", "school"], RESUME["college"]),
    (["graduation year", "year of passing", "passout", "batch", "passing year"], RESUME["graduation_year"]),

    # ── Personal ──
    (["gender", "sex"], RESUME["gender"]),
    (["marital", "married"], RESUME["marital_status"]),
    (["language", "languages known"], RESUME["languages"]),
    (["linkedin"], RESUME["linkedin"]),

    # ── Skills ──
    (["skill", "technologies", "tech stack", "tools", "proficien", "expertise"], ", ".join(RESUME["skills"])),

    # ── Summary / About ──
    (["about yourself", "summary", "describe yourself", "profile summary",
      "tell us about", "cover letter", "why should we", "introduction",
      "about you", "brief about"], RESUME["summary"]),
]

_YES_KEYWORDS = [
    "willing", "ready", "open to", "comfortable", "agree", "consent",
    "authorize", "confirm", "accept", "relocat", "shift", "travel",
    "work from office", "wfo", "hybrid", "onsite", "night shift",
    "rotational", "weekend", "immediate", "flexible", "ok with",
    "fine with", "available for", "interested",
]
_NO_KEYWORDS = [
    "disability", "handicap", "differently abled", "criminal", "backlog",
    "bond", "arrear", "gap in education", "gap in career",
]


def answer_question(question, numeric_only=False):
    if not question:
        return RESUME["total_experience"]
    q = question.lower().strip()

    # ── 1. Direct mapping match (order matters!) ──
    for keywords, value in _QA_MAP:
        if any(k in q for k in keywords):
            if numeric_only:
                return _to_numeric(value, q)
            return value

    # ── 2. Yes/No intelligence ──
    if not numeric_only:
        for k in _YES_KEYWORDS:
            if k in q:
                return "Yes"
        for k in _NO_KEYWORDS:
            if k in q:
                return "No"

    # ── 3. Smart fallback for numeric questions ──
    if any(w in q for w in ["salary", "ctc", "compensation", "package", "lpa",
                             "lakhs", "lakh", "annual", "pay", "remuneration"]):
        if any(w in q for w in ["expect", "desired", "looking for"]):
            return RESUME["expected_ctc"]
        return RESUME["current_ctc"]

    if any(w in q for w in ["how many", "number of", "count", "years", "months", "experience"]):
        if any(w in q for w in ["ai", "ml", "genai", "generative", "deep learning",
                                 "nlp", "machine learning", "data science"]):
            return RESUME["relevant_experience"]
        return RESUME["total_experience"]

    if any(w in q for w in ["notice", "join", "available", "start"]):
        if numeric_only:
            return RESUME["notice_period_days"]
        return RESUME["notice_period"]

    if any(w in q for w in ["location", "city", "place", "where"]):
        return RESUME["current_city"]

    # ── 4. Final fallback ──
    return RESUME["total_experience"]


# Convert text answers to numeric when field only accepts numbers
_NUMERIC_MAP = {
    "2 months": "60",
    "2months": "60",
    "1 month": "30",
    "3 months": "90",
    "15 days": "15",
    "30 days": "30",
    "60 days": "60",
    "90 days": "90",
    "immediate": "0",
}


def _to_numeric(value, question=""):
    # Already numeric
    if value.replace(".", "").replace("-", "").isdigit():
        return value
    # Known mappings
    vl = value.lower().strip()
    if vl in _NUMERIC_MAP:
        return _NUMERIC_MAP[vl]
    # Extract first number from value
    import re
    nums = re.findall(r'\d+\.?\d*', value)
    if nums:
        return nums[0]
    # Context-based: if question is about notice/days return 60
    q = question.lower()
    if any(w in q for w in ["notice", "days", "join"]):
        return "60"
    if any(w in q for w in ["ctc", "salary", "package", "lpa"]):
        return "30"
    if any(w in q for w in ["experience", "years"]):
        return "9"
    return "0"


# ══════════════════════════════════════════════════════════════════════
#  JOB TITLE RELEVANCE FILTER — only apply to AI/ML related roles
# ══════════════════════════════════════════════════════════════════════
_RELEVANT_WORDS = {
    "ai", "ml", "artificial", "intelligence", "machine", "learning",
    "deep", "generative", "genai", "llm", "nlp", "neural",
    "data", "science", "scientist", "rag", "prompt", "chatbot",
    "vision", "tensorflow", "pytorch", "langchain", "mlops",
    "sagemaker", "bedrock", "openai", "gpt", "bert", "transformer",
    "analytics", "diffusion", "hugging", "stt", "conversational",
    "retrieval", "augmented", "computer", "natural", "language",
    "model", "models", "llms", "prediction", "predictive",
    "classification", "regression", "clustering", "recommendation",
    "autonomous", "robotics", "cognitive", "intelligent",
}


# LinkedIn needs full numeric values for input fields
_LINKEDIN_NUMERIC = {
    # Notice period
    "notice_period": "60",
    "notice_period_days": "60",
    # CTC in actual numbers (LPA to annual)
    "current_ctc": "3000000",
    "current_ctc_lpa": "3000000",
    "fixed_ctc": "2870000",
    "variable_ctc": "130000",
    "expected_ctc": "4000000",
    "expected_ctc_lpa": "4000000",
    # Experience
    "total_experience": "9",
    "relevant_experience": "5",
    # Phone
    "phone": "8489122277",
    "phone_alt": "8489122277",
}


def answer_question_linkedin(question, numeric_only=False):
    """LinkedIn-specific: always returns numeric for salary/ctc/notice/experience fields."""
    if not question:
        return RESUME["total_experience"]
    q = question.lower().strip()

    # CTC / Salary — return full numeric (annual)
    if any(w in q for w in ["expected ctc", "expected salary", "expected annual",
                             "expected compensation", "desired salary", "desired ctc",
                             "expectation", "expected package"]):
        return "4000000"
    if any(w in q for w in ["current ctc", "current salary", "current annual",
                             "present salary", "present ctc", "last drawn",
                             "annual ctc", "yearly salary", "current package",
                             "present package"]):
        return "3000000"
    if any(w in q for w in ["fixed ctc", "fixed salary", "fixed component", "base salary", "base ctc"]):
        return "2870000"
    if any(w in q for w in ["variable ctc", "variable salary", "variable component", "bonus", "incentive"]):
        return "130000"
    if any(w in q for w in ["ctc", "salary", "compensation", "package", "lpa",
                             "lakhs", "lakh", "annual income", "remuneration",
                             "pay", "stipend"]):
        if any(w in q for w in ["expect", "desired", "looking for"]):
            return "4000000"
        return "3000000"

    # Notice period — always days
    if any(w in q for w in ["notice period", "notice", "joining time",
                             "when can you join", "earliest joining",
                             "how soon", "availability to join", "joining date"]):
        return "60"

    # Experience — years as number
    if any(w in q for w in ["relevant experience", "ai experience", "ml experience",
                             "genai experience", "generative ai experience",
                             "related experience", "experience in ai",
                             "experience in ml", "experience in gen",
                             "experience in deep", "experience in nlp",
                             "experience in machine"]):
        return "5"
    if any(w in q for w in ["total experience", "years of experience", "total years",
                             "overall experience", "how many year", "work experience",
                             "professional experience", "experience in year",
                             "total work", "it experience", "experience"]):
        return "9"

    # Fall through to normal answer for non-numeric fields
    return answer_question(question, numeric_only=numeric_only)
    if not title:
        return False
    import re
    t = re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip()
    words = set(t.split())
    match = words & _RELEVANT_WORDS
    if match:
        return True
    # Log what we're checking so we can debug
    import logging
    logging.getLogger(__name__).warning(f"SKIPPED title='{title}' normalized='{t}' words={words}")
    return False
