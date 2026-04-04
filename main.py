"""
Job Auto-Apply Bot — Naukri & LinkedIn Easy Apply
Usage:
    python main.py --platform naukri
    python main.py --platform linkedin
    python main.py --platform both
"""
import argparse
import logging
from config import CONFIG
from naukri_apply import NaukriApplier
from linkedin_apply import LinkedInApplier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run_naukri():
    c = CONFIG
    NaukriApplier(
        c["naukri"]["email"], c["naukri"]["password"],
        c["job_keywords"], c["job_locations"], c["max_applications"],
    ).run()


def run_linkedin():
    c = CONFIG
    LinkedInApplier(
        c["linkedin"]["email"], c["linkedin"]["password"],
        c["job_keywords"], c["job_locations"], c["max_applications"],
    ).run()


def main():
    parser = argparse.ArgumentParser(description="Auto-apply to jobs on Naukri / LinkedIn")
    parser.add_argument(
        "--platform", choices=["naukri", "linkedin", "both"], default="both",
        help="Which platform to apply on (default: both)",
    )
    args = parser.parse_args()

    if args.platform in ("naukri", "both"):
        log.info("=== Starting Naukri Auto-Apply ===")
        run_naukri()

    if args.platform in ("linkedin", "both"):
        log.info("=== Starting LinkedIn Auto-Apply ===")
        run_linkedin()


if __name__ == "__main__":
    main()
