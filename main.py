"""
Job Auto-Apply Bot — Naukri, LinkedIn, and Foundit
Usage:
    python main.py --platform naukri
    python main.py --platform linkedin
    python main.py --platform foundit
    python main.py --platform both
    python main.py --platform all
"""
import argparse
import logging
from config import CONFIG
from foundit_apply import FounditApplier
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


def run_foundit():
    c = CONFIG
    FounditApplier(
        c["foundit"]["email"], c["foundit"]["password"],
        c["foundit"]["job_keywords"], c["job_locations"], c["max_applications"],
    ).run()


def main():
    parser = argparse.ArgumentParser(description="Auto-apply to jobs on Naukri / LinkedIn / Foundit")
    parser.add_argument(
        "--platform", choices=["naukri", "linkedin", "foundit", "both", "all"], default="all",
        help="Which platform to apply on (default: all)",
    )
    args = parser.parse_args()

    if args.platform in ("naukri", "both", "all"):
        log.info("=== Starting Naukri Auto-Apply ===")
        run_naukri()

    if args.platform in ("linkedin", "both", "all"):
        log.info("=== Starting LinkedIn Auto-Apply ===")
        run_linkedin()

    if args.platform in ("foundit", "all"):
        log.info("=== Starting Foundit Auto-Apply ===")
        run_foundit()


if __name__ == "__main__":
    main()
