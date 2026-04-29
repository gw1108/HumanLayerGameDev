---
name: refine_research_question
description: Refine and sharpen a research question. The skill works interactively: it decomposes the question into composable research areas, asks clarifying and edge-case questions, iterates with the user until the question is sharp, and saves the refined question to thoughts/shared/questions/.
model: opus
---
 
# Refine Research Question
 
You are tasked with sharpening a fuzzy research question about a codebase. The output is a refined question(s) saved to `thoughts/shared/questions/`, which `/research_codebase` later reads as its starting point.
 
## Your job is to refine questions, not research
 
You work with the user to take a vague question and turn it into a sharp one — by working back and forth with the user. The output is a saved question file that `/research_codebase` consumes.
 
If the user references a specific file in their question — a ticket, a design doc, a JSON spec, a PR description — read that file fully. It's context for the question itself.
 
## Initial setup
 
When invoked, if the user hasn't already given you a research question, respond with:
 
```
I'll help you refine a research question before we dig into the codebase. What do you want to research?
```
 
Then wait for the user's question.
 
## Steps
 
### 1. Read any directly mentioned files
 
If the user references specific files, tickets, or docs in their question, read them in full before doing anything else. Read entire files (no offsets or limits).
 
### 2. Decompose and think hard about underlying intent
 
Take real time here. The user gave you their surface-level framing, and the research areas they actually need investigated are often broader, narrower, or sideways from what they literally asked.
 
Think about:
- What composable research areas does this question break into? Components, layers, concepts, data flows, lifecycles, integration points.
- What is the user *probably* trying to accomplish that prompted this question? An upcoming change? A bug hunt? Their motivation reshapes what useful research looks like.
- What are the obvious adjacent areas they didn't mention but probably want covered?
- What patterns or architectural concepts is this question implicitly about, even if they used different words?
Aim for a structured decomposition you can show the user as a starting point for the conversation. They'll redirect you if you've misread the intent.
 
### 3. Generate clarifying and edge-case questions
 
Two kinds of questions matter:
 
**Clarifying questions** sharpen the focus. Which subsystem. What time horizon (current state vs. recent changes vs. historical evolution). How deep (interface-level vs. implementation details). What level of abstraction. Are tests, configs, or docs in focus. What does the user already know vs. need explained.
 
**Edge-case questions** probe corners that are easy to miss. Error paths. Unusual inputs. Deprecated code. Related-but-distinct components that might get confused. Things that look the same but aren't. The "weird" version of the thing being researched.
 
Keep the question count manageable. 1–7 questions per round is usually right, more only if there's genuinely a lot to disambiguate. Group them by research area so the user can see the structure.
 
### 4. Present decomposition and questions in one turn
 
In a single response, give the user:
 
1. **Your interpretation** of what they're asking — one or two sentences. This lets them correct you fast if you're off.
2. **The research areas** you've decomposed it into — a short list with one-line descriptions.
3. **Your clarifying and edge-case questions**, grouped by research area.
Combining all three in one turn lets the user redirect your framing and answer questions in a single response.
 
### 5. Iterate until the question is sharp
 
The user will respond. They might:
- Answer some questions and skip others — skipped is fine, note it as "not specified"
- Push back on your decomposition or framing
- Add context you didn't have
- Ask their own questions back at you
Update your understanding, then either:
- Ask follow-up questions if new ambiguities emerged or important areas remain open
- Propose the final refined question if things feel solid
A question is "sharp enough" when the research areas are concrete, both you and the user know what's in and out, and a researcher reading just the refined question would know what to investigate without guessing.
 
Aim for two or three rounds at most. If the user seems impatient or says "just go," wrap up with what you have and move to step 6 — an imperfect refinement is still useful.
 
If the user's original question was already sharp, say so, skip extra rounds, and go straight to saving.
 
### 6. Save the refined question
 
Save the refined question by running:
 
```
python create_thought.py questions <file_name_description> <content> [ticket]
```
 
Where `<file_name_description>` is a short summary of the topic, `<content>` is the content of the output file (see format below), and `[ticket]` is the optional ticket if mentioned.
 
Then tell the user where it was saved.
 
## Output file format
 
Use this structure for `<content>`. Omit any sections that don't apply.
 
```markdown
---
researcher: [user's name if known, otherwise omit]
original_question: "[user's original phrasing, verbatim]"
ticket: [ticket id, or omit]
---
 
# Research Question: [Topic]
 
## Refined Question
[The sharpened version of what to research, written in plain language. Keep the user's voice where you can.]
 
## Research Areas
1. **[Area name]** — [one or two sentences on what to investigate here and why it's part of this research]
2. **[Area name]** — ...
 
## Clarifications Gathered
- **Q:** [clarifying question]
  **A:** [user's answer, or "not specified"]
- **Q:** ...
  **A:** ...
 
## Edge Cases to Address
- [Edge case the research should explicitly check]
- ...
 
## Files Provided by User
- `path/to/file.md` — [why it's relevant]
```
 
## Notes
 
- Keep the conversation efficient. If a single round of clarification is enough, one round is enough.