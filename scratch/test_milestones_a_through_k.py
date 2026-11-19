import asyncio
import calendar
import os
import sys
import sqlite3
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.tools.date_calculator import DateCalculator
from backend.app.services.tools.calculator import CalculatorTool
from backend.app.services.tools.python_sandbox import PythonSandboxTool
from backend.app.services.live.weather import WeatherService
from backend.app.services.live.currency import CurrencyService
from backend.app.services.live.news import NewsService
from backend.app.services.ai.router import RequestRouter
from backend.app.services.ai.factory import ProviderFactory
from backend.app.services.ai.model_manager import ModelManager


async def run_all_milestone_tests():
    results = {}
    print("=" * 70)
    print("AUREVON AI — MASTER INTELLIGENCE ENGINE VALIDATION (TESTS A - K)")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST A: Conversational Intelligence & Router Fast Path
    # -------------------------------------------------------------
    try:
        greeting_dec = RequestRouter.classify("Hello AUREVON, how are you?")
        assert greeting_dec.intent == "greeting", f"Expected greeting, got {greeting_dec.intent}"
        knowledge_dec = RequestRouter.classify("Explain quantum computing principles")
        assert knowledge_dec.intent == "knowledge", f"Expected knowledge, got {knowledge_dec.intent}"
        results["Test A (Conversational & Router)"] = "PASSED"
        print("[PASS] Test A: Intent classification & greeting fast-path routing verified.")
    except Exception as e:
        results["Test A (Conversational & Router)"] = f"FAILED: {e}"
        print(f"[FAIL] Test A: {e}")

    # -------------------------------------------------------------
    # TEST B: Exact Age Calculation (DOB: 15 March 2004, Ref: 13 Nov 2026)
    # -------------------------------------------------------------
    try:
        age_res = DateCalculator.calculate_exact_age("15 March 2004", "13 November 2026")
        assert age_res["ok"] is True
        assert age_res["years"] == 22, f"Expected 22 years, got {age_res['years']}"
        assert age_res["months"] == 7, f"Expected 7 months, got {age_res['months']}"
        assert age_res["days"] == 29, f"Expected 29 days, got {age_res['days']}"
        assert age_res["formatted"] == "22 years, 7 months and 29 days"
        assert age_res["total_days"] == 8278

        # Leap year birthday test (29 Feb 2000 -> 28 Feb 2001: 0 yrs, 11 mos, 30 days)
        leap_res = DateCalculator.calculate_exact_age("29 February 2000", "2001-02-28")
        assert leap_res["ok"] is True
        assert leap_res["is_leap_year_born"] is True

        results["Test B (Exact Age Engine)"] = "PASSED"
        print(f"[PASS] Test B: Exact Age calculated: {age_res['formatted']} ({age_res['total_days']} total days).")
    except Exception as e:
        results["Test B (Exact Age Engine)"] = f"FAILED: {e}"
        print(f"[FAIL] Test B: {e}")

    # -------------------------------------------------------------
    # TEST C: Live Weather for Mawanella
    # -------------------------------------------------------------
    try:
        w = await WeatherService.get_weather("Mawanella")
        assert w["ok"] is True
        assert "Mawanella" in w["location"]
        assert "temperature_c" in w["current"]
        assert "tomorrow" in w
        assert w["source"].startswith("Open-Meteo")
        results["Test C (Weather Open-Meteo)"] = "PASSED"
        print(f"[PASS] Test C: Weather retrieved for {w['location']}: {w['current']['temperature_c']}°C, {w['current']['condition']} (Source: {w['source']}).")
    except Exception as e:
        results["Test C (Weather Open-Meteo)"] = f"FAILED: {e}"
        print(f"[FAIL] Test C: {e}")

    # -------------------------------------------------------------
    # TEST D: Current News & DuckDuckGo Search
    # -------------------------------------------------------------
    try:
        n = await NewsService.get_news("ai", max_articles=3)
        assert n["ok"] is True
        assert len(n["articles"]) > 0
        assert all("title" in a and "url" in a and "source" in a for a in n["articles"])
        results["Test D (News & Web Intelligence)"] = "PASSED"
        print(f"[PASS] Test D: News retrieved ({len(n['articles'])} articles, top source: {n['articles'][0]['source']}).")
    except Exception as e:
        results["Test D (News & Web Intelligence)"] = f"FAILED: {e}"
        print(f"[FAIL] Test D: {e}")

    # -------------------------------------------------------------
    # TEST E: Python Data Analysis & Chart Generation
    # -------------------------------------------------------------
    try:
        code = """
import statistics
data = [12, 15, 18, 22, 30]
print("Mean:", statistics.mean(data))
print("Median:", statistics.median(data))
plot_bar(["Jan", "Feb", "Mar", "Apr", "May"], data, title="Growth Trends")
"""
        py_res = PythonSandboxTool.execute(code, timeout_seconds=6)
        assert py_res["ok"] is True
        assert "Mean: 19.4" in py_res["stdout"]
        assert len(py_res["charts"]) == 1
        assert py_res["charts"][0].startswith("<svg")
        results["Test E (Python Data Analysis)"] = "PASSED"
        print("[PASS] Test E: Python Data Analysis executed with verified statistics and SVG chart generation.")
    except Exception as e:
        results["Test E (Python Data Analysis)"] = f"FAILED: {e}"
        print(f"[FAIL] Test E: {e}")

    # -------------------------------------------------------------
    # TEST F: Python Sandbox Isolation Security
    # -------------------------------------------------------------
    try:
        for forbidden in ["import os", "import subprocess", "open('test.txt', 'w')", "eval('1+1')"]:
            blocked = PythonSandboxTool.execute(forbidden)
            assert blocked["ok"] is False and blocked["status"] == "blocked"
        results["Test F (Sandbox Security)"] = "PASSED"
        print("[PASS] Test F: Python sandbox AST allowlist strictly blocked dangerous operations.")
    except Exception as e:
        results["Test F (Sandbox Security)"] = f"FAILED: {e}"
        print(f"[FAIL] Test F: {e}")

    # -------------------------------------------------------------
    # TEST G: Live Currency Converter
    # -------------------------------------------------------------
    try:
        curr = await CurrencyService.get_exchange_rate("USD", "LKR", 100.0)
        assert curr["ok"] is True
        assert curr["converted"] > 0
        assert curr["rate"] > 0
        results["Test G (Currency Conversion)"] = "PASSED"
        print(f"[PASS] Test G: Forex verified: 100 USD = {curr['converted']} LKR (Rate: {curr['rate']}, Source: {curr['source']}).")
    except Exception as e:
        results["Test G (Currency Conversion)"] = f"FAILED: {e}"
        print(f"[FAIL] Test G: {e}")

    # -------------------------------------------------------------
    # TEST H: Scientific Calculator & AST Safety
    # -------------------------------------------------------------
    try:
        calc = CalculatorTool.execute("15% of 240 + sqrt(144)")
        assert calc["ok"] is True and calc["result"] == 48
        conv = CalculatorTool.execute("5 km to m")
        assert conv["ok"] is True and conv["converted"] == 5000
        results["Test H (Calculator & AST)"] = "PASSED"
        print(f"[PASS] Test H: Scientific Calculator verified: 15% of 240 + sqrt(144) = {calc['result']}.")
    except Exception as e:
        results["Test H (Calculator & AST)"] = f"FAILED: {e}"
        print(f"[FAIL] Test H: {e}")

    # -------------------------------------------------------------
    # TEST I: Multi-Provider & Google Gemini Adapter
    # -------------------------------------------------------------
    try:
        provs = ProviderFactory.list_all_providers()
        prov_names = [p.name for p in provs]
        assert "ollama" in prov_names, "Ollama must be registered"
        assert "gemini" in prov_names, "Gemini must be registered"
        assert "openai" in prov_names, "OpenAI must be registered"
        results["Test I (Provider Architecture)"] = "PASSED"
        print(f"[PASS] Test I: Provider Factory discovered registered providers: {prov_names}.")
    except Exception as e:
        results["Test I (Provider Architecture)"] = f"FAILED: {e}"
        print(f"[FAIL] Test I: {e}")

    # -------------------------------------------------------------
    # TEST J: Centralized Model Management & Pricing
    # -------------------------------------------------------------
    try:
        ollama_state = await ModelManager.fetch_ollama_runtime_state(force_refresh=True)
        assert ollama_state["reachable"] is True
        installed = [m["name"] for m in ollama_state["installed_models"]]
        assert any("qwen" in m for m in installed)
        results["Test J (Model Management)"] = "PASSED"
        print(f"[PASS] Test J: Ollama runtime active at {ollama_state['base_url']} with models: {installed}.")
    except Exception as e:
        results["Test J (Model Management)"] = f"FAILED: {e}"
        print(f"[FAIL] Test J: {e}")

    # -------------------------------------------------------------
    # TEST K: Database Record & Schema Preservation
    # -------------------------------------------------------------
    try:
        db_path = os.path.abspath("aurevon.db")
        assert os.path.exists(db_path), "aurevon.db must exist"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        users_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        convs_count = cur.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msgs_count = cur.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        alembic_ver = cur.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()

        assert users_count >= 33, f"Expected at least 33 users, found {users_count}"
        assert convs_count >= 44, f"Expected at least 44 conversations, found {convs_count}"
        assert msgs_count >= 86, f"Expected at least 86 messages, found {msgs_count}"
        assert alembic_ver == "20261112_0003", f"Expected revision 20261112_0003, found {alembic_ver}"

        results["Test K (Preservation & DB Integrity)"] = "PASSED"
        print(f"[PASS] Test K: Absolute Preservation Verified -> Users: {users_count}, Conversations: {convs_count}, Messages: {msgs_count}, Alembic: {alembic_ver}.")
    except Exception as e:
        results["Test K (Preservation & DB Integrity)"] = f"FAILED: {e}"
        print(f"[FAIL] Test K: {e}")

    print("=" * 70)
    print("TEST SUITE SUMMARY:")
    all_passed = True
    for test_name, status in results.items():
        print(f"  {test_name:<40}: {status}")
        if status != "PASSED":
            all_passed = False
    print("=" * 70)
    if all_passed:
        print("ALL TESTS A THROUGH K PASSED SUCCESSFULLY (100% COMPLETE)")
    else:
        print("SOME TESTS FAILED — INSPECT OUTPUT ABOVE")
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_milestone_tests())
    sys.exit(0 if success else 1)
