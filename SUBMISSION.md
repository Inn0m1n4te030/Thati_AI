# Thati AI — hackathon submission draft

Sources: `UI_SPEC.md`, `FINAL_CHECKLIST.md`, git history, and the current app. **`PLAN.md` is not in the repository.**

Replace the live URL placeholder before submitting.

---

**Project name:** Thati AI (သတိ)

**Participant / team:** Moe Thu Kyaw

**Live URL:** [https://your-host/] — public UI `/`, health `/health`, admin `/admin` (not linked from the public page). *Deployed `/health` was not verified in the freeze audit; paste the URL only after you have confirmed it.*

---

## Problem

People in Myanmar receive OTP-pressure SMS, fake “bank” chats, and job scams that mix Burmese and English. Recipients need a way to inspect a **message pattern** — quoted pressure, identifiers, and safer next steps — without treating a paste as a police verdict or publishing raw IDs.

## Solution

Thati AI is an evidence-first **screening aid**. A user pastes untrusted text; the service returns a structured assessment (summaries, required uncertainty, exact-substring quotes, extracted identifiers, non-accusatory actions). A separate pending **report** can be sent for humans. Only a reviewer with an admin token can approve selected identifiers onto a **hashed, masked** match list. AI never writes that list. The list is a community review log, **not** an authoritative or official blacklist.

The public UI states that results are screening, not a finding that a person committed a crime.

## Core working functionality

Confirmed by `FINAL_CHECKLIST.md` (mock mode, 2026-08-29):

- `GET /health` → mock, ready
- Text analysis (`POST /api/analyze/text`) on a fictional KBZ OTP fixture: quoted evidence, URL and phone entities, screening risk label
- Pending report (`POST /api/reports`) that does **not** create a list hit
- Admin routes reject missing tokens (`401`)
- Human approval of a **fictional** URL, then **exact** hashed match (`GET /api/blacklist/check`); a near-miss URL does not match
- Public `/` and `/admin` load; static JS/CSS load; browser console clean in the audit
- 74 automated tests; Python compile; JS syntax checks
- No `.env` or SQLite files tracked

Screenshot and voice **tabs exist** in the UI, and the repo includes mock/live client code plus tests. The freeze audit **did not** confirm image OCR, live Gemini, or live transcription. Mock screenshots use synthetic text, not pixels. Do not demo those as proven live features.

## Meaningful AI contribution

Live path (same interface as mock): server-side Gemini with a JSON schema (`FraudAssessment`), low temperature, evidence-first system prompt, and an untrusted-message wrapper so jailbreaks in the paste are data, not instructions. Quotes and entity values must appear in the source text. The model must not say a person is a criminal. `risk_score` is a screening indicator, not a probability.

**Audit honesty:** the freeze run used **mock** screening. Live Gemini was not exercised there. Mock returns a deterministic structured assessment so the product can be demonstrated without a key.

## How Cursor was used (Build Window)

The Build Window was run as a Cursor Cloud Agent against this repo: scaffold (FastAPI + static `web/`), Pydantic contract and validators, mock then live Gemini clients, hashed human-review workflow, admin token gate, Docker/Compose for a single non-root image, pytest throughout, Mobbin-informed `UI_SPEC.md` then original Myanmar UI, and a feature-freeze submission audit (`FINAL_CHECKLIST.md`). Secrets were kept out of git. The agent used Cursor tools for tests, local HTTP checks, and a browser console pass on mock pages.

## How Mobbin MCP informed UI

Patterns were **observed** on Mobbin, then rewritten for Thati (no brand clones):

| Thati | Informed by |
| --- | --- |
| Risk header, stacked safe-action cards, protect-don’t-accuse voice | Revolut “Secure your account” |
| Compose dock, attach vs primary analyze, file chip + remove | ChatGPT iOS composer |
| Preview before commit, persistent trust banner | WhatsApp Web send-document |
| Pending / approve / reject review desk | Circle content moderation |
| In-progress card, disabled primary, cancel | Confluence document import |

Lime chips are reserved for **human-reviewed** list matches, not AI scores. Copy is Myanmar-first.

## Technologies and third-party resources

- Python 3.12, FastAPI, Uvicorn (one worker), Pydantic Settings, SQLite
- Plain HTML/CSS/JS (`web/`); no React
- `google-genai` (live only; key never sent to the browser)
- FFmpeg in the Docker image (audio conversion; not part of the freeze HTTP audit)
- Docker Compose, host port 80 → 8000, volume `/data`
- Gemini model names in `.env.example` placeholders (`gemini-3.7-flash`, `gemini-3.5-transcribe`)
- Mobbin (design reference only)
- Fictional demo identifiers only (`09-123456789`, `https://kbz-secure-login.example/otp`)

## Honest limitations

- Screening aid, not law enforcement, a bank, or a court. Does **not** determine that a person is a criminal.
- Reviewed list is hashed exact-match only, masked on display, **not** authoritative, complete, or official.
- List entries require **human review**; AI cannot approve them.
- Live model and transcription need `APP_MODE=live` and a server-side `GEMINI_API_KEY`; not verified in the freeze audit.
- Mock screenshot path does not OCR. Mic recording usually needs HTTPS; file upload can work on HTTP.
- Docker image was not built in the audit environment. No production URL was verified.
- Public page does not link to `/admin` (by design).

## Three-minute demo sequence

Use **mock** mode unless live `/health` shows `mode: live`. Use **fictional** text only.

1. **0:00** Open `[live URL]/`. Point out the mock/live badge and the banner: screening, not a crime finding.
2. **0:20** Paste the OTP fixture (Myanmar “KBZ” close-account pressure, `09-123456789`, `https://kbz-secure-login.example/otp`). Analyze. Show quoted OTP/URL evidence, uncertainty, safe actions, identifiers from **this paste**.
3. **1:10** Open blacklist check for that URL → no match yet. Submit a report with the confirmation checkbox. Show “pending”; AI did not add the list.
4. **1:40** Open `/admin` (typed URL). Session token. Load pending queue. Approve **only the URL** (not “this person is guilty”). Rejected-token case: no token → unauthorized.
5. **2:20** Back to `/`. Exact URL check → match, **masked** display. A slightly different URL does not match. Restate: human-reviewed exact hashes, not an official blacklist.
6. **2:45** Optional: `GET /health`. Stop. Do not spend remaining time on screenshot/voice unless you separately show live OCR/transcription.

---

Copy-paste block (form fields):

```
Project: Thati AI (သတိ)
Team: Moe Thu Kyaw
Live URL: [https://your-host/]

Problem: Myanmar users receive OTP-pressure and fake-institution messages. They need quoted screening of the message, not a verdict about a person.

Solution: Evidence-first paste-to-assessment tool plus a pending report queue. Blacklist-style matches are hashed, masked, exact-match only, and require human approval. AI never writes the list. The list is not authoritative.

Working (mock audit): health, text analyze, pending reports, admin 401, human URL approval, exact list match, public and admin pages. 74 tests.

AI: Structured Gemini assessment (quotes must appear in the source; no criminal-person claims). Freeze demo used mock; live Gemini not audited.

Cursor: Cloud Agent built API, contract, mock/live clients, human review, Docker, tests, Mobbin-based UI spec, and the audit checklist.

Mobbin: Revolut (calm risk + actions), ChatGPT iOS (composer), WhatsApp (preview + trust), Circle (review desk), Confluence (progress). Original Myanmar UI.

Stack: FastAPI, SQLite, static HTML/CSS/JS, Docker, google-genai. FFmpeg in image.

Limits: Not a criminal finding. List not official. Human review required. Live AI/OCR/transcription not confirmed in freeze audit.
```
