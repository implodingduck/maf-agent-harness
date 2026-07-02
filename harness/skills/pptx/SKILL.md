---
name: pptx
description: Generate a PowerPoint (.pptx) deck from a structured JSON description of slides. Use this whenever the user asks to create, build, or export a PowerPoint / slide deck / presentation. Supports titles, subtitles, body text, content, images (URL or local), tables, and extra text boxes, with automatic template-layout matching.
---

# PowerPoint generation skill

This skill builds a `.pptx` file from a JSON description of the slides. It works
by analyzing the placeholder layout of a template deck, scoring each layout by a
"weight", and pairing every requested slide with the best-fitting layout before
filling in its placeholders. The logic mirrors the `scallighan/generate-pptx-api`
reference service.

## How to run it

The skill ships a Python script and a default template. Their absolute paths are
exported to the shell as `$MAF_PPTX_SKILL_DIR`, and the interpreter that has the
required packages installed is exported as `$MAF_PYTHON`. Use the **shell tool**
to run the generator with that interpreter (do not try to execute it through the
skill system):

1. Write the slide description to a JSON file, e.g. `slides.json`.
2. Run the generator:

   ```bash
   "$MAF_PYTHON" "$MAF_PPTX_SKILL_DIR/scripts/generate_pptx.py" \
     --input slides.json \
     --output presentation.pptx \
     --template "$MAF_PPTX_SKILL_DIR/assets/template2.pptx"
   ```

   - `--input`/`-i`: path to the JSON file, or `-` to read JSON from stdin.
   - `--output`/`-o`: output `.pptx` path (defaults to
     `generated_presentation_<timestamp>.pptx` in the current directory).
   - `--template`/`-t`: template `.pptx`. Omit to use python-pptx's built-in
     default template, or point at the bundled `assets/template2.pptx` for a
     richer set of layouts (Title Slide, Agenda, Section Break, Two Content,
     Summary, Table, Closing, ...).

The script prints the saved path to stdout and progress/warnings to stderr. It
requires the `python-pptx` package (already listed in the harness
`requirements.txt`).

## Input JSON schema

Provide either a bare list of slide objects, or an object with a `slides` list
and an optional `template` path. Every field on a slide is optional:

```json
{
  "template": "optional/path/to/template.pptx",
  "slides": [
    {
      "title": "Quarterly Review",
      "subtitles": ["FY25 Q3 Business Update"],
      "text": ["First body-text block", "Second body-text block"],
      "content": ["An object/content-placeholder bullet"],
      "pictures": ["https://example.com/chart.png", "local/logo.png"],
      "tables": [
        {
          "headers": ["Year", "Revenue", "Profit"],
          "rows": [["2023", "30M", "5M"], ["2024", "35M", "6M"]]
        }
      ],
      "extra_shapes": [
        {
          "shape_type": "text_box",
          "x": 914400, "y": 914400,
          "width": 3657600, "height": 914400,
          "text": "DRAFT"
        }
      ]
    }
  ]
}
```

Field mapping to PowerPoint placeholders:

- `title` → TITLE / CENTER_TITLE placeholder.
- `subtitles` → SUBTITLE placeholders (one per entry).
- `text` → BODY placeholders (one per entry).
- `content` → OBJECT / content placeholders (one per entry).
- `pictures` → PICTURE placeholders; each entry is a local path or an
  `http(s)` URL that is downloaded and inserted.
- `tables` → TABLE placeholders; each entry is `{"headers": [...], "rows": [[...]]}`.
- `extra_shapes` → free-floating shapes added directly to the slide. Only
  `shape_type: "text_box"` is currently supported. `x`, `y`, `width`, `height`
  are in English Metric Units (EMU); 914400 EMU = 1 inch.

## How layout matching works

- Each template layout gets a weight from its placeholder mix:
  `title*1 + subtitles*2 + text*5 + content*10 + pictures*100 + tables*1000`.
- Each requested slide gets a weight from its content using the same formula.
- If a slide's `title` (lowercased) exactly matches a layout name, that layout is
  used. Otherwise the layout with the closest weight is chosen — so a slide with
  a table lands on a table layout, a slide with a picture on a picture layout,
  and a bare-title slide on a title/section layout.
- Content that has no matching placeholder on the chosen layout is recorded in
  the slide's speaker notes as a warning, rather than being dropped silently.

## Examples
### Example 1:
{
  "template": "/code/app/templates/template2.pptx",
  "slides": [
    {
      "title": "2026 Internal Insights"
    },
    {
      "title": "Agenda",
      "content": [
          "2026 Internal Insights\nMichael Scott’s Portfolio Holdings\nImpact of MSFT Dropping 30% From Here\nLatest Microsoft News and Impact on Stock"
      ]
    },
    {
      "title": "2026 Internal Insights",
      "content": [
          " Macro regime: Age of capped real rates; structurally, real rates should gravitate toward neutral to negative, even if policy tightens cyclically.\nInflation drivers: Excess Chinese manufacturing capacity anchors global goods inflation; supply chains adapt, muting tariff-driven inflation.\nMonetary/FX architecture: Asia's credit creation increasingly in RMB/local currencies; monetary fragmentation advances.\nTrade policy: Protectionist rhetoric has muted inflation impact as supply chains reroute.\nTechnology themes: 'The AI Boom, Cracks and Opportunity,' 'Code Meets Cell,' 'The Autonomy Stack,' 'Artificial, but Surprisingly Empathetic.’\nChina, EM, and Breadth: Shift from concentrated growth toward wider dispersion across sectors/geographies; renewed interest in real assets.\nSource: BIG PICTURE: Key Themes for 2026 (1Q 2026), Morgan Stanley Investment Management."
      ]
    },
    {
      "title": "Michael Scott's Portfolio Holdings",
      "tables": [
          {
              "headers": [
                  "Ticker",
                  "Shares",
                  "Market Value",
                  "Current Price",
                  "Avg. Cost Basis",
                  "Unrealized Gain/Loss"
              ],
              "rows": [
                  [
                      "MSFT",
                      "172",
                      "$65,483.84",
                      "$380.72",
                      "$374.18",
                      "$1,124.88"
                  ],
                  [
                      "AAPL",
                      "1247",
                      "$170,489.84",
                      "$136.72",
                      "$177.44",
                      "-$50,775.16"
                  ],
                  [
                      "GOOG",
                      "792",
                      "$182,389.68",
                      "$230.29",
                      "$148.22",
                      "$65,002.32"
                  ],
                  [
                      "UNH",
                      "219",
                      "$63,039.15",
                      "$287.85",
                      "$524.67",
                      "-$51,863.58"
                  ],
                  [
                      "VOO",
                      "435",
                      "$117,036.75",
                      "$269.05",
                      "$438.39",
                      "-$73,662.90"
                  ],
                  [
                      "QQQ",
                      "152",
                      "$76,928.72",
                      "$506.11",
                      "$466.05",
                      "$6,089.20"
                  ],
                  [
                      "JEPI",
                      "5400",
                      "$341,496.00",
                      "$63.24",
                      "$55.29",
                      "$42,921.76"
                  ],
                  [
                      "SCHD",
                      "263",
                      "$16,839.89",
                      "$64.03",
                      "$62.10",
                      "$508.57"
                  ]
              ]
          }
      ]
    },
    {
      "title": "Impact of MSFT Dropping 30% from Here",
      "pictures": [      "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Microsoft_logo.svg/1024px-Microsoft_logo.svg.png"
      ],
      "content": [
          "Dollar loss on MSFT: $65,483.84 × 30% = $19,645.15 loss\nNew MSFT value: $45,838.69\nNew total portfolio value: $1,014,058.72 (down from $1,033,703.87)\nDollar impact on total portfolio: $19,645.15 decrease\nPercentage impact on total portfolio: approximately 1.9% decrease\nA 30% drop in MSFT would reduce Michael's entire portfolio value by about 1.9%, or $19.6K."
      ]
    },
    {
      "title": "Latest Microsoft News and Impact on Stock",
      "text": [
          "",
          ""
      ],
      "content": [
          "MSFT fell about 7% after Jan 28, 2026 fiscal Q2 print due to moderating cloud growth and lighter margin guidance.\nShares recently traded around $400.60 (Feb 25, 2026), reflecting partial recovery but continued volatility post-earnings.\nAzure and other cloud services grew 39% in Q2 (down from 40% in Q1); next quarter's Azure growth guided to 37–38% constant currency.\nImplied operating margin guidance of ~45.1% was below consensus; capex and finance leases reached a record $37.5B.\n",
          "Fundamentals: revenue $81.3B (+17% y/y), non‑GAAP EPS $4.14, Microsoft Cloud revenue $51.5B.\nCommercial remaining performance obligation rose 110% to $625B, with about 45% tied to OpenAI.\nKey watchpoints: Azure growth, margin path, AI monetization signals, management commentary at Mar 4, 2026 TMT Conference.\nTakeaway: Volatility driven by balance between AI investment and pace of cloud/AI monetization; steadier Azure trajectory and improving margins would likely dampen swings."
      ]
    },
    {
      "title": "Thank You!",
      "subtitles": [
          ""
      ]
    }
  ]
}

### Example 2:
{
  "template": "/code/app/templates/template2.pptx",
  "slides": [
      {
          "title": "Dynamic Slide Title"
      },
      {
          "title": "Agenda",
          "content": ["* Introduction\n* Main Topic\n* Conclusion"]
      },
      {
          "title": "Intro - Test Client",
          "pictures": [
              "https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/media/managed-virtual-network/diagram-managed-network.png?view=foundry-classic"
          ]
      },
      {
          "title": "Some Topic"
      },
      {

          "title": "We can now generate slides!",
          "content": ["We take a template PPTX with placeholders and fill them with data using Jinja2 templating."],
          "pictures": [
              "https://cdn-dynmedia-1.microsoft.com/is/image/microsoftcorp/Content-Card-Xbox-Controllers-Black-Detail"
          ]
      },
      {
          "title": "Comparison to Version 2",
          "text": ["version1", "version2"],
          "content": [
              "Jinja2 templating\nstatic page count",
              "Dynamic slide count\nmore flexible"
          ]
      },
      {
          "title": "Conclusion",
          "content": ["This is the conclusion slide."],
          "tables": [
              { 
                  "headers": ["Year", "Earnings", "Profit"],
                  "rows": [
                      ["2023", 10000000, 2000000],
                      ["2024", 25000000, 4000000],
                      ["2025", 35000000, 6000000]
                  ]
              }
          ]
      },
      {
          "title": "Thank you for your attention!",
          "subtitles": [
              "Test Bot\n- test@nothing.com\n- 555-123-4567"
          ]
      }
  ]
}


## Tips

- To pick a specific layout for a slide, set its `title` to the exact layout
  name (e.g. `"Section Break 2"`), or shape the slide's content so its weight
  matches the desired layout.
- Inspect a template's available layouts and placeholders before authoring
  slides with:

  ```bash
  "$MAF_PYTHON" - "$MAF_PPTX_SKILL_DIR/assets/template2.pptx" <<'PY'
  import sys
  from pptx import Presentation
  for lo in Presentation(sys.argv[1]).slide_layouts:
      print(lo.name, [str(ph.placeholder_format.type) for ph in lo.placeholders])
  PY
  ```
