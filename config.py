import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "naukri": {
        "email": os.getenv("NAUKRI_EMAIL"),
        "password": os.getenv("NAUKRI_PASSWORD"),
    },
    "linkedin": {
        "email": os.getenv("LINKEDIN_EMAIL"),
        "password": os.getenv("LINKEDIN_PASSWORD"),
    },
    "job_keywords": [k.strip() for k in os.getenv("JOB_KEYWORDS", "Python Developer").split(",")],
    "job_locations": [l.strip() for l in os.getenv("JOB_LOCATIONS", os.getenv("JOB_LOCATION", "Bangalore")).split(",")],
    "max_applications": int(os.getenv("MAX_APPLICATIONS", 50)),
}
