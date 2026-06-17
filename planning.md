# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
search listings will look through the listings (in this case the mock dataset instead of actually querying live data) for items matching a user's requested description (including size/price if needed)

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): This represents what the user is looking for like "vintage jeans"
- `size` (str): this represents the size to filter by (this can also be none)
- `max_price` (float): this is the max a user wants to pay

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
this will return a list of matching listing dicts (sorted by relevance). an empty list is returned if no matches

**What happens if it fails or returns nothing:**
see above - we won't return an exception, we'll return an empty list

---

### Tool 2: suggest_outfit

**What it does:**
once we have a thrifted item and the existing user's wardrobe, we can suggest 1 or 2 full outfits

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): this is the item the user is considering buying 
- `wardrobe` (dict): this is the dict with the items in their wardrobe (needs to still work if its empty)

**What it returns:**
a string with outfit suggestions. if no wardrobe, we'll still return general styling advice

**What happens if it fails or returns nothing:**
see above, we'll still return general styling advice, NOT an exception

---

### Tool 3: create_fit_card

**What it does:**
this seems like an engagement features, a short and shareable caption will get generated for the thrifted find.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): this is the outfit suggestion from suggest outfit
- `new_item` (dict): this is the listing dict for the thrifted item that got returned from the user's original desires

**What it returns:**
<!-- Describe the return value -->
returns 2-4 sentences that could be used on social media.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
if it fails, we'll give a generic error/message, not an exception

---

### Additional Tools (if any)

These are the extra credit / stretch features. Documented here before building each one.

### Tool 4: estimate_price_fairness

**What it does:**
given a found item, it looks at comparable listings already in the dataset (same category, with overlapping style tags) and tells us whether the item's price is a deal, fair, or high compared to those comps. no LLM, just math on the dataset.

**Input parameters:**
- `new_item` (dict): the listing we want to price check

**What it returns:**
a dict with the verdict ("deal", "fair", or "high"), the item's price, the comparable count, and the average comp price. so the agent can say something like "this is a deal, $18 vs the $24 average for similar y2k tops."

**What happens if it fails or returns nothing:**
if there aren't enough comparable listings (say fewer than 3), we return a verdict of "not enough data" instead of guessing. no exception.

---

### Tool 5: get_trending_styles

**What it does:**
surfaces what styles are currently popular. real platforms like depop or tiktok block scraping and don't have a free public api for this, so we mock it using our own dataset as the "platform." we count the most common style_tags across listings, optionally narrowed to the user's size range, and return the top ones as a stand in for what's trending.

**Input parameters:**
- `size` (str or None): if given, only count tags on listings that fit this size

**What it returns:**
a list of the top style tags with their counts, sorted most popular first.

**What happens if it fails or returns nothing:**
if nothing matches the size filter, we return an empty list, not an exception.

---

### Stretch behavior 1: retry logic with fallback (planning loop change)

this is not a new tool, it's a change to the planning loop. right now if search_listings comes back empty we set an error and stop. with this, before giving up we retry once with the size filter removed (the most common reason a search comes back empty). if the loosened retry finds something we proceed normally but tell the user what we relaxed, like "couldn't find it in size M so here's the closest match ignoring size." we track what got relaxed in the session. only if the retry is also empty do we show the hard error.

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The loop looks at the session dict to decide what to do next -- each step reads from and writes to it.

First, we parse the user's natural language query using the LLM (Groq), asking it to return JSON with three keys: description, size (or null), max_price (or null). if the LLM call fails or returns bad JSON, we fall back to regex (looking for "under $X" for price and "size X" for size, everything else becomes the description). parsed params go into session["parsed"].

Then it calls search_listings with those params. This is the only condition that changes behavior -- if results is empty, we set session["error"] with a helpful message and return early. the loop is done and suggest_outfit never gets called. if results is not empty, we take the top result as session["selected_item"] and continue.

Next, suggest_outfit is called with session["selected_item"] and session["wardrobe"]. result goes into session["outfit_suggestion"]. then create_fit_card is called with session["outfit_suggestion"] and session["selected_item"]. result goes into session["fit_card"].

The loop knows it's done when session["fit_card"] is set and we return the full session -- or earlier if session["error"] was set.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

We'll use a session dict similar to hw/labs, keys like:
selected_item (what was chosen as the top item from search), outfit_suggestion (the full outfit pairing the selected item with the user's wardrobe, or a tailored suggestion to the item but not necessarily their wardrobe if they don't have one), and fit_card. 

We'll have an error field too

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | We'll suggest increasing the budget or changing size |
| suggest_outfit | Wardrobe is empty | We'll let the user know we didn't have their personal wardrobe data, but that we'd recommend styling it in x way generically based on the style of the selected item |
| create_fit_card | Outfit input is missing or incomplete | This would be a generic and graceful error message. Like sorry, I couldn't build your fit card, please try again. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
User query
   │
   ▼
Planning Loop
   │
   ├─► search_listings(description, size, max_price)
   │        │
   │        ├─ results == []  ─►  session["error"] = "No listings found,
   │        │                      try a higher budget or a different size"  ─►  return session
   │        │
   │        └─ results = [item, ...]
   │                 │
   │                 ▼
   │        session["selected_item"] = results[0]
   │
   ├─► suggest_outfit(selected_item, wardrobe)
   │        │
   │        ▼
   │        session["outfit_suggestion"] = "..."   (general advice if wardrobe is empty)
   │
   └─► create_fit_card(outfit_suggestion, selected_item)
            │
            ▼
        session["fit_card"] = "..."
            │
            ▼
        return session  ─►  user sees outfit_suggestion + fit_card
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I'll give claude code my tool 1, tool 2, and tool 3 blocks, and the milestone requirements, and explicitly ask it to walk me through if i've covered anything, if i'm missing anything, and to explain the missing pieces to me so I can understand and update the spec before code is autocompleted based on spec. I'll test it with the example queries as shown in the milestones and pay attention in terminal, and review the code it autocompletes.

**Milestone 4 — Planning loop and state management:**
I'll use claude to help test this and see if I missed any storage pieces or handoff, and ask it to explain and diff what's missed and understand it before accepting any changes. My inputs will be the planning loop, state management, and arch diagrams, and the output will be the planning loop function. I'll test by running it end to end with the example query and see if it matched what we blocked and mapped out earlier.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
It'll call search_listings(description="vintage graphic tee", size=None, max_price=30.0). no size in the query so that's None. if it returns an empty list, we stop here and tell the user to try adjusting their search (wider price, different keywords). otherwise we take the top result, something like the Bootleg Tour Tee at $24 on Depop.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
the top result from step 1 goes into suggest_outfit as new_item, along with the user's wardrobe if they have one. wardrobe has baggy jeans and chunky sneakers which matches the query context.

**Step 3:**
<!-- Continue until the full interaction is complete -->
fit card function is called with outfit suggestion as the input and the original thrifted item found to create a social media snipped

**Final output to user:**
<!-- What does the user actually see at the end? -->
user sees the outfit suggestion string (how to style it with their existing wardrobe) followed by the fit card caption (the shareable social media snippet)
