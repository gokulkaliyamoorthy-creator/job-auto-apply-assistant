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


def answer_question(question):
    if not question:
        return RESUME["total_experience"]
    q = question.lower().strip()

    # ── 1. Direct mapping match (order matters!) ──
    for keywords, value in _QA_MAP:
        if any(k in q for k in keywords):
            return value

    # ── 2. Yes/No intelligence ──
    for k in _YES_KEYWORDS:
        if k in q:
            return "Yes"
    for k in _NO_KEYWORDS:
        if k in q:
            return "No"

    # ── 3. Smart fallback for numeric questions ──
    # CTC/salary related — return 30 (current) not 9
    if any(w in q for w in ["salary", "ctc", "compensation", "package", "lpa",
                             "lakhs", "lakh", "annual", "pay", "remuneration"]):
        if any(w in q for w in ["expect", "desired", "looking for"]):
            return RESUME["expected_ctc"]
        return RESUME["current_ctc"]

    # Experience related
    if any(w in q for w in ["how many", "number of", "count", "years", "months", "experience"]):
        if any(w in q for w in ["ai", "ml", "genai", "generative", "deep learning",
                                 "nlp", "machine learning", "data science"]):
            return RESUME["relevant_experience"]
        return RESUME["total_experience"]

    # Notice related
    if any(w in q for w in ["notice", "join", "available", "start"]):
        return RESUME["notice_period"]

    # Location related
    if any(w in q for w in ["location", "city", "place", "where"]):
        return RESUME["current_city"]

    # ── 4. Final fallback ──
    return RESUME["total_experience"]
