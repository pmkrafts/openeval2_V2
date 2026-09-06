# OpenEval2 — What it is, in plain language

Written for non-technical readers: recruiters, managers, friends. No jargon needed.
If a term is unavoidable, it is explained in §9.

Repo: github.com/pmkrafts/openeval2

---

## 1. What is this project?

A website that reads **customer complaints** (specifically: hotel reviews from Booking.com),
shows them in a table, and uses **two AI assistants** to sort each complaint into a theme —
Location, Staff, Room, Cleanliness, Food, Price, or Other.

When the two AIs disagree, the complaint is short, or something looks odd, the row is put
into a **"needs review" pile** for a human to look at. A person can then save the *correct*
answer, and the tool can compare two AI prompts to see which one tags better.

It is a small, clean, working example of a loop used at work every day for survey answers.

---

## 2. The problem it solves

Real problem: when thousands of people write complaints, **nobody can read them all**.

- One hotel chain can get tens of thousands of comments a year.
- A survey with open-ended questions ("what could be better?") gets the same flood.
- Companies need to know *what* people complain about — is it the room? the staff? the price? — without a team of people reading every single line.

This project shows the standard answer: **let AI do the first pass, and let a human
check only the rows the AI is unsure about.** That is the whole trick, and it is the
same loop used for survey open-ends at work — except the text here is public hotel
reviews, so no private data is involved.

---

## 3. The data

| Fact | Value |
|---|---|
| Where from | Booking.com reviews, published on Kaggle (public dataset, CC0 license) |
| How big | ~515,000 reviews |
| What we keep | a random sample of **50,000** |
| What we label with AI | only **200** of those |
| License | free to use; the CSV file itself is still kept out of git |

Why not label all 515,000? Labeling costs money (paid AI models) and a human can only
check so many rows. Sample first, prove the loop, stop.

Each kept review is a complaint — rows that say "No Negative" are thrown away at the
start, so the AI never even sees them.

---

## 4. How it works — the everyday story

1. **Download** the hotel review file into a private folder (not uploaded to git).
2. **Shrink it**: take 50,000 reviews at random, keep only the ones with a real complaint.
3. **Tag it**: two AI assistants read each complaint's negative text and each pick a theme
   (Location, Staff, Room, Cleanliness, Food, Price, Other).
4. **Sort it**:
   - Both AIs picked the same theme, and the complaint is long enough → **ok**.
   - The AIs disagree, or the text is tiny ("bad bed"), or an AI failed → **needs review**.
   - (v2, extra check) A 1–4-out-of-10 review tagged "Other" by both AIs with a long
     complaint → also **needs review**, because "Other" on a genuinely bad review is suspicious.
5. **Review it**: a human opens the "needs review" pile, reads the complaint, and can save
   the correct theme as a **gold** answer. Gold never overwrites the AI tags — it sits
   beside them as the human's truth.
6. **Compare** (v2): run two versions of the AI prompt on the same complaints and compare
   cost, speed, and how often they agree — so you can pick the better prompt with data.

---

## 5. A concrete example

A guest writes: *"Room was dirty, hair on the pillows, bathroom smelled."*

- AI #1 tags it **Room**. AI #2 tags it **Cleanliness**.
- They disagree → the row lands in **needs review**.
- A human opens the row: reads it, thinks "the real complaint is cleanliness," and saves
  gold = **Cleanliness**.
- On the next screen the row shows both AI tags, the human's gold answer, and stays in
  the queue until the person closes it out.

Now imagine 200 rows like this with one tagger pair, and 50,000 complaints stored behind
a fast table. That is the scale the tool is built for.

---

## 6. Who uses it, in the real world

| Person | What they do with it |
|---|---|
| The builder | Loads data, runs the labelers, keeps API + website alive |
| An analyst | Hunts for bad tags, saves gold answers, exports a spreadsheet |
| A hiring manager | Opens the URL, sees real complaints and the review pile, understands in 10 minutes |
| A recruiter | Hears the story: "515k public reviews → 50k stored → 200 AI-labeled → humans check the disagreements" |

---

## 7. What it solves in the real world (beyond hotels)

Same loop, three example jobs:

- **Survey open-ends**: "What should we improve?" → AI tags the theme, humans review the
  disagreements instead of reading 10,000 answers.
- **Support tickets**: incoming complaints sorted by topic so a small team sees the
  biggest problems first.
- **Review moderation**: product or venue reviews flagged when AI can't confidently agree
  on the theme.

The general formula the project demonstrates: **AI does the bulk pass, a "disagreement
queue" catches the unsure rows, a human sets the truth, and metrics tell you which prompt
to trust.**

The honest framing for the work version: *"At work this is survey open-ends behind
private APIs. This demo uses public hotel text."*

---

## 8. Honest limits (what it does NOT do)

- It does **not** read positive reviews for tagging — only the negative complaint.
- It does **not** load all 515,000 reviews into the website; 50,000 is the store, and the
  site only renders one page at a time.
- It labels **≤200** rows with a paid model — enough to prove the loop, not to ship a full product.
- The "needs review" pile exists because **the AI is expected to be wrong sometimes**.
  That pile is a feature, not a bug.
- The public demo runs on **fake, hotel-shaped data** — no real Kaggle file on a public
  server, no API key needed to look at it.
- No maps, no location pins, no Spark-scale infrastructure. Deliberately small.

---

## 9. Little glossary

| Word | Meaning |
|---|---|
| Sample | A random slice of the data, picked so it represents the whole |
| Label / theme | The category an AI assigns to a complaint (Staff, Room, …) |
| Dual-LLM | Two AI assistants tagging the same text independently |
| needs_review | The queue: rows a human should check |
| Gold label | The human's correct answer, saved on a row |
| A/B test | Running two prompt versions on the same rows to compare them |
| Mock mode | A fake labeler used in tests so nothing costs money or needs a key |
| API | The behind-the-scenes service that hands data to the website |
| Virtualized table | A table that only draws what is on screen, so 50,000 rows stay smooth |

---

## 10. The 10-minute demo script

1. Open the site → stats bar: 50k reviews stored, 200 labeled.
2. Filter the "needs review" pile.
3. Open one disagreement row and read the complaint sentence aloud.
4. Save a gold answer (v2).
5. Export the filtered rows to Excel — it opens cleanly.
6. Say: *"Same loop as survey open-ends at work — this text is public."*

If any step needs a client name, skip that step.
