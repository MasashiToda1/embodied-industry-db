# Fey-R

> *"What I cannot create, I do not understand."* — Richard Feynman

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills) that guides you through academic papers using the Feynman technique — you try to derive the author's solution yourself before seeing it.

## What It Does

Fey-R walks you through a paper section by section in an interactive Socratic dialogue. The workflow combines Keshav's [three-pass reading method](https://web.stanford.edu/class/ee384m/Handouts/HowtoReadPaper.pdf) with derivation-first learning:

| Phase | What happens |
|-------|-------------|
| **0. First Pass** | Quick scan, 5 Cs orientation card (Category, Context, Contributions, Correctness, Clarity), set your reading goal. Stop here if the overview is enough. |
| **1. Background** | Introduction + key references (optional). One focused comprehension check. |
| **2. Pain Points** | Related work landscape. You identify what's missing before being told. |
| **3. Your Derivation** | Given the pain points, you design your own solution — architecture, loss function, key mechanisms. Then predict how you'd test it. |
| **4. Author's Approach** | Reveal and compare. Where you aligned, where you diverged, and why. Critical assessment of the paper's own assumptions. |
| **5. Experiments** | Figure analysis, results walkthrough, your predictions vs. reality, future work brainstorm. |
| **6. Feedback** | Optional post-session feedback to improve the skill. |

Two reading modes: **Careful** (full depth, multiple checks, 3+ design decisions) and **Skim** (key ideas, fewer checks, faster pace). Switch anytime.

## Output

Each session produces a structured `[paper-name]_notes.md` with:
- Paper overview and 5 Cs assessment
- Background, pain points, and method comparison (yours vs. author's)
- Critical assessment, figure analysis, prediction vs. reality
- Dialogue Record tracking your comprehension trajectory
- Tagged review questions (Why / Contrast / Transfer / Hypothetical / Connection)

Partial sessions save progress with a Resumption Guide — pick up where you left off.

## Installation

Copy the skill into your Claude Code skills directory:

```bash
# Clone the repo
git clone https://github.com/xvirobotics/fey-r.git

# Copy to Claude Code skills directory
cp -r fey-r ~/.claude/skills/fey-r
```

Or add it as a project skill by placing it in your project's `.claude/skills/` directory.

## Usage

In Claude Code, provide a paper and the skill activates automatically:

```
Read this paper: https://arxiv.org/abs/xxxx.xxxxx
```

Or invoke it explicitly:

```
/fey-r
```

## Project Structure

```
fey-r/
  SKILL.md                  # Skill definition and workflow
  assets/note-template.md   # Template for generated notes
```

## Customization

- **Change the workflow or interaction style**: edit `SKILL.md`
- **Change the notes format**: edit `assets/note-template.md`
- **Change when the skill triggers**: update the `description` field in `SKILL.md` frontmatter


## License

MIT
