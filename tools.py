"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Filter by price and size
    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    # Score by keyword overlap with description
    keywords = description.lower().split()

    def score(listing):
        searchable = " ".join([
            listing["title"],
            listing["description"],
            " ".join(listing["style_tags"]),
            listing["category"],
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(score(listing), listing) for listing in filtered]
    min_score = max(1, (len(keywords) + 1) // 2)
    scored = [(s, l) for s, l in scored if s >= min_score]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [listing for _, listing in scored]


# ── Tool 5: get_trending_styles ───────────────────────────────────────────────

def get_trending_styles(size: str | None = None, top_n: int = 5) -> list[dict]:
    """
    Surface the most popular style tags across the dataset as a proxy for
    what's currently trending. Optionally narrow to listings that match a size.

    Note: this uses the mock dataset as a stand-in for a live platform feed
    since real fashion platforms block scraping and have no free public API.
    The function shape is the same as a real API integration would require.

    Args:
        size:  If provided, only count tags from listings that match this size
               (case-insensitive). None counts across all listings.
        top_n: How many top tags to return. Defaults to 5.

    Returns:
        A list of dicts sorted by popularity, each with:
            tag (str): the style tag
            count (int): how many listings carry this tag
        Returns an empty list if nothing matches the size filter — no exception.
    """
    listings = load_listings()

    if size is not None:
        listings = [l for l in listings if size.lower() in l["size"].lower()]

    if not listings:
        return []

    counts: dict[str, int] = {}
    for listing in listings:
        for tag in listing.get("style_tags", []):
            counts[tag] = counts.get(tag, 0) + 1

    sorted_tags = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"tag": tag, "count": count} for tag, count in sorted_tags[:top_n]]


# ── Tool 4: estimate_price_fairness ──────────────────────────────────────────

def estimate_price_fairness(new_item: dict) -> dict:
    """
    Compare an item's price against similar listings in the dataset to estimate
    whether it's a deal, fair, or high.

    Args:
        new_item: A listing dict (the item the user is considering buying).

    Returns:
        A dict with:
            verdict (str): "deal", "fair", "high", or "not enough data"
            item_price (float): the item's price
            avg_comp_price (float or None): average price of comparable listings
            comp_count (int): number of comparables found
        Never raises an exception.
    """
    listings = load_listings()
    item_tags = set(new_item.get("style_tags", []))

    comps = [
        l for l in listings
        if l["id"] != new_item["id"]
        and l["category"] == new_item["category"]
        and item_tags & set(l.get("style_tags", []))
    ]

    if len(comps) < 3:
        return {
            "verdict": "not enough data",
            "item_price": new_item["price"],
            "avg_comp_price": None,
            "comp_count": len(comps),
        }

    avg = sum(l["price"] for l in comps) / len(comps)
    diff = (new_item["price"] - avg) / avg

    if diff < -0.15:
        verdict = "deal"
    elif diff > 0.15:
        verdict = "high"
    else:
        verdict = "fair"

    return {
        "verdict": verdict,
        "item_price": new_item["price"],
        "avg_comp_price": round(avg, 2),
        "comp_count": len(comps),
    }


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()
    item_summary = f"{new_item['title']} (${new_item['price']}, {new_item['condition']} condition)"

    if not wardrobe["items"]:
        prompt = (
            f"I just thrifted this item: {item_summary}. "
            f"Its style tags are: {', '.join(new_item['style_tags'])}. "
            "I don't have any wardrobe info for this user, so start your response by noting "
            "that you're giving general styling advice since no wardrobe was provided. "
            "Then suggest 1-2 general outfit ideas — what kinds of bottoms, shoes, "
            "or layers would pair well. Keep it casual and specific."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({', '.join(item['style_tags'])})"
            for item in wardrobe["items"]
        )
        prompt = (
            f"I just thrifted this item: {item_summary}. "
            f"Its style tags are: {', '.join(new_item['style_tags'])}. "
            f"Here's my current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 specific outfits using the new item and named pieces from my wardrobe. "
            "Keep it casual and specific."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Sorry, we couldn't build your fit card this time. Please try again."

    client = _get_groq_client()
    prompt = (
        f"I thrifted this item: {new_item['title']} for ${new_item['price']} on {new_item['platform']}. "
        f"Here's the outfit I'm putting together with it: {outfit}\n\n"
        "Write a 2-4 sentence Instagram/TikTok caption for this outfit. "
        "Make it sound like a real OOTD post — casual, authentic, not like a product description. "
        "Mention the item name, price, and platform once each, naturally. "
        "Capture the specific vibe of the outfit."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    return response.choices[0].message.content
