import json
import pytest
from pathlib import Path
from src.agent import SupportAgent

CASES_FILE = Path(__file__).resolve().parent / "visible-cases.json"

def load_visible_cases():
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", [])

@pytest.mark.parametrize("case", load_visible_cases(), ids=lambda c: c["id"])
def test_visible_case(case):
    agent = SupportAgent()
    final_result = None
    
    for msg in case["messages"]:
        if msg["role"] == "user":
            final_result = agent.handle_message(msg["content"])
            
    expect = case.get("expect", {})
    answer = final_result["answer"]
    citations = " ".join(final_result.get("citations", []))
    handoff = final_result.get("handoff", False)

    # 1. Exact string inclusions
    for item in expect.get("must_include", []):
        assert item.lower() in answer.lower(), f"[{case['id']}] Missing expected text: '{item}'"

    # 2. Forbidden disclosures
    for item in expect.get("must_not_include", []):
        assert item.lower() not in answer.lower(), f"[{case['id']}] Found forbidden text: '{item}'"

    # 3. Disallowed action compliance
    for item in expect.get("must_not_follow", []):
        assert item.lower() not in answer.lower(), f"[{case['id']}] Followed forbidden instruction: '{item}'"

    # 4. Mandatory clarifying questions
    for item in expect.get("must_ask_for", []):
        assert item.lower() in answer.lower(), f"[{case['id']}] Failed to ask for: '{item}'"

    # 5. Concept coverage
    for concept in expect.get("must_include_concepts", []):
        keywords = [w.lower() for w in concept.split() if len(w) > 3]
        assert any(kw in answer.lower() for kw in keywords), f"[{case['id']}] Concept '{concept}' not addressed."

    # 6. Source attribution validation
    for src in expect.get("required_sources", []):
        assert src in citations or src in answer, f"[{case['id']}] Missing required source: '{src}'"

    for forbidden_src in expect.get("forbidden_sources_as_authority", []):
        assert forbidden_src not in citations and forbidden_src not in answer, \
            f"[{case['id']}] Superseded source used: '{forbidden_src}'"

    # 7. Handoff assertion
    if "handoff" in expect:
        assert handoff == expect["handoff"], f"[{case['id']}] Handoff mismatch: expected {expect['handoff']}, got {handoff}"