# Job Auto-Apply Bot (Naukri + LinkedIn)

Automates job applications on Naukri and LinkedIn Easy Apply using Selenium.

## Setup

```bash
cd c:\Users\fe901f\Documents\job_auto_apply

# Create virtual env
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configure

1. Copy `.env.example` to `.env`
2. Fill in your credentials and job search preferences:

```
NAUKRI_EMAIL=your_email@example.com
NAUKRI_PASSWORD=your_password
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
JOB_KEYWORDS=Python Developer
JOB_LOCATION=Bangalore
MAX_APPLICATIONS=50
```

## Run

```bash
# Apply on both platforms
python main.py --platform both

# Naukri only
python main.py --platform naukri

# LinkedIn only
python main.py --platform linkedin
```

## Important Notes

- **LinkedIn CAPTCHA/2FA**: If detected, the script pauses and asks you to solve it manually in the browser, then press ENTER.
- **LinkedIn Easy Apply only**: The script only applies to jobs with the "Easy Apply" button. Multi-step forms with required unfilled fields are skipped.
- **Naukri popups**: The script attempts to handle post-apply chatbot/questionnaire popups automatically.
- **Chrome required**: Uses Chrome via `webdriver-manager` (auto-downloads matching ChromeDriver).
- **Rate limits**: Both sites may throttle or block if you apply too fast. The built-in delays help, but you may still get flagged.
- **Profile must be complete**: Both platforms use your profile data when applying — make sure your resume, skills, and experience are up to date.
