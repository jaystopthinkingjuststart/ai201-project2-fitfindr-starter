"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card, estimate_price_fairness, get_trending_styles

load_dotenv()


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query_fallback(query: str) -> dict:
    """Regex fallback if LLM parsing fails."""
    price_match = re.search(r'(?:under|for|at|around|less than|no more than)?\s*\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    size_match = re.search(r'\bsize\s+(\S+)', query, re.IGNORECASE)

    max_price = float(price_match.group(1)) if price_match else None
    size = size_match.group(1) if size_match else None

    desc = query
    for match in filter(None, [price_match, size_match]):
        desc = desc.replace(match.group(0), "")
    desc = re.sub(r'\s+', ' ', desc).strip()

    return {"description": desc, "size": size, "max_price": max_price}


def _parse_query(query: str) -> dict:
    """Use LLM to extract description, size, and max_price from a natural language query.
    Falls back to regex if the LLM call fails or returns invalid JSON."""
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        prompt = (
            "Extract search parameters from this thrift shopping query. "
            "Return ONLY valid JSON with exactly these keys: "
            "\"description\" (str, the item being searched for), "
            "\"size\" (str or null, clothing size if mentioned), "
            "\"max_price\" (float or null, maximum price if mentioned). "
            f"Query: \"{query}\""
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return _parse_query_fallback(query)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "price_check": None,         # dict returned by estimate_price_fairness
        "trending_styles": [],       # list returned by get_trending_styles
        "relaxed": None,             # set if a filter was dropped to find results
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    # Step 2: parse the query
    session["parsed"] = _parse_query(query)
    parsed = session["parsed"]

    # Step 3: search, then loosen filters before giving up.
    # We drop price first (spending more is an easier ask than changing size),
    # then drop size if that still finds nothing.
    desc = parsed.get("description", query)
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    session["search_results"] = search_listings(desc, size=size, max_price=max_price)

    dropped = []
    if not session["search_results"] and max_price is not None:
        dropped.append("price")
        max_price = None
        session["search_results"] = search_listings(desc, size=size, max_price=max_price)

    if not session["search_results"] and size is not None:
        dropped.append("size")
        size = None
        session["search_results"] = search_listings(desc, size=size, max_price=max_price)

    if not session["search_results"]:
        session["error"] = (
            "No listings found for that search. "
            "Try adjusting budget or size, or using different keywords."
        )
        return session

    # Build a friendly note about anything we loosened
    if dropped:
        orig_price = parsed.get("max_price")
        orig_size = parsed.get("size")
        if "price" in dropped and "size" in dropped:
            session["relaxed"] = "couldn't find an exact match, so here are some options outside your price and size if you're interested:"
        elif "price" in dropped:
            session["relaxed"] = f"couldn't find anything under ${orig_price:g}, but here are some outside that range if you're interested:"
        elif "size" in dropped:
            session["relaxed"] = f"couldn't find anything in size {orig_size}, but here are some others if you're interested:"

    # Step 4: pick the top result and run supporting tools
    session["selected_item"] = session["search_results"][0]
    session["price_check"] = estimate_price_fairness(session["selected_item"])
    session["trending_styles"] = get_trending_styles(size=parsed.get("size"))

    # Step 5: suggest an outfit
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )

    # Step 6: create the fit card
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
