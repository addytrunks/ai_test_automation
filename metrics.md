# Metrics to Track During the Internship

The goal is to collect numbers you can *actually defend in an interview* — not numbers you pre-invented before writing a single line of code. Every metric below is something you can log as you build and test. If you can't point to a log file, a timestamp, or a test run that produced the number, don't put it on your resume.

---

## 1. Agentic Loop Behavior (Your Core Differentiator)

This is what separates your project from "I built a script that calls an LLM." Track the loop itself.

- **Iteration count per run:** How many reasoning cycles did the agent need before hitting a stopping condition? Log this per spec. If it's always 1, your loop isn't doing anything meaningful.
- **New tests generated per iteration:** Iteration 1 might produce 20 tests. Does Iteration 2 produce 8 more genuinely new ones? Does Iteration 3 produce 2? This curve tells the real story. A flat curve means the coverage gap analysis isn't working.
- **Deduplication rate:** Out of all tests generated across iterations, what % were duplicates caught by the hash? This number *proves* the deduplication logic is working and that the agent isn't just regenerating the same cases.

**Resume framing (only after you have real data):**
> "Built a LangGraph agentic loop that averaged X iterations per API spec, surfacing Y additional edge cases beyond the initial pass."

---

## 2. Test Quality Score (The Hard One — and the Most Valuable)

This is the metric almost no intern will have, and it's the one that actually demonstrates you understand evaluation, not just generation.

You need a scoring rubric. For each generated test case, score it on:

- **Relevance** — Does it actually test the endpoint it claims to test?
- **Correctness** — Is the HTTP method, path, and payload structurally valid?
- **Security intent** — For a security-focused test, does the payload actually probe a real vulnerability class (e.g., BOLA, IDOR, injection)?
- **Non-redundancy** — Is this genuinely different from another test in the set?

Score each dimension 1–3. Do this manually on a sample (say, 30–50 tests). Then compare your scores to what the agent auto-tagged. The gap between agent confidence and your manual review *is* a real finding.

**Resume framing:**
> "Developed a multi-dimension test quality rubric; manual evaluation of N generated tests showed X% met all four quality criteria, with security intent being the most frequent failure mode."

---

## 3. False Positive Rate

If the agent generates tests that claim to detect a vulnerability but the assertion logic is wrong (e.g., it expects a 403 but the endpoint always returns 200 for unrelated reasons), that's a false positive. Track it.

- Count how many tests *pass* on VAmPI when they should *fail* (meaning the vulnerability exists but your test didn't catch it).
- Count how many tests *fail* on a healthy endpoint for the wrong reason (e.g., bad request format, not actual vulnerability).

This is a metric that shows you understand precision vs. recall in a testing context — not just "how many tests did it generate."

---

## 4. Generation Time (Track It, but Don't Overstate It)

Time the actual generation runs with a stopwatch or `time` in Python. Per endpoint:

- Time from spec upload to first test batch ready
- Time for each subsequent iteration

**Important caveat:** Don't compare this to "2 hours of manual work" unless you've actually timed a human writing tests for the same endpoint. A made-up baseline is an interview liability. If you haven't timed it manually, the honest framing is:

> "Generated X test cases per endpoint in under Y seconds."

That's defensible. The comparison claim is not.

---

## 5. VAmPI Vulnerability Detection (Honest Version)

VAmPI's vulnerabilities are public and documented. Detecting them all is not impressive on its own — your prompts are engineered to find exactly those classes. What *is* worth tracking:

- **Which vulnerability classes did you encode via few-shot prompting?** List them explicitly.
- **Did the agent find any vulnerability pattern you didn't explicitly encode?** Even one instance of this is a strong story.
- **How many iterations did it take to surface each finding?** A vulnerability found in Iteration 3 that wasn't in Iteration 1 is a concrete proof point that the loop is working.

**Resume framing:**
> "Agent detected X out of Y seeded vulnerability classes in VAmPI across Z agentic iterations; 2 findings required multiple reasoning cycles to surface."

---

## 6. What NOT to Put on Your Resume

These will get you caught in an interview:

- "0% to 100% coverage" — coverage of what, exactly? Endpoint count is not coverage.
- "40% token reduction" — compared to what baseline? You'd need to have built the other version and measured it.
- "100 concurrent tests in under 2 seconds" — only include this if you actually ran a load test and measured it.
- "10 interconnected database schemas" — this is table counting, not a metric.

---

## 7. Token Cost per Run (Cost Efficiency, Not Just Cost)

Engineering managers care about token spend, but not in isolation. A raw dollar figure means nothing without context. The metric that actually lands is **cost-per-finding** and **cost-per-iteration yield** — showing that you understand where budget is being spent and whether it's justified.

LiteLLM exposes `prompt_tokens` and `completion_tokens` on every response. Log both, per node, per iteration.

**What to track:**

- **Total token spend per full agentic run** — e.g., "3-iteration loop on VAmPI: 45k tokens ≈ $0.12." Baseline number, necessary but not sufficient.
- **Token spend broken down by iteration** — How much did Iteration 1 cost vs. Iteration 2 vs. Iteration 3? If Iteration 3 costs as much as Iteration 1 but produces 2 new tests instead of 20, that's a concrete argument for tightening your stopping condition.
- **Token spend broken down by node** — Which node is the most expensive? The coverage gap analyzer prompt is likely heavier than the test generation prompt. Knowing this tells you where optimization effort is worth spending.
- **Cost-per-finding** — Total token cost divided by number of *unique, non-duplicate* tests generated. This is the number that makes cost-awareness concrete.

**Resume framing (after you have real data):**
> "Instrumented per-node token spend via LiteLLM; identified that coverage gap analysis consumed ~60% of total token budget, leading to prompt optimization that reduced cost-per-test from $X to $Y."

Or if you find the loop is efficient:
> "Full 3-iteration agentic run on a 15-endpoint spec cost under $0.15, with 80% of token spend concentrated in Iteration 1; Iterations 2–3 yielded incremental findings at ~$0.01 per unique test."

**What not to do:** Don't just log total cost and call it cost-awareness. If you can't explain what that cost bought, the number works against you — it invites the question "could you have gotten the same output cheaper with one iteration?"

Add to your `metrics_log.txt`:
```
Token spend (total):
Token spend (by iteration):
Token spend (by node, if tracked):
Cost-per-unique-test:
```

---

## What to Do Right Now

Keep a `metrics_log.txt` as you build. Every time you run the agent, log:

```
Date: 
Spec: 
Iterations run: 
Tests generated (per iteration): 
Duplicates caught: 
VAmPI findings: 
Generation time (seconds): 
Notes:
```

By Week 6 you'll have real data. By Week 8, your resume bullets will be defensible in any technical interview.