import streamlit as st
import os
import shutil
import pandas as pd
from shortlist import (
    extract_text, analyze_cv,
    analyze_cv_with_openai,
    analyze_cv_with_ollama,
    analyze_cv_with_claude,
    list_ollama_models
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="CV Analyser",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📑 CV Analysing App")
st.caption("Upload candidate CVs and rank them using keyword scoring or AI-powered analysis.")

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "mode" not in st.session_state:
    st.session_state.mode = "keyword"
if "job_type" not in st.session_state:
    st.session_state.job_type = "professional"


# ─────────────────────────────────────────────
# SIDEBAR: CONFIGURATION
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    # --- Analysis Mode ---
    st.subheader("Analysis Mode")
    mode = st.radio(
        "Select mode",
        options=["keyword", "claude", "ollama", "openai"],
        format_func=lambda x: {
            "keyword": "🔍 Keyword Scoring",
            "claude":  "🤖 Claude (Anthropic API)",
            "ollama":  "🦙 Ollama (Local, Free)",
            "openai":  "🔵 OpenAI (API Key required)",
        }[x],
        index=0,
    )
    st.session_state.mode = mode

    st.divider()

    # --- Job Type ---
    st.subheader("Job Type")
    job_type = st.radio(
        "Select job type",
        options=["professional", "internship"],
        format_func=lambda x: "💼 Professional Role" if x == "professional" else "🎓 Internship / Entry Level",
        index=0,
        help="Internship mode disables experience filtering and adjusts AI evaluation criteria."
    )
    st.session_state.job_type = job_type

    st.divider()

    # --- Experience Filter (Professional only) ---
    if job_type == "professional":
        st.subheader("Experience Filter")
        exp_min, exp_max = st.slider(
            "Preferred years of experience (reference only)",
            min_value=0, max_value=30, value=(0, 15),
            help="This is logged for reference only and does not reject CVs from shortlisting."
        )
    else:
        exp_min, exp_max = 0, 99   # effectively disabled
        st.info("🎓 Experience filter is **disabled** for internship analysis. All candidates are evaluated on skills and potential.")

    st.divider()

    # --- Keyword Configuration (all modes) ---
    st.subheader("🔑 Keywords")
    st.caption("Used for scoring in all modes. In AI mode, matched keywords are shown alongside AI results.")

    kw_tab_simple, kw_tab_advanced = st.tabs(["✏️ Simple", "⚖️ With Weights"])

    with kw_tab_simple:
        st.caption("Type keywords separated by commas. All keywords get equal weight (10).")
        simple_input = st.text_area(
            "Keywords",
            placeholder="e.g. python, aws, docker, kubernetes, sql",
            height=100,
            label_visibility="collapsed",
        )
        if simple_input.strip():
            job_keywords = {
                kw.strip().lower(): 10
                for kw in simple_input.split(",")
                if kw.strip()
            }
        else:
            job_keywords = {}

    with kw_tab_advanced:
        st.caption("Set individual weights (1–20). Higher weight = more important skill.")
        default_kw_rows = [
            {"Keyword": "python",          "Weight": 10},
            {"Keyword": "aws",             "Weight": 10},
            {"Keyword": "docker",          "Weight": 8},
            {"Keyword": "kubernetes",      "Weight": 8},
            {"Keyword": "terraform",       "Weight": 7},
            {"Keyword": "machine learning","Weight": 6},
            {"Keyword": "sql",             "Weight": 5},
            {"Keyword": "java",            "Weight": 4},
            {"Keyword": "leadership",      "Weight": 5},
            {"Keyword": "communication",   "Weight": 3},
        ]
        edited_kw = st.data_editor(
            pd.DataFrame(default_kw_rows),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Keyword": st.column_config.TextColumn("Keyword"),
                "Weight": st.column_config.NumberColumn("Weight", min_value=1, max_value=20),
            }
        )
        advanced_keywords = {
            row["Keyword"].strip().lower(): int(row["Weight"])
            for _, row in edited_kw.iterrows()
            if str(row["Keyword"]).strip()
        }
        # Advanced tab overrides simple if user has edited it
        if advanced_keywords:
            job_keywords = advanced_keywords

    if not job_keywords:
        st.warning("⚠️ No keywords defined — add some above for better scoring.")

    st.divider()

    # --- Rejection Threshold ---
    st.subheader("🚫 Rejection Threshold")
    reject_below = st.number_input(
        "Reject CVs with weighted keyword match below (%)",
        min_value=0, max_value=100, value=60, step=5,
        help="Match % = sum of matched keyword weights ÷ sum of all keyword weights × 100. "
             "Set to 0 to disable rejection. In AI modes, rejected CVs are not sent to the AI."
    )
    hide_rejected = st.checkbox("Hide rejected CVs from results", value=False)

    st.divider()

    # --- Ollama Config ---
    if mode == "ollama":
        st.subheader("🦙 Ollama Settings")
        ollama_url = st.text_input(
            "Ollama server URL",
            value="http://localhost:11434",
            help="Default is localhost. Change only if running Ollama on another machine."
        )
        # Try to detect locally available models
        detected_models = list_ollama_models(ollama_url)
        RECOMMENDED = ["llama3", "llama3.2", "mistral", "phi3", "gemma2", "qwen2.5"]

        if detected_models:
            st.success(f"✅ Ollama is running — {len(detected_models)} model(s) found")
            ollama_model = st.selectbox("Select model", options=detected_models, index=0)
        else:
            st.warning("⚠️ Ollama not detected. Is it running? See setup steps below.")
            ollama_model = st.selectbox(
                "Model name (type manually if not detected)",
                options=RECOMMENDED,
                index=0,
            )

        with st.expander("📖 How to set up Ollama"):
            st.markdown("""
**Step 1 — Install Ollama**
```
https://ollama.com/download
```
Download and install for macOS, Windows, or Linux.

**Step 2 — Pull a model** (run in terminal)
```bash
ollama pull llama3
```
Other good options: `mistral`, `phi3`, `gemma2`

**Step 3 — Start the server** (if not auto-started)
```bash
ollama serve
```

**Step 4 — Come back here and upload CVs!**
No API key needed. Runs 100% on your machine.
""")

    # --- Claude Config ---
    if mode == "claude":
        st.subheader("🤖 Claude Settings")
        claude_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Your key is only used for this session and never stored."
        )
        claude_model = st.selectbox(
            "Model",
            options=["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
            index=0,
            help="Opus 4.7 is most capable. Sonnet 4.6 balances speed and quality. Haiku 4.5 is fastest."
        )
        st.caption("💡 **Tip:** Haiku 4.5 costs ~$0.001 per CV. Opus 4.7 gives the deepest insights.")

    # --- OpenAI Config ---
    if mode == "openai":
        st.subheader("🤖 OpenAI Settings")
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Your key is only used for this session and never stored."
        )
        openai_model = st.selectbox(
            "Model",
            options=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
            index=0,
            help="gpt-4o-mini is fastest and most cost-effective."
        )
        st.caption("💡 **Tip:** gpt-4o-mini costs ~$0.001 per CV. gpt-4o gives deeper insights.")

    st.divider()

    # --- Job Description ---
    st.subheader("📝 Job Description")
    job_description = st.text_area(
        "Paste the job description here",
        height=200,
        placeholder="e.g. We are looking for a Senior Python Developer with 3–7 years of experience in AWS, Docker, and Kubernetes...",
        help="Used by AI mode for richer matching. Also used for keyword mode display."
    )


# ─────────────────────────────────────────────
# MAIN AREA: FILE UPLOAD
# ─────────────────────────────────────────────
st.subheader("📁 Upload CVs")
uploaded_files = st.file_uploader(
    "Upload PDF CVs (multiple allowed)",
    type=["pdf"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

analyse_btn = st.button("▶ Analyse CVs", type="primary", disabled=not uploaded_files)

# ─────────────────────────────────────────────
# PROCESSING
# ─────────────────────────────────────────────
if analyse_btn and uploaded_files:
    if mode == "claude" and not claude_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
        st.stop()
    if mode == "openai" and not openai_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        st.stop()
    if mode in ("claude", "openai", "ollama") and not job_description.strip():
        st.warning("⚠️ No job description provided. AI analysis will be less accurate.")

    results = []
    os.makedirs("temp", exist_ok=True)
    progress = st.progress(0, text="Processing CVs…")

    for i, uploaded_file in enumerate(uploaded_files):
        progress.progress((i) / len(uploaded_files), text=f"Analysing: {uploaded_file.name}")
        file_path = os.path.join("temp", uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        cv_text = extract_text(file_path)

        if mode == "keyword":
            analysis = analyze_cv(
                cv_text,
                job_keywords=job_keywords,
                min_exp=exp_min,
                max_exp=exp_max,
                job_type=job_type,
                reject_below=reject_below,
            )
            results.append({
                "filename": uploaded_file.name,
                "score": analysis["score"],
                "match_pct": analysis["match_pct"],
                "rejected": analysis["rejected"],
                "experience_years": analysis["experience_years"],
                "matched_keywords": analysis["matched_keywords"],
                "summary": analysis["summary"],
                "mode": "keyword",
                "job_type": job_type,
            })

        else:  # claude, ollama or openai
            kw_analysis = analyze_cv(cv_text, job_keywords=job_keywords, min_exp=exp_min, max_exp=exp_max, job_type=job_type, reject_below=reject_below)
            if kw_analysis["rejected"]:
                # Skip the AI call for CVs below the keyword threshold
                results.append({
                    "filename": uploaded_file.name,
                    "score": 0,
                    "match_pct": kw_analysis["match_pct"],
                    "rejected": True,
                    "experience_years": kw_analysis["experience_years"],
                    "matched_keywords": kw_analysis["matched_keywords"],
                    "summary": kw_analysis["summary"],
                    "ai_score": 0,
                    "strengths": [],
                    "gaps": [],
                    "experience_fit": "Rejected",
                    "recommendation": "No",
                    "ai_summary": "AI analysis skipped — CV rejected by keyword match threshold.",
                    "mode": mode,
                    "job_type": job_type,
                })
            else:
                jd = job_description.strip() or ("Internship role." if job_type == "internship" else "General software engineering role.")
                if mode == "claude":
                    ai = analyze_cv_with_claude(cv_text, jd, api_key=claude_key, model=claude_model, job_type=job_type)
                elif mode == "ollama":
                    ai = analyze_cv_with_ollama(cv_text, jd, model=ollama_model, ollama_url=ollama_url, job_type=job_type)
                else:
                    ai = analyze_cv_with_openai(cv_text, jd, api_key=openai_key, model=openai_model, job_type=job_type)

                results.append({
                    "filename": uploaded_file.name,
                    "score": ai["ai_score"],
                    "match_pct": kw_analysis["match_pct"],
                    "rejected": False,
                    "experience_years": kw_analysis["experience_years"],
                    "matched_keywords": kw_analysis["matched_keywords"],
                    "summary": kw_analysis["summary"],
                    "ai_score": ai["ai_score"],
                    "strengths": ai["strengths"],
                    "gaps": ai["gaps"],
                    "experience_fit": ai["experience_fit"],
                    "recommendation": ai["recommendation"],
                    "ai_summary": ai["summary"],
                    "mode": mode,
                    "job_type": job_type,
                })

    progress.progress(1.0, text="✅ Done!")
    # Shortlisted CVs first, then by score
    st.session_state.results = sorted(results, key=lambda x: (not x["rejected"], x["score"]), reverse=True)


# ─────────────────────────────────────────────
# RESULTS DISPLAY
# ─────────────────────────────────────────────
if st.session_state.results:
    st.divider()
    st.subheader("📊 Ranked Results")

    all_results = st.session_state.results
    rejected_count = sum(1 for r in all_results if r.get("rejected"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Total CVs", len(all_results))
    c2.metric("✅ Shortlisted", len(all_results) - rejected_count)
    c3.metric("❌ Rejected", rejected_count)

    results = [r for r in all_results if not r.get("rejected")] if hide_rejected else all_results
    if not results:
        st.info("All CVs were rejected by the keyword match threshold. Untick 'Hide rejected CVs' to see them.")
        st.stop()

    def fmt_pct(r):
        return f"{r['match_pct']}%" if r.get("match_pct") is not None else "—"

    def status(r):
        return "❌ Rejected" if r.get("rejected") else "✅ Shortlisted"

    result_mode = results[0].get("mode", "keyword")
    result_job_type = results[0].get("job_type", "professional")
    is_ai_mode = result_mode in ("claude", "openai", "ollama")
    exp_fit_label = "Candidate Level" if result_job_type == "internship" else "Exp Fit"

    if result_job_type == "internship":
        st.info("🎓 Results shown in **Internship mode** — candidates evaluated on skills and potential, not experience.")

    # ── Summary table ──
    if result_mode == "keyword":
        table_data = []
        for rank, r in enumerate(results, 1):
            table_data.append({
                "Rank": rank,
                "Status": status(r),
                "Filename": r["filename"],
                "Score": r["score"],
                "Match %": fmt_pct(r),
                "Exp (yrs)": r["experience_years"],
                "Matched Keywords": ", ".join(r["matched_keywords"]) or "—",
                "Summary": r["summary"],
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    else:  # openai or ollama
        RECO_COLORS = {
            "Strong Yes": "🟢",
            "Yes": "🟡",
            "Maybe": "🟠",
            "No": "🔴",
            "Error": "⚫",
        }
        table_data = []
        for rank, r in enumerate(results, 1):
            reco = r.get("recommendation", "—")
            table_data.append({
                "Rank": rank,
                "Status": status(r),
                "Filename": r["filename"],
                "AI Score": r.get("ai_score", "—"),
                "Match %": fmt_pct(r),
                "Exp (yrs)": r["experience_years"],
                exp_fit_label: r.get("experience_fit", "—"),
                "Recommendation": f"{RECO_COLORS.get(reco, '')} {reco}",
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Expandable detail cards ──
    st.subheader("🗂️ Detailed Candidate Cards")
    for rank, r in enumerate(results, 1):
        label = f"#{rank} — {r['filename']}  |  Score: {r['score']}  |  Match: {fmt_pct(r)}  |  {status(r)}"
        with st.expander(label, expanded=(rank == 1)):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Score", r["score"])
                st.metric("Keyword Match", fmt_pct(r))
                st.metric("Experience", f"{r['experience_years']} yrs")
                if r.get("matched_keywords"):
                    st.markdown("**Matched Keywords:**")
                    st.markdown(", ".join(f"`{k}`" for k in r["matched_keywords"]))
                else:
                    st.markdown("_No keyword matches_")

            with col2:
                if is_ai_mode:
                    rec = r.get("recommendation", "—")
                    st.metric("AI Score", r.get("ai_score", "—"))
                    st.metric("Recommendation", rec)
                    st.metric(exp_fit_label, r.get("experience_fit", "—"))

            if is_ai_mode:
                st.markdown("**AI Summary:**")
                st.info(r.get("ai_summary", "—"))
                s_col, g_col = st.columns(2)
                with s_col:
                    if r.get("strengths"):
                        st.markdown("✅ **Strengths**")
                        for s in r["strengths"]:
                            st.markdown(f"- {s}")
                with g_col:
                    if r.get("gaps"):
                        st.markdown("⚠️ **Gaps / Concerns**")
                        for g in r["gaps"]:
                            st.markdown(f"- {g}")

            st.markdown("**Rule-based Summary:**")
            st.caption(r["summary"])

    # ── Export ──
    st.divider()
    if is_ai_mode:
        export_rows = []
        for rank, r in enumerate(results, 1):
            export_rows.append({
                "Rank": rank,
                "Status": "Rejected" if r.get("rejected") else "Shortlisted",
                "Filename": r["filename"],
                "AI Score": r.get("ai_score", ""),
                "Match %": r.get("match_pct", ""),
                "Exp (yrs)": r["experience_years"],
                "Exp Fit": r.get("experience_fit", ""),
                "Recommendation": r.get("recommendation", ""),
                "Strengths": "; ".join(r.get("strengths", [])),
                "Gaps": "; ".join(r.get("gaps", [])),
                "AI Summary": r.get("ai_summary", ""),
            })
    else:
        export_rows = []
        for rank, r in enumerate(results, 1):
            export_rows.append({
                "Rank": rank,
                "Status": "Rejected" if r.get("rejected") else "Shortlisted",
                "Filename": r["filename"],
                "Score": r["score"],
                "Match %": r.get("match_pct", ""),
                "Exp (yrs)": r["experience_years"],
                "Matched Keywords": ", ".join(r["matched_keywords"]),
                "Summary": r["summary"],
            })

    export_df = pd.DataFrame(export_rows)
    csv = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Results as CSV",
        data=csv,
        file_name="shortlisted_cvs.csv",
        mime="text/csv"
    )

    # ── Clear ──
    if st.button("🗑️ Clear All Results"):
        st.session_state.results = []
        st.session_state.uploader_key += 1
        temp_folder = "temp"
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)
            os.makedirs(temp_folder)
        st.rerun()
