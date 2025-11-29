# CP Writing Style Guide v4.1.0

**Version**: 4.1.0  
**Last Updated**: 2025-11-22  
**Source**: [8090-inc/8090-claude-skills](https://github.com/8090-inc/8090-claude-skills/tree/main/.claude/skills/cp-writing-style)

---

## Brand Guidelines

**Accent Color**: #0055D4  
**Neutral Colors**: Tailwind CSS Slate Colors  
**Font**: Figtree (regular weight to semi-bold weight)

### Visual Standards
- **WCAG AA Compliance**: Ensure all text contrast meets WCAG AA standards
- **Color Usage**: Use pure white and slate gray (50–950) but not pure black
- **Visual Elements**: Round corners to 8px when applicable
- **Brand Color**: Use #0055D4 as an accent but not for main colors
- **Content Hierarchy**: Ensure proper content hierarchy and harmony of visual elements

---

## Overview

This guide provides comprehensive guidance on writing in Chamath Palihapitiya's distinctive communication style. The style is optimized for maximum clarity, honesty, and action-orientation across all business communications.

---

## The 10 Universal Principles

These rules apply to **ALL** communications, regardless of format or audience.

### 🚨 CRITICAL: NEVER FABRICATE DATA 🚨
When applying Principle 2 (Data Over Adjectives), you can ONLY use data from the original source material. If data is missing, use bracketed placeholders `[Need: description]` or state "data not available." Fabricated numbers are worse than vague language.

### Principle 1: Radical Clarity [MUST]
**Say it simpler**

- Use plain language. Define technical terms/acronyms on first use
- State conclusions firmly. No hedging or qualifiers
- Target 10th-grade reading level (use as guide, not strict rule)
- Replace vague pronouns (this, that, it) with specific nouns when unclear
- Be decisive: make the call, don't waffle

**Example**:
```
❌ "We are experiencing challenges in our go-to-market execution strategy"
✅ "We're bad at sales"
```

**When to deviate**: Never. Clarity is non-negotiable.

---

### Principle 2: Data Over Adjectives [MUST]
**Show numbers from source, not descriptions**

**NEVER INVENT DATA**

- Replace "significant," "major," "substantial" with actual metrics FROM THE SOURCE
- Use percentages, dollar amounts, time periods FROM THE SOURCE
- Provide context for numbers (comparisons, benchmarks)
- Round to meaningful precision (not false precision)
- **When data is missing**: Use `[Need: description]` or state "data not available"
- **When estimating**: Label explicitly AND cite methodology
- **When using imprecise calculations**: Qualify with uncertainty statement
  - Use "~" notation for approximations
  - Acknowledge imprecision: "~40% (this math isn't highly precise but it frames our problem)"

**Example**:
```
❌ "We saw significant growth this quarter"
✅ "Revenue grew 47% QoQ from $2.1M to $3.1M" [IF YOU HAVE THIS DATA]
✅ "Revenue grew [Need: Q3 and Q4 revenue figures]" [IF YOU DON'T]
```

**When to deviate**: Never. If you don't have data, say you don't have data.

---

### Principle 3: Honesty First [MUST]
**Acknowledge failures upfront**

- Start difficult communications with truth, no matter how uncomfortable
- Don't bury bad news in positive framing
- Use "What happened?" to explain failures directly
- Balance honesty with respect: Acknowledge → State truth → Provide solution

**Example**:
```
❌ "Despite some challenges, we had a great quarter overall"
✅ "Poor coordination caused a 2-day automation drop from 40% to 5% on October 14th (since resolved). That said, we delivered 15.7 FTE equivalents in time savings"
```

**When to deviate**: Never on substance. You can modulate tone for audience, but never hide truth.

---

### Principle 4: First-Principles Thinking [SHOULD]
**Explain from fundamentals**

- Ask "why" repeatedly until you reach bedrock assumptions
- Challenge conventional wisdom explicitly
- Explain reasoning from basics, not industry norms
- Use pattern: "Conventionally, [X]... However, [Y]"

**When to deviate**: Skip for routine tactical communications where audience already understands context.

---

### Principle 5: Economy of Language [MUST]
**Cut every wasted word**

- Eliminate filler words ("very," "really," "quite," "actually")
- Use strong verbs instead of weak verb + adverb
- Delete redundant phrases
- Prefer active voice over passive
- Short sentences. Declarative statements.

**The Three-Pass Cutting Method**:
1. **First pass**: Write to think. Get ideas out.
2. **Second pass**: Cut everything that doesn't drive the decision.
3. **Third pass**: Read each sentence. Ask "Does this need to exist?" Cut 30% more.

**Target**: 50-80% reduction from first draft.

**Example**:
```
❌ "We are very excited to really announce that we have quite successfully completed..."
✅ "We completed..."
```

**When to deviate**: Never. Always cut ruthlessly.

---

### Principle 6: Active Voice & Personal Accountability [MUST]
**People do things**

- Use "I," "we," "you" not passive constructions
- Assign clear ownership
- Make subjects of sentences do the action
- Avoid "it was done" → "we did it"

**Example**:
```
❌ "Mistakes were made and lessons were learned"
✅ "I made mistakes. I learned from them"
```

**When to deviate**: Rarely. Only when the actor is genuinely unknown or irrelevant.

---

### Principle 7: Context Provision [MUST]
**Always explain "why"**

- Frame decisions with strategic reasoning
- Provide enough background for audience to understand implications
- Don't assume knowledge—teach the fundamentals
- Connect tactical actions to strategic objectives
- Context enables delegation: explain "why" so others can execute "how"

**Example**:
```
❌ "We need to implement Solution X"
✅ "Because customers are churning at 5% monthly (vs. 2% industry average), we need to implement Solution X"
```

**When to deviate**: Skip minimal context in very quick tactical emails when recipient already has full context.

---

### Principle 8: Proper Attribution [SHOULD]
**Credit sources**

- Name the person/source when sharing ideas
- Use footnotes or inline citations for data
- Don't claim others' insights as your own
- Strengthen arguments by showing intellectual foundation

**Example**:
```
❌ "Distribution is more important than product"
✅ "As Peter Thiel observes: '[quote]' Put more simply, Distribution > Product"
```

**When to deviate**: Common knowledge doesn't require attribution. When in doubt, attribute.

---

### Principle 9: Forward-Looking & Action-Oriented [MUST]
**Point to next, drive outcomes**

- End with implications, not just conclusions
- Provide roadmaps, timelines, next steps
- Make clear what success looks like
- Include clear directives with specific next steps
- Assign ownership and accountability

**When to deviate**: Only for pure informational communications (FYI emails).

---

### Principle 10: Format Follows Function [SHOULD]
**Structure serves message**

- Default to narrative prose for explanations, arguments, stories
- Use bullets only for parallel lists, specifications, action items
- Tables for comparative data
- Headers to signal topic shifts
- Long-form for strategic/educational content

**When to deviate**: When specific format requirements dictate different structure.

---

## Banned & Golden Elements

### Banned Words/Phrases

**Vague Adjectives**:
- ❌ Significant, substantial, considerable
- ❌ Very, really, quite, actually

**Corporate Jargon**:
- ❌ Leverage, synergy, paradigm
- ❌ Going forward, moving forward
- ❌ Drive toward, laser-focused on, de-risk
- ❌ Socialize, alignment, stakeholder engagement
- ❌ Stand up, operationalize, at scale
- ❌ Capability enhancements, governance frameworks
- ❌ Cross-pollination, shift right, ladder up to
- ❌ Touch base, circle back

**Euphemisms**:
- ❌ Challenges (say "problems" or be specific)
- ❌ Opportunities for improvement (say "failures")
- ❌ Rightsizing (say "layoffs")

### Golden Phrases

**Transitions**:
- ✅ "What happened?"
- ✅ "This resulted in..."
- ✅ "What does this mean for..."
- ✅ "Put more simply, X > Y"
- ✅ "The reason lies with..."

**Causal Connections**:
- ✅ "Because [reason], [action]"
- ✅ "Since [context], [implication]"

**Analysis**:
- ✅ "Conventionally, [X]... However, [Y]"
- ✅ "Throughout [time period], [observation]"

**Directives**:
- ✅ "Run it by [name] before you send it pls"
- ✅ "You need to..."

---

## Meta-Rules: Balancing Principles

### Hierarchy of Values

When principles conflict, use this priority order:

1. **Honesty First** (Principle 3) → Never compromise truth
2. **Clarity** (Principle 1) → Never sacrifice understanding
3. **Data** (Principle 2) → Ground arguments in facts
4. **Brevity** (Principle 5) → But not at expense of 1-3

### Quality Hierarchy

Optimize in this order:

1. **Clarity**: Can the reader understand this?
2. **Brevity**: Is every word necessary?
3. **Polish**: Is formatting consistent?

**Never sacrifice clarity for brevity.** If you need 100 words to explain clearly, use 100 words. But most drafts use 200 words where 100 would be clearer.

---

## MANDATORY: 3-Pass Writing Method

**You have NOT applied CP style unless you complete all 3 passes:**

### PASS 1: Write to Think
- Get ideas out
- Use placeholders for missing data
- Don't self-edit yet

### PASS 2: Apply All 10 Principles
- [ ] **Principle 1 (Clarity)**: Plain language? Vague pronouns removed?
- [ ] **Principle 2 (Data)**: Used only source data? Placeholders for missing data? NO FABRICATION? Imprecise numbers qualified?
- [ ] **Principle 3 (Honesty)**: Failures acknowledged upfront?
- [ ] **Principle 4 (First-Principles)**: Explained "why" from fundamentals? (if strategic doc)
- [ ] **Principle 5 (Economy)**: Cut every wasted word? Removed corporate jargon?
- [ ] **Principle 6 (Active Voice)**: "We do X" not "X is done"?
- [ ] **Principle 7 (Context)**: Explained "why" this matters?
- [ ] **Principle 8 (Attribution)**: Cited sources? (if applicable)
- [ ] **Principle 9 (Forward)**: Clear next steps? Roadmap? Asks?
- [ ] **Principle 10 (Format)**: Right structure for audience?

### PASS 3: Ruthless Cutting (Target: Cut 30% more)
- Read each sentence
- Ask: "Does this sentence need to exist?"
- Ask: "Does this word drive the decision?"
- If no → delete it
- Check banned words list one more time

### FINAL CHECK
- [ ] Word count reduced 50-80% from Pass 1?
- [ ] All MUST principles applied?
- [ ] All [Need: X] placeholders explicit (no fabricated data)?
- [ ] Maximum signal-to-noise ratio achieved?

**WARNING**: If you skip Pass 2 or Pass 3, you have NOT applied CP style. You've only started.

---

## Format Decision Tree

### What format should I use?

```
Strategic reflection + annual performance
  → ANNUAL LETTER (2-5K words)

Progress reporting + stakeholder management + asks
  → CUSTOMER BRIEF (500-2K words)

Policy recommendations + implementation plans
  → POLICY IDEAS BRIEF (3-5K words)

Educational deep-dive on complex topic
  → LEARN WITH ME PRESENTATION (40-80 slides)

Quick tactical communication (single purpose)
  ├─ Sharing business principle → EMAIL: Philosophy
  ├─ Personnel announcement → EMAIL: Personnel
  └─ Directive or feedback → EMAIL: Tactical

Teaching complex topic (prose format)
  → LONG-FORM ESSAY (3-7K words)
```

---

## Context-Dependent Tone Calibration

| Audience | Formality | Technical Detail | Diplomatic Buffer |
|----------|-----------|------------------|-------------------|
| Investors/Public | Professional conversational | Moderate (explain acronyms) | Some (it's public) |
| Business stakeholders | Business professional | High (assume context) | Minimal (results matter) |
| Internal team | Casual conversational | Very high (use jargon) | Zero (be direct) |
| Founders (advice) | Professional warm | Moderate (principles not tactics) | Some (you're teaching) |

---

## When CP Style is NOT Appropriate

**Don't use this style for**:
- Marketing copy (requires different persuasion tactics)
- Legal documents (requires specific legal language)
- Customer service communications (requires different empathy tone)
- Crisis communications (may need more diplomatic framing)

---

## The Goal

**Maximum signal-to-noise ratio.** Every word should earn its place.

This style prioritizes truth and clarity over politeness and comfort. Write to inform and drive action, not to impress or obscure.

---

## Additional Resources

For complete format-specific playbooks, templates, and examples, see:
- [Full CP Writing Style Guide on GitHub](https://github.com/8090-inc/8090-claude-skills/tree/main/.claude/skills/cp-writing-style)
