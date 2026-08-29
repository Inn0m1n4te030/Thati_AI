# Thati AI UI specification

This spec is for the public screening surface and the human-review admin surface. It is original Thati AI, not a branded clone. Patterns below were observed in Mobbin references and then restated for Myanmar fraud screening.

**Do not implement HTML, CSS, or JavaScript from this file until it is approved.**

## Chosen Mobbin references (maximum five)

| # | Role in Thati | Source |
| --- | --- | --- |
| 1 | Security / risk review | [Revolut — Secure your account](https://mobbin.com/screens/f32234af-d71b-4c32-ad84-8aa4edc49b3f) |
| 2 | Text / file / voice composer | [ChatGPT iOS — composer with attach, preview, mic, send](https://mobbin.com/screens/594e1411-90e5-481f-8e5c-804534dcfba6) |
| 3 | File preview before commit + trust banner | [WhatsApp Web — sending a document](https://mobbin.com/flows/fa7037b7-2e7b-468f-9e49-f09e2867b736) |
| 4 | Report-review dashboard | [Circle — Approving a content](https://mobbin.com/flows/a50bc33f-7773-4efc-85a3-25fc2bd13e69) |
| 5 | Loading / in-progress analysis | [Confluence — importing a document](https://mobbin.com/screens/4ca4995a-8a4f-4c55-b89c-346f0c0b269e) |

Supporting observations (not counted as the five): [SchoolAI upload modal](https://mobbin.com/screens/e27bec82-a8d5-4aca-8b31-a89d8d4efc64) (selected-file count + remove), [Digg report submitted toast](https://mobbin.com/flows/3e4c73a4-a877-418a-a775-60a9f87bdded) (completed report copy).

---

## Reference notes (what was actually on screen)

### 1. Revolut — Secure your account (web, mobile-width)

- **Hierarchy:** Back control, large purpose title, short “we will do the following” line, then two stacked action cards (icon, bold action, supporting count, expand chevron), then a one-line reassurance, then Confirm.
- **Primary action:** Full-width pill **Confirm** pinned to the bottom thumb zone after the user has read the cards.
- **Trust/safety copy:** Frames the work as protection (“To protect your account…”). Reassurance sits *above* Confirm (“You can unfreeze your cards later”), which lowers panic.
- **Loading / error:** Not shown. Status is implied by a calm, complete checklist before commit.
- **Mobile:** Single column, large type, generous padding, no competing side actions.

**Use for Thati:** Risk result header, safe-action cards, non-accusatory framing, bottom primary action on phones.

### 2. ChatGPT iOS — multimodal composer

- **Hierarchy:** Thin header; large empty conversation; all work in a bottom dock: `+` attach, rounded field, selected-file thumbnail with **X**, placeholder, mic, high-contrast circular send.
- **Primary action:** Send is a separate filled circle (black on that screen), not mixed with attach.
- **Trust/safety copy:** Almost none in the chrome; trust comes from a quiet, uncluttered field.
- **Loading / error:** Empty thread is just whitespace waiting for the first send.
- **Mobile:** Thumb-reach dock; attach and send are distinct hit targets so attach is not accidental send.

**Use for Thati:** Public compose dock (text + screenshot + voice), selected-file chip, empty first-run.

### 3. WhatsApp Web — sending a document

- **Hierarchy:** Chat list stays visible; workspace switches to a **large file preview**, filename and page count, caption field, then send. After send, the file becomes a card (thumbnail, name, type, size).
- **Primary action:** Circular send, bottom-right of the preview stage; **X** cancels before send.
- **Trust/safety copy:** Pale banner with lock: encryption is explained in one sentence plus “learn more”. Repeated in the list footer. Not a scare headline.
- **Loading / error:** Preview is the gate: user sees the file before the system treats it as submitted.
- **Mobile:** Same composer grammar (`+`, field, mic). Desktop keeps a list | detail split.

**Use for Thati:** Screenshot/voice preview *before* Analyze; persistent “screening aid, not a verdict” banner; evidence shown as a readable card, not a dump.

### 4. Circle — Approving a content (moderation)

- **Hierarchy:** Title **Moderation**; tabs **Inbox / Approved / Rejected** with counts; table of flagged items; row action **Review**. Detail is a modal: what was flagged, **Details | Reports**, reasons in grey boxes, then **Approve** (neutral) and **Reject** (high-contrast destructive).
- **Primary action:** List uses a text **Review**. Modal puts decisions at the bottom-right. After success, a dark pill toast: “Content approved”. Empty inbox: “No data available” plus “0 reports”.
- **Trust/safety copy:** Neutral words (“flagged content”), not “criminal”. Counts make workload honest.
- **Loading / error:** Empty is a sentence in the table body, not a dead page. Completed work is a toast, not a navigation jump.
- **Mobile:** Modal becomes a full-screen sheet; two decision buttons stack at the bottom.

**Use for Thati admin:** Pending / approved / rejected tabs, review sheet, approve only after entity indexes, toast on success.

### 5. Confluence — importing a document

- **Hierarchy:** Dimmed page; centered modal; illustration; status label **Importing document…**; percent + bar; **Cancel** enabled; **Finish** disabled until done.
- **Primary action:** Finish stays disabled during work so the user cannot skip a half-finished import.
- **Trust/safety copy:** Friendly illustration; no threat language.
- **Loading / error:** Determinate progress; cancel is always available. Error is not on this frame; Thati should add a retry on the same card.
- **Mobile:** Full-screen progress sheet, same disable/enable rule.

**Use for Thati:** Analyze in progress — bar or pulse, disable Analyze, allow cancel, then swap to the result.

---

## Original Thati design system

### Intent

Calm enough to read Myanmar at phone size. Urgent only when the *message pattern* is high or critical. Lime only for **human-reviewed blacklist match** and other verified-human facts. Never lime for an AI score.

### Color (names, not a brand kit)

| Token | Role |
| --- | --- |
| `ink` | Near-black page chrome, primary text (`#14110E` range) |
| `paper` | Warm paper page and cards (`#F4EFE6` range) |
| `paper-raised` | Slightly lighter card (`#FBF7F0`) |
| `rule` | Hairline separators (`ink` at ~12% opacity) |
| `urgent` | High/critical pattern, destructive reject, OTP pressure (`#E25A12` range) |
| `urgent-soft` | Wash behind high-risk banner |
| `lime` | Human-verified match, “reviewed” chips (`#C6F25A` on `ink`, not neon on paper) |
| `mute` | Secondary text (`ink` at ~55%) |
| `danger-text` | Errors only (`#8B1E1E` range), never for “this person is guilty” |

Low/medium results stay on paper + ink. Do not paint the whole screen orange.

### Type

- UI chrome: one geometric sans that supports Myanmar (system stack first: `Noto Sans Myanmar`, `Padauk`, then `ui-sans-serif`).
- Myanmar body: **minimum 17px** on mobile, **line-height 1.65**, slightly looser tracking than English.
- Do not lock Myanmar into 12px table cells. Admin tables wrap; row height grows.
- Risk score is a **screening indicator** label, never “probability %”.

### Shape and motion

- Cards: 12–16px radius. Buttons: full pill on mobile CTAs.
- Motion: short (150–220ms), opacity + small translate. No celebratory confetti on a fraud tool.
- Focus rings: 2px `urgent` on paper, `lime` on ink bars.

### Voice

- Myanmar first on public UI; English as secondary line where needed (summaries already exist in the API).
- Copy pattern from Revolut + WhatsApp: **protect / explain / reassure**, never accuse a person.
- Banner example: “ဤရလဒ်သည် စာသားပုံစံ စစ်ဆေးချက်သာ ဖြစ်သည်။ လူတစ်ဦးကို ပြစ်မှုကျူးလွန်သူဟု မသတ်မှတ်ပါ။”
- Report thanks (Digg-style, rewritten): “ပေးပို့ပြီးပါပြီ။ လူက သုံးသပ်မှသာ စာရင်းသွင်းပါမည်။”

---

## Page structure

Two routes only for v1 UI (matches the backend):

1. **Public — `/` screening studio**
2. **Admin — `/admin` review desk** (token field or header already required by API)

### Public: screening studio

Mobile (default):

1. Sticky top: wordmark **သတိ**, mode chip (`mock` / `live`), one-line trust banner.
2. Scroll: empty/loading/result region.
3. Sticky bottom **compose dock** (ChatGPT iOS + WhatsApp):
   - `+` attach screenshot (disabled visually until image API exists; still show the control so layout is stable).
   - Mic for voice (same).
   - Textarea (Myanmar placeholder: “သံသယရှိသော စာကို ဤနေရာတွင် ကူးထည့်ပါ”).
   - Selected-file row: thumbnail or filename, size, **X**.
   - Primary **စစ်ဆေးရန်** (Analyze) as a filled `ink` pill; disabled while empty or loading.

Desktop (≥880px):

- Left ~42%: compose + preview (WhatsApp list|detail idea, but Thati is not a chat log).
- Right ~58%: result column (Revolut cards + evidence).
- Trust banner spans the top of the result column, not a yellow WhatsApp clone — use `paper-raised` + lock-equivalent icon in `ink`.

### Result column (after analysis)

Order (Revolut: status first, then actions, then metadata):

1. **Status strip:** risk level word (low / medium / high / critical) + numeric screening score with caption “ညွှန်းကိန်း၊ ဖြစ်နိုင်ခြေ မဟုတ်”.
2. If human blacklist hits: **lime chip** “လူက အတည်ပြုထားသော စာရင်းနှင့် တူ”.
3. Myanmar summary, then English summary in `mute`.
4. **Uncertainty** in its own card (mandatory, always visible).
5. **Quoted evidence:** original text with marks; each quote is a block with Myanmar explanation.
6. **Identifiers:** chips, masked when talking about the blacklist; exact values only as they appeared in *this* paste.
7. **Safe actions:** Revolut-style stacked cards, checkable reading order, not a lecture.
8. Secondary **သတင်းပို့ရန်** (submit pending report) — not the same visual weight as Analyze.

### Admin: review desk (Circle)

- Title **စစ်ဆေးရန် တောင်းဆိုမှုများ**.
- Tabs: စောင့်ဆိုင်း / အတည်ပြုပြီး / ငြင်းပယ် (`pending` / `approved` / `rejected`) with counts.
- Rows: time, excerpt (max ~2 Myanmar lines), masked entity list, **ကြည့်ရန်**.
- Sheet/modal: excerpt, entity index checkboxes (human must pick indexes), reason field, **အတည်ပြု** (`ink`) vs **ငြင်းပယ်** (`urgent` outline or fill — reject is serious but not “this person is guilty”).
- Empty tab: short sentence, no cartoon mascot (Reddit’s cat is off-brand). Example: “စောင့်ဆိုင်းနေသော အချက် မရှိပါ။”

---

## Responsive behavior

| Breakpoint | Behavior |
| --- | --- |
| &lt; 600px | Single column; dock sticky; Analyze full width; admin tabs scroll horizontally; review is a full-height sheet; buttons stacked. |
| 600–879px | Same, slightly wider cards; two safe-action cards per row if they fit without crushing Myanmar. |
| ≥ 880px | Public split compose | result. Admin: table + right drawer or modal (Circle desktop). |
| Keyboard | Analyze is Enter in textarea with a hint; Shift+Enter newline. Focus visible. |
| Reduced motion | Instant state swap, no bar animation. |

Touch targets ≥ 44px. Myanmar labels may wrap; buttons grow in height, they do not shrink type.

---

## Component states

### Empty (no analysis yet)

Informed by ChatGPT empty thread + Circle “No data available”.

- Center of the result pane: short Myanmar prompt + three example chips (OTP SMS, job chat, “benign lunch”).
- No fake “100% safe” empty graphic.

### Loading

Informed by Confluence import.

- Result pane replaced by a card: “စစ်ဆေးနေသည်…” + indeterminate or determinate bar if the client can estimate.
- Analyze disabled; **ပယ်ဖျက်** (cancel) enabled if the request can abort.
- Compose dock stays, dimmed.

### Error

Not shown on the Confluence frame; Thati still needs it.

- Same card chrome as loading.
- Generic copy only (`provider_error`, `rate_limited`, `text_required`) — never a stack trace, never the API key.
- Primary **ပြန်ကြိုးစားရန်**; secondary edit text.

### Completed analysis

Informed by Revolut status cards + WhatsApp sent-file card.

- Status strip + evidence + actions as above.
- Optional short toast if a report was just sent (Digg: “team will review” → Thati: human review only).

### Selected file / voice preview (when those APIs exist)

Informed by ChatGPT thumbnail+X, WhatsApp large preview, SchoolAI “1 file selected”.

- Screenshot: thumbnail in dock; tap opens a preview sheet with **X**.
- Voice: waveform or duration chip, **X**, then Analyze.
- Analyze stays disabled until preview is accepted (WhatsApp: see the file first).

### Report + blacklist

- Submit report: modal with optional note; Submit disabled until the user confirms they understand it stays **pending** (Digg disabled Submit until a reason).
- Blacklist match: lime, masked value, never a raw stored identifier.

---

## Pattern-to-spec map (disclosure)

| Thati element | Informed by |
| --- | --- |
| Risk header, safe-action cards, bottom Confirm grammar, reassurance line | [Revolut Secure your account](https://mobbin.com/screens/f32234af-d71b-4c32-ad84-8aa4edc49b3f) |
| Bottom compose dock, attach vs send separation, file chip + X | [ChatGPT iOS](https://mobbin.com/screens/594e1411-90e5-481f-8e5c-804534dcfba6) |
| Preview-before-analyze, trust banner, file metadata card | [WhatsApp sending a document](https://mobbin.com/flows/fa7037b7-2e7b-468f-9e49-f09e2867b736) |
| Admin tabs, review modal, approve/reject contrast, empty + toast | [Circle Approving a content](https://mobbin.com/flows/a50bc33f-7773-4efc-85a3-25fc2bd13e69) |
| In-progress modal/card, disabled finish, cancel | [Confluence importing a document](https://mobbin.com/screens/4ca4995a-8a4f-4c55-b89c-346f0c0b269e) |

Thati must not reuse Revolut, ChatGPT, WhatsApp, Circle, or Confluence logos, mascots, purple/green brand fills, or layout pixel-for-pixel. Palette, Myanmar type, evidence quotes, and human-only blacklist lime are the product-specific layer.

---

## Out of scope until this spec is approved

- HTML / CSS / JavaScript
- Screenshot OCR and voice transcription UI wiring (controls may be present but inert)
- Extra marketing pages
