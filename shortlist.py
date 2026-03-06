import re
import os
import json
import requests
from PyPDF2 import PdfReader

# ─────────────────────────────────────────────
# PDF TEXT EXTRACTION
# ─────────────────────────────────────────────

def extract_text(filename: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    try:
        reader = PdfReader(filename)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"⚠️ Could not extract text from {filename}: {e}")
    return text


# ─────────────────────────────────────────────
# EXPERIENCE EXTRACTION (IMPROVED)
# ─────────────────────────────────────────────

def extract_experience(text: str) -> int:
    """
    Extracts years of experience from a CV.
    Uses multiple patterns and also attempts to infer
    from work history date ranges (e.g., 2017–2024).
    Returns the highest value found.
    """
    lower = text.lower()
    years = []

    # Pattern 1: Explicit mentions like "7 years", "7+ years", "over 7 years"
    explicit_patterns = [
        r"(?:over|more than|almost|nearly|around|approx(?:imately)?)?\s*(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)?",
        r"(\d+)\s*\+?\s*(?:years?|yrs?)'?\s*experience",
    ]
    for p in explicit_patterns:
        for m in re.findall(p, lower):
            try:
                val = int(m)
                if 1 <= val <= 50:  # sanity check
                    years.append(val)
            except ValueError:
                pass

    # Pattern 2: Infer from date ranges in work history (e.g., "Jan 2017 – Mar 2024")
    year_range_pattern = r"\b(20\d{2}|19\d{2})\b"
    all_years = [int(y) for y in re.findall(year_range_pattern, text)]
    if len(all_years) >= 2:
        inferred = max(all_years) - min(all_years)
        if 1 <= inferred <= 50:
            years.append(inferred)

    return max(years) if years else 0


# ─────────────────────────────────────────────
# RULE-BASED CV ANALYSIS (IMPROVED)
# ─────────────────────────────────────────────

def analyze_cv(text: str, job_keywords: dict = None, min_exp: int = 0, max_exp: int = 99, job_type: str = "professional") -> dict:
    """
    Analyze CV text using keyword matching and return a priority score.

    Args:
        text: Raw CV text.
        job_keywords: Dict of {keyword: weight}. Falls back to defaults if None.
        min_exp: Minimum years of experience required (ignored for internship).
        max_exp: Maximum years of experience allowed (ignored for internship).
        job_type: "professional" or "internship".

    Returns:
        Dict with score, matched_keywords, experience_years, and summary.
    """
    experience_years = extract_experience(text)
    lower_text = text.lower()

    # Experience gate — only applied for professional roles
    if job_type == "professional":
        if experience_years > max_exp and max_exp < 99:
            return {
                "score": 0,
                "matched_keywords": [],
                "experience_years": experience_years,
                "summary": f"❌ Rejected: {experience_years} years of experience (max allowed: {max_exp})"
            }
        if experience_years < min_exp and experience_years > 0:
            return {
                "score": 0,
                "matched_keywords": [],
                "experience_years": experience_years,
                "summary": f"❌ Rejected: Only {experience_years} years of experience (min required: {min_exp})"
            }

    # No hardcoded defaults — keywords must be supplied by the caller via the UI
    if not job_keywords:
        job_keywords = {}

    score = 0
    found_keywords = []

    for keyword, weight in job_keywords.items():
        if " " in keyword:
            pattern = re.escape(keyword)
        else:
            pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, lower_text):
            score += weight
            found_keywords.append(keyword)

    if job_type == "professional":
        # Bonus: seniority signals (not relevant for internships)
        seniority_bonus = 0
        for signal in ["senior", "lead", "principal", "architect", "head of", "manager"]:
            if signal in lower_text:
                seniority_bonus += 2
        score += min(seniority_bonus, 10)
    else:
        # Internship mode: bonus for academic/project signals instead
        internship_bonus = 0
        for signal in ["university", "degree", "undergraduate", "final year", "project",
                       "dissertation", "gpa", "honours", "distinction", "dean"]:
            if signal in lower_text:
                internship_bonus += 2
        score += min(internship_bonus, 10)

    exp_label = f"{experience_years} yrs" if experience_years > 0 else "Not specified"
    return {
        "score": score,
        "matched_keywords": found_keywords,
        "experience_years": experience_years,
        "summary": (
            f"{'🎓 Internship mode | ' if job_type == 'internship' else ''}"
            f"Experience: {exp_label} | "
            f"Matched {len(found_keywords)} skills: {', '.join(found_keywords) or 'None'}"
        )
    }


# ─────────────────────────────────────────────
# SHARED PROMPT BUILDER
# ─────────────────────────────────────────────

SYSTEM_PROMPT_PROFESSIONAL = """You are an expert HR recruiter. Evaluate the candidate CV against the job description.

CRITICAL RULES — you MUST follow these exactly:
- Respond with ONLY a single JSON object. No text before or after it.
- Do NOT use markdown, code fences, or backticks.
- All string values must use double quotes. Never use single quotes inside strings.
- Do NOT include apostrophes (') in any string value — rephrase to avoid them (e.g. use "does not" not "doesn't").
- Do NOT include commas inside string values.
- Keep all string values short and simple.

Required JSON format:
{
  "ai_score": <integer 0-100>,
  "strengths": ["strength one", "strength two", "strength three"],
  "gaps": ["gap one", "gap two"],
  "experience_fit": "<Too Junior | Good Fit | Overqualified>",
  "recommendation": "<Strong Yes | Yes | Maybe | No>",
  "summary": "<2-3 sentences about the candidate with no apostrophes or commas>"
}"""

SYSTEM_PROMPT_INTERNSHIP = """You are an expert HR recruiter evaluating candidates for an internship or entry-level position.

IMPORTANT CONTEXT: These are students or fresh graduates with little or no professional experience.
Do NOT penalise candidates for lacking work experience. Instead evaluate:
- Academic background and GPA if mentioned
- University projects and coursework relevance
- Personal or open-source projects
- Internship or part-time exposure (even brief)
- Relevant skills and tools learned
- Enthusiasm and learning potential

CRITICAL RULES — you MUST follow these exactly:
- Respond with ONLY a single JSON object. No text before or after it.
- Do NOT use markdown, code fences, or backticks.
- All string values must use double quotes. Never use single quotes inside strings.
- Do NOT include apostrophes (') in any string value — rephrase to avoid them.
- Do NOT include commas inside string values.
- Keep all string values short and simple.
- For experience_fit use: "Student | Fresh Graduate | Has Some Experience" instead of seniority labels.

Required JSON format:
{
  "ai_score": <integer 0-100>,
  "strengths": ["strength one", "strength two", "strength three"],
  "gaps": ["gap one", "gap two"],
  "experience_fit": "<Student | Fresh Graduate | Has Some Experience>",
  "recommendation": "<Strong Yes | Yes | Maybe | No>",
  "summary": "<2-3 sentences about the candidate with no apostrophes or commas>"
}"""


def _build_user_prompt(cv_text: str, job_description: str, job_type: str = "professional") -> str:
    truncated_cv = cv_text[:6000] if len(cv_text) > 6000 else cv_text
    context = (
        "This is an INTERNSHIP role. Focus on academic projects, skills and potential — not work experience."
        if job_type == "internship"
        else "This is a professional role. Evaluate experience, skills and seniority fit."
    )
    return f"""JOB DESCRIPTION:
{job_description}

EVALUATION CONTEXT: {context}

---

CANDIDATE CV:
{truncated_cv}

---

Evaluate this candidate for the job described above. Reply with JSON only."""


def _clean_raw_json(raw: str) -> str:
    """Remove markdown fences and trim whitespace."""
    raw = re.sub(r"```(?:json)?", "", raw)
    raw = raw.strip().rstrip("`").strip()
    return raw


def _extract_json_block(raw: str) -> str:
    """Pull out the first {...} block from the string (handles preamble/postamble)."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return match.group(0) if match else raw


def _sanitize_json_strings(raw: str) -> str:
    """
    Fix common issues local LLMs produce inside JSON string values:
    - Unescaped apostrophes/single quotes  (don't → don\'t handled by json, but curly ones break it)
    - Unescaped double quotes inside values
    - Curly/smart quotes replaced with straight quotes
    """
    # Replace smart/curly quotes with standard straight quotes
    raw = raw.replace("\u2018", "'").replace("\u2019", "'")   # ' '
    raw = raw.replace("\u201c", '"').replace("\u201d", '"')   # " "
    raw = raw.replace("\u2032", "'").replace("\u2033", '"')   # prime chars

    # Remove literal newlines inside JSON string values (between quotes)
    # This replaces \n inside "..." with a space
    def fix_newlines_in_strings(s):
        result = []
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                result.append(ch)
                in_string = not in_string
            elif in_string and ch in ("\n", "\r"):
                result.append(" ")  # replace bare newline inside string with space
            else:
                result.append(ch)
        return "".join(result)

    return fix_newlines_in_strings(raw)


def _parse_fields_with_regex(raw: str) -> dict:
    """
    Last-resort field-by-field regex extraction when JSON is too broken to parse.
    Pulls key values directly from the raw string.
    """
    def find_int(key):
        m = re.search(rf'"{key}"\s*:\s*(\d+)', raw)
        return int(m.group(1)) if m else 0

    def find_str(key):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
        return m.group(1).strip() if m else "Unknown"

    def find_list(key):
        m = re.search(rf'"{key}"\s*:\s*\[([^\]]*)\]', raw, re.DOTALL)
        if not m:
            return []
        inner = m.group(1)
        items = re.findall(r'"([^"]+)"', inner)
        return items

    return {
        "ai_score": find_int("ai_score"),
        "strengths": find_list("strengths"),
        "gaps": find_list("gaps"),
        "experience_fit": find_str("experience_fit"),
        "recommendation": find_str("recommendation"),
        "summary": find_str("summary"),
        "error": None,
    }


def _parse_ai_response(raw: str) -> dict:
    """
    Robustly parse JSON from an LLM response using 3 progressive strategies:
      1. Clean + standard json.loads()
      2. Extract JSON block + sanitize + json.loads()
      3. Regex field-by-field extraction (last resort)
    """
    # Strategy 1: clean and try direct parse
    cleaned = _clean_raw_json(raw)
    try:
        result = json.loads(cleaned)
        return {
            "ai_score": int(result.get("ai_score", 0)),
            "strengths": result.get("strengths", []),
            "gaps": result.get("gaps", []),
            "experience_fit": result.get("experience_fit", "Unknown"),
            "recommendation": result.get("recommendation", "Unknown"),
            "summary": result.get("summary", "No summary available."),
            "error": None,
        }
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract JSON block, sanitize, try again
    try:
        block = _extract_json_block(cleaned)
        sanitized = _sanitize_json_strings(block)
        result = json.loads(sanitized)
        return {
            "ai_score": int(result.get("ai_score", 0)),
            "strengths": result.get("strengths", []),
            "gaps": result.get("gaps", []),
            "experience_fit": result.get("experience_fit", "Unknown"),
            "recommendation": result.get("recommendation", "Unknown"),
            "summary": result.get("summary", "No summary available."),
            "error": None,
        }
    except json.JSONDecodeError:
        pass

    # Strategy 3: regex extraction — never fails, extracts what it can
    return _parse_fields_with_regex(cleaned)


def _error_response(msg: str) -> dict:
    return {
        "ai_score": 0,
        "strengths": [],
        "gaps": [],
        "experience_fit": "Unknown",
        "recommendation": "Error",
        "summary": f"⚠️ {msg}",
        "error": msg,
    }


# ─────────────────────────────────────────────
# OPENAI-POWERED CV ANALYSIS
# ─────────────────────────────────────────────

def analyze_cv_with_openai(
    cv_text: str,
    job_description: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    job_type: str = "professional"
) -> dict:
    """
    Use OpenAI to evaluate a CV against a job description.
    Requires: pip install openai
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system_prompt = SYSTEM_PROMPT_INTERNSHIP if job_type == "internship" else SYSTEM_PROMPT_PROFESSIONAL
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(cv_text, job_description, job_type)}
            ],
            temperature=0.2,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_ai_response(raw)
    except Exception as e:
        return _error_response(f"OpenAI analysis failed: {e}")


# ─────────────────────────────────────────────
# OLLAMA-POWERED CV ANALYSIS (LOCAL, FREE)
# ─────────────────────────────────────────────

def analyze_cv_with_ollama(
    cv_text: str,
    job_description: str,
    model: str = "llama3",
    ollama_url: str = "http://localhost:11434",
    job_type: str = "professional"
) -> dict:
    """
    Use a locally running Ollama model to evaluate a CV.
    job_type: "professional" or "internship" — changes the evaluation prompt and criteria.
    """
    endpoint = f"{ollama_url.rstrip('/')}/api/chat"
    system_prompt = SYSTEM_PROMPT_INTERNSHIP if job_type == "internship" else SYSTEM_PROMPT_PROFESSIONAL

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(cv_text, job_description, job_type)}
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 600,
        }
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        raw = data["message"]["content"].strip()
        return _parse_ai_response(raw)

    except requests.exceptions.ConnectionError:
        return _error_response(
            "Cannot connect to Ollama. Make sure Ollama is running: open a terminal and run `ollama serve`"
        )
    except requests.exceptions.Timeout:
        return _error_response(
            "Ollama timed out. The model may be loading — try again in a moment, or use a smaller model like phi3."
        )
    except Exception as e:
        return _error_response(f"Ollama analysis failed: {e}")


def list_ollama_models(ollama_url: str = "http://localhost:11434") -> list[str]:
    """
    Fetch the list of locally available Ollama models.
    Returns a list of model name strings, or empty list if Ollama is not running.
    """
    try:
        resp = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return [m["name"] for m in models]
    except Exception:
        return []
