# This week's card

[中文](share_card_zh.md)

TOMC Memory can draw a picture of your last 7 days: how many fewer tokens went to the model, a 7-day bar chart and a few small numbers. It is made on your computer and nothing is uploaded. You decide whether to post it.

## Make one

From the desktop pet, the dashboard or the analysis page, choose **This week's card**. A preview opens:

- **Hide money** removes the money line and the model it was priced at.
- **Landscape** switches from 1080×1350 (4:5, good for a feed post) to 1200×630.
- **Copy image** puts the picture on the clipboard. **Save PNG…** saves it, by default to Pictures (or Desktop) as `TOMC-weekly-report-YYYYMMDD.png`.

From a terminal (works without a screen):

```bash
tomc share-card                      # PNG in this folder, terminal language
tomc share-card --lang en --landscape --out ~/Pictures
tomc share-card --hide-money --out card.png
```

It prints the file path and a one-line summary. It needs PySide6: `pip install 'tomc-memory[widget]'`.

## What the numbers mean

- **Fewer tokens sent** is the context text before minus after TOMC Memory prepared it, over the last 7 UTC days. Tokens are a local text estimate (the counter is named on the card), not the provider's count.
- **Share** is that saving divided by what would have been sent. With fewer than 5 usable records the card says "Too few samples" and gives no percentage.
- **Money** is "≈ $x at list price (estimate)": the saving times the listed uncached-input (or cache-read) price of the model named on the card. It is not a bill. Caching and subscriptions make the real difference smaller. If no price is known, the money line is hidden, never shown as $0.
- **Coverage** with the Windows gateway (beta) is "12 of 18 requests compressed". With TOMC tool calls it is how many preparations got shorter.
- **Top work type** comes from the gateway's request records, by kind of work only.

## Rules the card always follows

- Every token, money and percentage figure has "≈" or "estimate".
- The footer always says "Context estimate, not a bill or quota saving" and names the token counter; when money is shown it also names the price used. These lines cannot be turned off.
- Counts from TOMC tool calls and from the Windows gateway (beta) are counted differently. They are listed separately and never added up.
- A week with no saving says "Nothing saved this week"; if the context grew, it says so.
- Demo or test data gets a diagonal "演示数据 · DEMO DATA" watermark that cannot be turned off.
- Savings are never turned into water, electricity or trees. Those were never measured.
- No conversation names, folders, prompts or IDs appear on the card. Only kinds of work.

## For developers

```python
from tomc.share_card import card_data, card_strings, summary_line
from tomc.share_card_qt import render_card, show_share_card

data = card_data(path, "en")  # numbers and wording, no Qt
image = render_card(data, "portrait")  # QImage; "landscape" for 1200x630
show_share_card(parent, path)  # the preview dialog (non-modal)
```

`card_strings(data)` lists every string the card draws, which the tests use to check the rules above.
