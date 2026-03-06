# 📋 CV Shortlister

A Streamlit-based application for shortlisting and ranking candidate CVs (PDFs) using either rule-based keyword scoring or AI-powered semantic analysis. Supports both professional role hiring and internship/entry-level recruitment, with full local inference support via Ollama — no cloud API key required.

---

## Table of Contents

- [Features](#features)
- [File Structure](#file-structure)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [How to Use](#how-to-use)
  - [Step 1 — Choose an Analysis Mode](#step-1--choose-an-analysis-mode)
  - [Step 2 — Choose a Job Type](#step-2--choose-a-job-type)
  - [Step 3 — Set the Experience Filter](#step-3--set-the-experience-filter)
  - [Step 4 — Define Your Keywords](#step-4--define-your-keywords)
  - [Step 5 — Configure Your AI Backend](#step-5--configure-your-ai-backend)
  - [Step 6 — Paste a Job Description](#step-6--paste-a-job-description)
  - [Step 7 — Upload CVs and Analyse](#step-7--upload-cvs-and-analyse)
  - [Step 8 — Review and Export Results](#step-8--review-and-export-results)
- [Analysis Modes in Detail](#analysis-modes-in-detail)
  - [Keyword Scoring Mode](#-keyword-scoring-mode)
  - [Ollama Mode (Local AI)](#-ollama-mode-local-ai)
  - [OpenAI Mode](#-openai-mode)
- [Job Types in Detail](#job-types-in-detail)
  - [Professional Role Mode](#-professional-role-mode)
  - [Internship / Entry Level Mode](#-internship--entry-level-mode)
- [Setting Up Ollama](#setting-up-ollama)
- [Keyword Configuration](#keyword-configuration)
- [Understanding the Results](#understanding-the-results)
- [Dependencies](#dependencies)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Three analysis modes** — pure keyword scoring, local AI via Ollama, or cloud AI via OpenAI
- **Two job type modes** — Professional (experience-gated) and Internship (experience-free, potential-focused)
- **Fully configurable keywords** — define your own skills via a simple comma-separated input or a weighted table; no hardcoded defaults
- **Automatic experience extraction** — detects explicit mentions ("5 years") and infers from date ranges in work history
- **AI-powered candidate cards** — per-CV breakdown with score, strengths, gaps, experience fit, and recommendation
- **Robust JSON parsing** — three-layer fallback parser handles malformed output from local LLMs gracefully
- **CSV export** — download the full ranked results table for further review or reporting
- **Privacy-safe by default** — Ollama mode runs entirely on your local machine; no CV data leaves your network

---

## File Structure

```
├── app.py           # Streamlit UI — all sidebar controls, file upload, results display
├── shortlist.py     # Core logic — PDF extraction, keyword scoring, AI integration
├── temp/            # Temporary folder for uploaded PDFs (auto-created and auto-cleared)
└── README.md        # This file
```

---

## Installation

**1. Clone or download the project files**

Ensure `app.py` and `shortlist.py` are in the same directory.

**2. Install Python dependencies**

```bash
pip install streamlit PyPDF2 requests pandas
```

For OpenAI mode, also install:

```bash
pip install openai
```

> Ollama mode uses only `requests` — no additional SDK needed.

---

## Running the App

```bash
python3 -m streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## How to Use

All configuration lives in the **left sidebar**. Work through it top to bottom before uploading CVs.

### Step 1 — Choose an Analysis Mode

| Mode | Description | Cost | Privacy |
|---|---|---|---|
| 🔍 **Keyword Scoring** | Fast rule-based matching against your keyword list | Free | Local |
| 🦙 **Ollama (Local AI)** | Full LLM analysis running on your machine | Free | 100% Local |
| 🤖 **OpenAI** | Cloud LLM analysis via GPT models | Pay-per-use | Data sent to OpenAI |

### Step 2 — Choose a Job Type

| Job Type | Description |
|---|---|
| 💼 **Professional Role** | Standard hiring. Experience filter is active. Seniority signals boost the score. |
| 🎓 **Internship / Entry Level** | Experience filter is disabled. Academic projects, GPA, and learning potential are rewarded instead. |

### Step 3 — Set the Experience Filter

*(Professional mode only — this section is hidden in Internship mode)*

Use the slider to define the acceptable range of years of experience. Any CV that falls outside this range is automatically rejected before AI analysis runs, saving time and API calls.

Experience is extracted both from explicit mentions (e.g. "5+ years of experience") and inferred from date ranges found in the work history section (e.g. jobs listed from 2019 to 2024 → ~5 years).

### Step 4 — Define Your Keywords

Keywords are used by all three modes — in Keyword mode they are the primary scoring mechanism, and in AI modes they populate the "Matched Keywords" column alongside the AI results.

There are two ways to enter keywords:

**✏️ Simple tab** — type a comma-separated list. All keywords receive equal weight (10):
```
python, aws, docker, kubernetes, sql, terraform, git
```

**⚖️ With Weights tab** — use the editable table to assign different importance scores (1–20) to different skills. For example, a role where Kubernetes is critical can be weighted higher than general communication skills. You can add rows, delete rows, and edit any value inline. The Advanced tab overrides the Simple tab if both have content.

> If no keywords are defined, a warning appears and scoring will return 0 for all CVs.

### Step 5 — Configure Your AI Backend

**If using Ollama:** Enter the server URL (default `http://localhost:11434`). The app will automatically detect which models you have installed and show them in a dropdown. See the [Setting Up Ollama](#setting-up-ollama) section below.

**If using OpenAI:** Paste your API key (it is only held in memory for the current session and never stored to disk). Select a model:
- `gpt-4o-mini` — fastest and cheapest (~$0.001 per CV), recommended for large batches
- `gpt-4o` — higher quality analysis, better at nuanced reasoning
- `gpt-4-turbo` — balanced option

### Step 6 — Paste a Job Description

*(Recommended for AI modes; optional for Keyword mode)*

Paste the full job description into the text area at the bottom of the sidebar. In AI modes, this is sent to the model alongside the CV so the evaluation is grounded in the actual role requirements rather than general criteria. The more detailed the description, the more accurate the scoring.

### Step 7 — Upload CVs and Analyse

Click **"Upload PDF CVs"** in the main area and select one or more PDF files. Then click **▶ Analyse CVs**. A progress bar shows each file as it is processed.

### Step 8 — Review and Export Results

Results appear ranked by score. You can:
- View the **summary table** at the top for a quick at-a-glance ranking
- Expand any **candidate card** to see the full breakdown — matched keywords, AI score, strengths, gaps, and recommendation
- Click **⬇️ Download Results as CSV** to export the full ranked list
- Click **🗑️ Clear All Results** to reset everything and start a new batch

---

## Analysis Modes in Detail

### 🔍 Keyword Scoring Mode

Each CV is scanned for the keywords you defined. When a keyword is found, its weight is added to the candidate's total score. Keywords are matched case-insensitively. Single-word keywords use word-boundary matching (so "java" does not match "javascript"). Multi-word phrases like "machine learning" use substring matching.

On top of keyword matches, a contextual bonus of up to 10 points is added:
- **Professional mode**: signals like "Senior", "Lead", "Principal", "Architect", "Manager" each add +2
- **Internship mode**: signals like "university", "final year", "GPA", "distinction", "project", "dissertation" each add +2

CVs are ranked highest-to-lowest by total score.

### 🦙 Ollama Mode (Local AI)

Ollama runs open-source LLMs on your local machine. The CV text (up to 6,000 characters) and job description are sent to the model, which returns a structured JSON assessment. No data leaves your computer.

The app uses a carefully engineered system prompt that instructs the model to return only a JSON object with no prose, no markdown fences, and no apostrophes or commas inside string values — which are the most common causes of parse failures in local models.

Even so, local models can sometimes produce slightly malformed JSON. The parser handles this with three progressive strategies:

1. **Standard parse** — strip markdown and call `json.loads()` directly
2. **Sanitise and retry** — extract the JSON block, replace smart/curly quotes, collapse embedded newlines, then retry
3. **Regex extraction** — if JSON is still unparseable, extract each field individually by pattern matching so you always get a result rather than a raw error

Recommended models (install with `ollama pull <name>`):

| Model | RAM Required | Notes |
|---|---|---|
| `phi3` | ~4 GB | Fastest, good for large batches |
| `llama3` | ~8 GB | Best balance of speed and quality |
| `mistral` | ~8 GB | Strong at structured reasoning |
| `gemma2` | ~9 GB | Very reliable JSON output |

### 🤖 OpenAI Mode

Works identically to Ollama mode in terms of what is evaluated and what is returned, but uses OpenAI's API. The same system prompts and JSON schema are used. The response parser is shared between both modes.

API keys are entered per-session in the sidebar and are never written to disk.

---

## Job Types in Detail

### 💼 Professional Role Mode

- Experience filter slider is shown; candidates outside the min/max range are rejected before AI analysis runs
- AI prompt instructs the model to assess experience level, seniority fit, and professional track record
- `experience_fit` values: `Too Junior`, `Good Fit`, `Overqualified`
- Seniority signals boost the keyword score

### 🎓 Internship / Entry Level Mode

- Experience filter is disabled entirely — no candidate is rejected based on years of experience
- AI prompt explicitly instructs the model *not* to penalise candidates for lacking work experience, and instead to focus on:
  - Academic background and GPA
  - University or personal projects
  - Relevant tools and skills learned
  - Open-source contributions
  - Learning potential and enthusiasm
- `experience_fit` values: `Student`, `Fresh Graduate`, `Has Some Experience`
- Academic signals boost the keyword score instead of seniority signals
- A 🎓 banner appears in results to confirm which mode was active

---

## Setting Up Ollama

**1. Download and install Ollama**

Visit [https://ollama.com/download](https://ollama.com/download) and install for your operating system (macOS, Windows, or Linux).

**2. Pull a model**

Open a terminal and run:

```bash
ollama pull llama3
```

This downloads the model weights (~4–8 GB depending on the model). You only need to do this once per model.

**3. Start the Ollama server**

On macOS, Ollama starts automatically after installation. On Windows and Linux, run:

```bash
ollama serve
```

This starts a local REST API at `http://localhost:11434`.

**4. Verify it is working**

The app sidebar will show a green ✅ message and auto-populate a dropdown of your installed models when Ollama is detected. If you see a warning instead, confirm that `ollama serve` is running in a terminal window.

---

## Keyword Configuration

Keywords are fully user-defined — there are no hardcoded defaults in the scoring engine. If you provide no keywords, all CVs score 0 on keyword matching (AI modes will still produce an AI score, but the Matched Keywords column will be empty).

**Tips for effective keywords:**

- Use the exact skill names that appear on CVs, not job posting language. CVs say "PostgreSQL", not "relational databases"
- Multi-word terms work well: "machine learning", "project management", "continuous integration"
- Assign higher weights to must-have skills and lower weights to nice-to-haves
- For internship roles, include academic tools and course-related terms: "React", "TensorFlow", "Arduino", "Figma"
- Keep your keyword list focused — 8 to 15 keywords typically gives a more meaningful spread of scores than 30+

---

## Understanding the Results

### Keyword Mode columns

| Column | Description |
|---|---|
| Rank | Position ordered by score (highest first) |
| Score | Total weighted keyword score plus contextual bonus |
| Exp (yrs) | Years of experience extracted from the CV |
| Matched Keywords | Which of your defined keywords were found in the CV |
| Summary | One-line human-readable summary of the match |

### AI Mode columns

| Column | Description |
|---|---|
| AI Score | 0–100 score assigned by the LLM based on overall fit for the role |
| Exp (yrs) | Years of experience extracted from the CV |
| Exp Fit / Candidate Level | Seniority fit label (Professional) or candidate stage (Internship) |
| Recommendation | 🟢 Strong Yes / 🟡 Yes / 🟠 Maybe / 🔴 No |

Each candidate also has an expandable card showing:
- **Strengths** — top positive signals identified by the AI
- **Gaps / Concerns** — missing skills or concerns flagged by the AI
- **AI Summary** — 2–3 sentence plain-English candidate summary
- **Rule-based Summary** — experience years and keyword match details from the local scorer

---

## Dependencies

| Package | Purpose | Required for |
|---|---|---|
| `streamlit` | Web UI framework | All modes |
| `PyPDF2` | PDF text extraction | All modes |
| `requests` | HTTP calls to Ollama REST API | Ollama mode |
| `pandas` | Data tables and CSV export | All modes |
| `openai` | OpenAI API client | OpenAI mode only |

Install everything at once:

```bash
pip install streamlit PyPDF2 requests pandas openai
```

---

## Troubleshooting

**CVs are being rejected with unexpected experience values**

The experience extractor picks the highest year span it can find in the document. If a CV mentions a publication year, award year, or graduation year that is far in the past, it can skew the inferred range. In Internship mode this never causes rejections. In Professional mode, try widening the experience slider, or switch to AI mode which evaluates experience contextually rather than by number alone.

**Ollama returns errors or empty results**

- Confirm Ollama is running: open a terminal and run `ollama serve`
- Confirm the model is downloaded: run `ollama list`
- If the model takes a long time to respond, it may still be loading into memory — wait 30 seconds and try again
- Try a smaller model like `phi3` if you are running low on RAM

**Ollama AI scores are all 0 with no strengths or gaps**

This means the model returned a response that even the regex fallback parser could not extract fields from. This is rare but can happen with very small or quantized models. Switch to `llama3` or `mistral` for more reliable structured output.

**OpenAI returns an authentication error**

Check that your API key starts with `sk-` and has not expired. Keys are not saved between sessions so you will need to re-enter it each time you open the app.

**Keyword scores are all 0**

No keywords have been defined, or the keywords tab that was active when you clicked Analyse had no content. Add keywords in the sidebar before running the analysis. A warning banner will appear in the sidebar if keywords are missing.
