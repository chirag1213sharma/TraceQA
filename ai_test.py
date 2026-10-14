"""Quick script to test Google Gemini structured test analysis."""

import os
import requests
from pathlib import Path
import json
from pprint import pprint

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"
)

def ask_gemini(system_prompt: str, user_prompt: str, additional_data: str) -> str:
    """Send a request to the Google Gemini cloud model and return its reply."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is empty. Set it before calling ask_gemini.")

    user_content = f"{user_prompt}\n\nTest data for analysis:\n{additional_data}"

    response = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        },
        timeout=600,
    )
    response.raise_for_status()

    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def test_logs_extract() -> tuple:
    result = Path(r"C:\TraceQA\test-logs\Regression_Report\test_system_report_20260621.json")
    test_name = result.parents[0].name
    report_name = result.name
    with open(result, 'r', encoding="utf-8") as json_file:
        data = json.load(json_file)
    pprint(data)
    return (test_name, report_name, data)


if __name__ == "__main__":
    test_logs = test_logs_extract()
    reply = ask_gemini(
        system_prompt="""
        You are an automated test result analyser. Your task is to analyse test data from any test and provide structured responce.
        I will provide you : Test Name, Report name (contains execution date) and Raw data of test (any format like json, html or txt)
        You are going to analyze the test and give structured responce to following:
        {
        test_name : str,
        execution_date : int (YYYYMMDD),
        status : str (passed, failed),
        test_cases_passed : str (50/100),
        test_cases_failed : str (10/ 50),
        failed_test_case_list : list (e.g. : [mill_module, turn_module], return empty if status in passed)
        ai_analysis : str (Expalin in ~50 words about status of test and explain what is wrong in the results)
        insturctions_for_qa : str (You will give instruction to QA like check mill module since it is showing more test cases failed)
        }
        """,
        user_prompt=f"Test Name : {test_logs[0]}, Report Name : {test_logs[1]}",
        additional_data=f"{test_logs[2]}",
    )
    print(reply)
