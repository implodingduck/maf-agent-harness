---
name: researcher
description: Research a topic on the web and distill it into an insightful, reusable research brief. Use this whenever the user asks to research, investigate, gather background, do due diligence, compare options, or find current/factual information on a topic before producing a deliverable (report, deck, decision, plan). Produces a structured Markdown brief saved to disk so later steps can build on the findings.
---

# Researcher skill

Turn an open-ended question into a **research brief**: a structured, evidence-backed
Markdown document that captures not just facts but *insight* — what the facts mean,
where sources agree or conflict, and what to do next. The brief is written to a file
so downstream work (a slide deck, a report, a decision, another agent turn) can build
on it after the raw search results have scrolled out of context.

Use the built-in **web search tool** to gather information and the **shell tool** to
save the brief. There is no bundled script — this skill is a methodology plus an
output contract.

## When to use this skill

- The user asks to *research / investigate / look into / dig into* a topic.
- You need current or fast-moving facts (news, releases, prices, versions, events)
  that you should verify rather than recall from memory.
- You need background or context to inform a later deliverable (e.g. "research X,
  then build a deck / write a summary / recommend an option").
- A claim needs to be checked against multiple sources.

Prefer this skill over answering from memory whenever accuracy, currency, or
citations matter.

## Method

Work in plan → execute style; if the topic is non-trivial, capture the steps below
as todos first, then work through them.

1. **Frame the question.** Restate the topic in one sentence. List the specific
   sub-questions the brief must answer and any constraints (time range, geography,
   audience, decision the research feeds into). If the ask is ambiguous, ask one
   clarifying question before spending search budget.
2. **Plan queries.** Draft several targeted search queries covering different angles
   and phrasings. Use your own knowledge to form hypotheses, but treat them as
   things to verify, not conclusions.
3. **Search broadly, then narrow.** Run the web search tool on each angle. Skim
   results, then drill into the most authoritative or most recent sources. If a
   search returns weak/irrelevant results, reformulate the query before moving on.
4. **Cross-reference.** Corroborate every key claim with at least two independent
   sources when possible. Prefer primary sources (official docs, filings, the
   original announcement) and recent, reputable secondary sources.
5. **Capture as you go.** For each finding record the claim, the evidence, and the
   source **URL + publication date**. You will need these for citations; do not
   reconstruct them from memory later.
6. **Synthesize insight.** Go beyond a list of facts:
   - What is the *so what* — the implication for the user's goal?
   - Where do sources **agree**, and where do they **conflict**? When they
     conflict, say which you trust more and why.
   - What is surprising, non-obvious, or a second-order effect?
   - What is still **unknown or uncertain**, and how confident are you?
7. **Save the brief.** Write the brief to a Markdown file under the git-ignored
   `output/` directory (see below) using the shell tool so it survives context
   compaction and later steps can read it.
8. **Report back.** Return a short summary (headline + 3–7 key insights) inline and
   tell the user the path to the full brief.

## Output contract

Save the brief to `output/research/<slug>.md` under the current working
directory, where `<slug>` is a short kebab-case version of the topic (e.g.
`output/research/azure-ai-foundry-pricing.md`). The `output/` directory is
git-ignored so generated briefs never clutter commits; create it (and the
`research/` subfolder) if needed. Follow this structure — it is the reference
template in
[`references/research_brief_template.md`](references/research_brief_template.md):

```markdown
# Research Brief: <Topic>

- **Date:** <YYYY-MM-DD>
- **Question:** <the one-sentence question this brief answers>
- **Scope / constraints:** <time range, geography, audience, decision it feeds>
- **Confidence:** <High | Medium | Low> — <one line on why>

## Key insights
1. **<Insight, stated as a takeaway, not a topic>** — <what it means / so what>.
   _Evidence:_ <fact/number>. _Source:_ [<name>](<url>), <date>.
2. ...

## Detailed findings
### <Sub-question or theme>
<Prose synthesis with inline citations: "According to [Source](url) (date), ...">

## Points of agreement & disagreement
- **Agreement:** <what most sources converge on>.
- **Disagreement:** <where they differ> — <which source is more reliable and why>.

## Implications / recommendations
- <Actionable implication for the user's goal / the next step down the path>.

## Open questions & unknowns
- <What could not be confirmed, or needs more research>.

## Sources
- [<name>](<url>) — <what it was used for>, <date>.
```

Every non-obvious claim in the brief must carry an inline citation. End with a
complete `Sources` list.

## Handing off to later steps

The saved brief is the durable artifact "used later down the path". When a
subsequent step needs it:

- Read it back with the shell tool (e.g. `cat output/research/<slug>.md`) instead
  of relying on memory.
- The **Key insights** and **Detailed findings** sections map cleanly onto slides
  for the `pptx` skill (title = insight, content = evidence + implication), or onto
  sections of a written report.
- If the user asks to update the research later, append to or revise the same file
  and bump the `Date`.

## Quality bar

- **Verify, don't assert.** No key claim without a source. If you cannot find a
  source, say so explicitly rather than guessing.
- **Recency matters.** Note publication dates; flag when the best available source
  is stale for a fast-moving topic.
- **Insight over volume.** A tight brief with sharp, sourced takeaways beats an
  exhaustive info dump. Summarize; don't paste raw search results.
- **Stay in scope.** Answer the framed question; park interesting tangents under
  Open questions.
