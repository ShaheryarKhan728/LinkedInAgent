# LinkedIn Job Application Agent
---

## ⚙️ SETUP (One-time, 5 minutes)

### Step 1 — Install Python 3.10+
Download from https://python.org if not already installed.

### Step 2 — Install dependencies
Open terminal in the `linkedin_agent` folder and run:

```bash
pip install playwright
python -m playwright install chromium
```

### Step 3 — Place your resume
Copy your resume PDF into the `resumes/` folder and name it:
```
ShaheryarKhan_Resume.pdf
```

---

## ▶️ RUNNING THE AGENT

```bash
python main.py
```

You will be prompted for:
```
LinkedIn Email:    [type your email]
LinkedIn Password: [type your password — hidden, not stored]
```

The agent will then run **fully autonomously**.

---

## 👁️ WHAT YOU'LL SEE

A **real Chrome browser window** will open and you'll watch it:
1. Log into your LinkedIn account
2. Search for `.NET Developer` remote jobs in Europe, Singapore & US
3. Click each Easy Apply job
4. Fill in the form (name, experience, skills, etc.)
5. Upload a tailored resume (ATS-optimized for each job)
6. Fill cover letters where required
7. Submit the application
8. Move to the next job (with human-like delays)

---

## 📊 OUTPUT FILES

After the session, check the `output/` folder:
- `applications_YYYYMMDD_HHMMSS.csv` — Full log of every job applied to

Check `resumes/tailored/` for:
- One tailored resume text per job (ATS-optimized with job-specific keywords)

Check `logs/` for:
- Detailed debug log of every action taken

---

## ⚠️ IMPORTANT NOTES

| Topic | Detail |
|-------|--------|
| **Security** | Your credentials are typed at runtime and **never saved to disk** |
| **Daily Limit** | Agent applies to max 25 jobs/session to avoid LinkedIn flagging |
| **CAPTCHA** | If LinkedIn shows a security challenge, complete it manually in the browser — agent waits 60 seconds |
| **Browser** | Chrome runs in **visible mode** so you can monitor it |
| **Rate Limiting** | Human-like delays of 4–12 seconds between actions |

---

## 🎯 JOB SEARCH CONFIGURATION

Configured in `main.py`:
- **Keywords**: `.NET Developer`, `.NET Core Developer`, `C# Developer`, `Backend .NET Engineer`, `Software Engineer .NET`
- **Locations**: Europe, Singapore, United States
- **Type**: Remote only
- **Level**: Mid-Senior (2–4 years experience)
- **Filter**: Easy Apply only

---

## 🔧 CUSTOMIZATION

Edit `main.py` to change:
- `max_jobs_per_session` — How many jobs per run (default: 25)
- `search_keywords` — Add/remove job titles
- `target_locations` — Add/remove locations

Edit `core/easy_apply_handler.py` → `CANDIDATE_PROFILE` to update:
- Phone, city, notice period, salary expectations

---

## 🆘 TROUBLESHOOTING

**Login fails:** Double-check credentials. If 2FA is enabled on your account, you may need to temporarily disable it or handle the OTP manually in the browser window.

**No jobs found:** LinkedIn may have changed their HTML structure. Check `logs/` for details.

**CAPTCHA every time:** LinkedIn sometimes challenges automation. Try running at different times of day, or reduce `max_jobs_per_session` to 10.

**Resume upload fails:** Ensure `resumes/ShaheryarKhan_Resume.pdf` exists in the folder.
