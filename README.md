# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

### `search_listings(description, size, max_price)`
- **Inputs:** `description` (str), `size` (str or None), `max_price` (float or None)
- **Output:** `list[dict]`, the matching listings sorted by relevance, or an empty list if nothing matches
- **Purpose:** filters the mock dataset by price and size, then scores what's left by keyword overlap with the description. no LLM, just filtering and ranking.

### `suggest_outfit(new_item, wardrobe)`
- **Inputs:** `new_item` (dict, the listing), `wardrobe` (dict with an `items` list)
- **Output:** `str`, 1 to 2 outfit suggestions
- **Purpose:** calls the LLM to style the found item. if the wardrobe has items it pairs the item with named pieces, if it's empty it gives general styling advice instead.

### `create_fit_card(outfit, new_item)`
- **Inputs:** `outfit` (str, the suggestion from suggest_outfit), `new_item` (dict, the listing)
- **Output:** `str`, a 2 to 4 sentence social caption
- **Purpose:** calls the LLM at a higher temperature so captions vary, and turns the outfit into a shareable OOTD post.

### `estimate_price_fairness(new_item)` (extra credit)
- **Inputs:** `new_item` (dict, the listing)
- **Output:** `dict` with `verdict` ("deal", "fair", "high", or "not enough data"), `item_price`, `avg_comp_price`, and `comp_count`
- **Purpose:** no LLM. finds comparable listings in the dataset (same category, at least one shared style tag) and compares the item's price to their average. if it's more than 15% under it's a deal, more than 15% over it's high, otherwise fair. if there are fewer than 3 comps we return "not enough data" instead of guessing.

### `get_trending_styles(size, top_n)` (extra credit)
- **Inputs:** `size` (str or None, narrows to listings matching that size), `top_n` (int, default 5)
- **Output:** `list[dict]`, each with `tag` and `count`, sorted most popular first
- **Purpose:** surfaces what styles are popular by counting the most common style_tags. real platforms block scraping and have no free api, so we mock it using our own dataset as the platform. the function shape is the same as a real api integration would need.

---

## Planning Loop

`run_agent()` in `agent.py` runs the steps in order. first it parses the query with the LLM into description, size, and max_price (with a regex fallback if the LLM errors or returns bad JSON). then it calls `search_listings`. if results come back empty we don't give up right away, we retry with loosened filters (extra credit): drop the price ceiling first since spending more is an easier ask than changing size, then drop size if that still finds nothing, and we tell the user what we relaxed. only if both retries come back empty do we set an error and return early, so `suggest_outfit` never runs on empty input. otherwise we take the top result, run `estimate_price_fairness` and `get_trending_styles` on it (extra credit), pass it to `suggest_outfit`, then pass that outfit plus the item to `create_fit_card`. the loop is done once the fit card is set, or earlier if an error was set.

## State Management

everything lives in one session dict created by `_new_session()`. each step reads from it and writes its result back, so state flows forward without re-prompting or hardcoding. keys are `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, `price_check`, `trending_styles`, `relaxed`, and `error`. the selected_item that goes into `suggest_outfit` is the exact same dict that came out of search, and the outfit_suggestion that goes into `create_fit_card` is the exact string suggest_outfit returned.

---

## Interaction Walkthrough

<!-- Walk through a complete interaction step by step: natural language query → each tool call (and why) → final fit card.
     Walk through this carefully — it's how graders follow your agent's reasoning without a live demo.
     Use a specific example — do not leave this as a template. -->

**User query:** "looking for a vintage graphic tee under $30"

**Step 1, Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0` (parsed out of the query)
- Why this tool: we need to find a real listing before we can style anything.
- Output: a ranked list, top result is the Y2K Baby Tee at $18.

**Step 2, Tools called (extra credit):**
- Tools: `estimate_price_fairness` and `get_trending_styles`, both run on the top result
- Input: the selected listing dict, plus the parsed size for the trend filter
- Why these tools: price fairness tells the user if $18 is a good deal, trending styles surfaces what's popular so they have context.
- Output: a verdict of "deal" ($18 vs a $22 average for similar tops), and a list of top style tags like vintage and streetwear.

**Step 3, Tool called:**
- Tool: `suggest_outfit`
- Input: the top listing dict, plus the example wardrobe
- Why this tool: now that we have an item, we pair it with the user's actual closet.
- Output: a styling suggestion using named pieces like the baggy jeans and chunky sneakers.

**Step 4, Tool called:**
- Tool: `create_fit_card`
- Input: the outfit string from step 3, plus the same listing dict
- Why this tool: turns the look into something shareable.
- Output: a casual 2 to 4 sentence caption mentioning the item, price, and platform.

**Final output to user:** the listing details with the price verdict, the outfit idea, the fit card caption, and the trending styles, one in each panel of the app.

---

## Error Handling and Fail Points

<!-- For each tool, describe the specific failure mode and what your agent does in response.
     This maps to the error handling section of the rubric (F5-C1). -->

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | no listings match the query | returns an empty list, never an exception. the agent retries with loosened filters (drop price, then size) before giving up. only if both retries are still empty does it set an error and stop before calling the other tools. |
| `suggest_outfit` | wardrobe is empty | returns general styling advice and notes upfront that no wardrobe was provided, instead of crashing or returning an empty string. |
| `create_fit_card` | outfit string is empty or whitespace | returns a graceful message, "Sorry, we couldn't build your fit card this time. Please try again.", with no LLM call and no exception. |
| `estimate_price_fairness` | fewer than 3 comparable listings | returns a verdict of "not enough data" with a null average, instead of giving a confident verdict off one or two comps. |
| `get_trending_styles` | nothing matches the size filter | returns an empty list, and the app shows "no trending data available for this search." no exception. |

**Concrete example from testing:** running the agent with "designer ballgown size XXS under $5" still found nothing even after dropping the price and size filters, so it returned "No listings found for that search. Try adjusting budget or size, or using different keywords." and left `fit_card` as None, confirming the branch stops early. a softer case, "vintage graphic tee under $10", found nothing under $10 so it dropped the price, landed on the $18 Y2K tee, and told the user "couldn't find anything under $10, but here are some outside that range if you're interested:".

---

## Spec Reflection

**One way planning.md helped during implementation:**
writing the planning loop section out as actual branches, not just "it decides what to do," meant the code basically wrote itself. i already knew the one place behavior changes is the empty search check, so wiring `run_agent` was just following my own steps.

**One divergence from your spec, and why:**
the spec didn't mention query parsing at all, it assumed the params arrived clean. once i started Milestone 4 i realized the agent gets raw natural language, so i added an LLM parsing step with a regex fallback. i documented it back in planning.md after the fact.

---

## AI Usage

**Instance 1, the tools.** i gave the AI my Tool 1, 2, and 3 spec blocks from planning.md one at a time and had it implement each function in `tools.py`. for `search_listings` the first version kept everything that matched even one keyword, so a belt matching only "vintage" ranked alongside actual tees. i changed it to require matching at least half the keywords, which dropped the noise.

**Instance 2, the planning loop.** i gave the AI my Planning Loop and State Management sections plus the architecture diagram and asked it to implement `run_agent`. it produced the right sequence and the early return on empty results. the one thing i added myself was the LLM query parsing with a regex fallback, since my spec didn't cover parsing raw natural language and i wanted it to not break if the LLM call failed.

---

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
