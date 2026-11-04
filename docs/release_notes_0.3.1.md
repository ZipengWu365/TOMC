# TOMC Memory 0.3.1 release notes

**English** | [简体中文](release_notes_0.3.1_zh.md) · 2026-10-31 · release tag `v0.3.1-preview.1`

0.3.1 is about the interface: the cat shows what it saved without a click, money is always labelled as an estimate, the demo page opens on a real result, and there is a weekly card you can share. Compression rules and the MCP tools are the same as in 0.3.0, and the paper's compiler kernel is unchanged. For 0.3.0, see the [0.3.0 release notes](release_notes_0.3.0.md).

## Weekly report card

- **Where to find it.** **Weekly report** is in the cat's right-click menu, on the dashboard and on the analysis page. It draws the last 7 days as one image: estimated tokens not sent, a 7-day bar chart and a few small figures.
- **What you can do with it.** Copy it, or save it as PNG in portrait (1080×1350) or landscape (1200×630). From a terminal, run `tomc share-card`.
- **Nothing leaves your computer.** The image is made locally and is not uploaded. It never shows chat names, folders, prompts or ids.
- **Honest numbers.**
  - Every figure carries "≈" or "estimate".
  - The footer always says "Context estimate, not a bill or quota saving", and this cannot be turned off.
  - Money is hidden when no price is known.
  - Under 5 usable records the card says "too few samples" instead of a percentage.
  - A week with no saving says so.
  - Demo data carries a watermark.
- See [Weekly report card](share_card.md).

## Desktop cat

- **Today's saving is always on show.** A small "Today −82K" label sits under the cat, and the idle cat is no longer faded. With no saving today the label is hidden, never shown as 0.
- **The cat grows with what it saves.** Its four forms now follow your estimated total saving: about 100K, 1M and 10M tokens. A form once reached is kept, even if a later request adds context, and a short bubble says when it grows. Before, the form followed the length of each single context, so most people never saw it change. The length of each context now only sets how much paper flies in that one animation, and the analysis chart calls those length bands, not stages.
- **Clearer bubble.** After a preparation, "Saved" is the one big number, with the context size in small print, and the cat smiles when it saved something.
- **Money is labelled as an estimate everywhere.**
  - Amounts read "≈ $x at list price (estimate)".
  - The tooltip says "Not a bill; less with caching or a subscription".
  - The dashboard and the pricing page now use the same calculation and wording.
- **No internal codes on screen.** Codes such as `short_history` are now plain sentences, and an unknown code reads "Sent unchanged". The dashboard's three technical status lines are now one dot and one sentence.
- **Smaller fixes.**
  - Quit is last in the menu.
  - Chats with no title show as "Untitled chat", never an id.
  - The new-session notice appears once.
  - When data cannot be read, stale per-model amounts and the chart are cleared.
  - English labels no longer get cut off.
- **Colour.** The macOS accent is the brand green instead of system blue.

## Demo page

- **Dark mode.** The brand and tabs are readable when the system is in dark mode.
- **Language and header.** Chinese by default with an English switch, plus a header with the cat and "When a fact changes, only the latest version comes back."
- **It opens on a live result.** The page runs the same 120-day sample as `tomc try` (budget 200).
  - The first line is one large number: "6,015 fewer tokens (−96%) · estimate".
  - It counts the whole request (instructions, question and memory), which is stricter than the history-only −97% that `tomc try` prints.
- **Side by side.** A two-column strip shows the original lines that were kept next to what the model receives, each with its source line number.
- **Plain signs.** Reductions always use "−"; an increase is called an increase.
- **Tour.** It now opens on an example that compresses. The old 31 → 36 example moved to a "Limits: very short chats" note.
- **Footer and phones.** The footer shows the installed version, and the page no longer scrolls sideways on a phone.

## AI amnesia stories

- **New forms.** There is a discussion form and an issue form for stories where an AI got a changed fact wrong in a long chat. Submitting requires ticking "I removed private content".
- **Stories become credited tests.** Good stories are rewritten as synthetic examples in `examples/amnesia/` with a regression test, credited to the person who sent them.
- **Honest labels.** Each one is marked "self-reported, not reproduced" or "reproduced (with command)". These stories are self-selected, so they are never used to estimate how often AIs forget.

## Unchanged

- Compression, the latest-value rules, the twelve MCP tools and save-nothing-by-default are the same as in 0.3.0.
- The 0.3.0 numbers (stale-value benchmark, `tomc try`) still hold, and the [evidence page](evidence.md) is unchanged.

## Upgrade

- **Plugins.**
  - Claude Code: update with `/plugin` and start a new session.
  - Codex: download the 0.3.1 ZIP and rerun its installer.
  - Claude Desktop: install the 0.3.1 `.mcpb`.
- **Desktop cat.** Restart the cat once.
