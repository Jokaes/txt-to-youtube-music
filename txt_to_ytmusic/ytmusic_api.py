"""YouTube Music API interactions for TxtToYoutubeMusic."""

import json
import os
import re
import traceback
import unicodedata
from ytmusicapi import YTMusic


TRANSIENT_AUTH_HEADER_NAMES = {
    "accept-encoding",
    "alt-used",
    "connection",
    "content-encoding",
    "content-length",
    "host",
    "te",
}

NOISY_RESULT_TERMS = {
    "live",
    "cover",
    "remix",
    "mix",
    "karaoke",
    "nightcore",
    "slowed",
    "sped",
    "instrumental",
    "fancam",
}


def _get_header_value(headers, header_name):
    """Return a header value from a dict using case-insensitive lookup."""
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return value
    return None


def sanitize_auth_headers(headers):
    """Remove transient browser transport headers from copied auth data."""
    if not isinstance(headers, dict):
        raise ValueError("Authentication data must be a JSON object with header names and values.")

    sanitized_headers = {}
    for key, value in headers.items():
        if key.lower() in TRANSIENT_AUTH_HEADER_NAMES:
            continue
        sanitized_headers[key] = value

    return sanitized_headers


def validate_auth_headers(headers):
    """Validate that auth headers look usable for YouTube Music requests."""
    if not isinstance(headers, dict):
        raise ValueError("Authentication data must be a JSON object with header names and values.")

    cookie = _get_header_value(headers, "cookie")
    if not cookie:
        raise ValueError("Authentication data is missing the Cookie header.")

    routing_headers = {
        "host": _get_header_value(headers, "host"),
        "origin": _get_header_value(headers, "origin"),
        "x-origin": _get_header_value(headers, "x-origin"),
        "referer": _get_header_value(headers, "referer"),
        "alt-used": _get_header_value(headers, "alt-used"),
    }
    music_domain_header_found = False
    wrong_domain_headers = []
    for name, value in routing_headers.items():
        if not value:
            continue

        value_lower = str(value).lower()
        if "music.youtube.com" in value_lower:
            music_domain_header_found = True
        elif "youtube.com" in value_lower:
            wrong_domain_headers.append(name)

    if wrong_domain_headers:
        joined_headers = ", ".join(wrong_domain_headers)
        raise ValueError(
            "Authentication headers were copied from a non-music YouTube page. "
            "Copy the request headers from a signed-in https://music.youtube.com request "
            f"instead. Problem headers: {joined_headers}."
        )

    if not music_domain_header_found:
        raise ValueError(
            "Authentication headers do not include a https://music.youtube.com origin or referer. "
            "Copy the request headers from a signed-in request on https://music.youtube.com."
        )


def validate_auth_headers_file(headers_file):
    """Validate an auth JSON file before passing it to ytmusicapi."""
    try:
        with open(headers_file, "r", encoding="utf-8") as file_obj:
            headers = json.load(file_obj)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Authentication file '{headers_file}' is not valid JSON: {exc.msg}."
        ) from exc

    validate_auth_headers(headers)
    sanitized_headers = sanitize_auth_headers(headers)

    if sanitized_headers != headers:
        with open(headers_file, "w", encoding="utf-8") as file_obj:
            json.dump(sanitized_headers, file_obj, indent=4, ensure_ascii=False)
            file_obj.write("\n")

    return sanitized_headers


def _normalize_search_text(text):
    """Normalize common clipboard punctuation and spacing for YTMusic queries."""
    translation_table = str.maketrans({
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "﹘": "-",
        "﹣": "-",
        "－": "-",
    })
    normalized_text = unicodedata.normalize("NFKC", text)
    normalized_text = normalized_text.translate(translation_table)
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
    return normalized_text


def _canonicalize_comparison_text(text):
    """Convert text into a looser comparison form for query/result matching."""
    normalized_text = _normalize_search_text(text).casefold()
    normalized_text = unicodedata.normalize("NFKD", normalized_text)
    normalized_text = "".join(
        character for character in normalized_text if not unicodedata.combining(character)
    )
    normalized_text = normalized_text.replace("-", " ")
    normalized_text = re.sub(r"[^\w\s]", "", normalized_text)
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
    return normalized_text


def _extract_query_parts(query):
    """Split a query into two sides when it uses a dash separator."""
    normalized_query = _normalize_search_text(query).replace('"', '').replace("'", "")
    parts = [part.strip() for part in re.split(r"\s+-\s+", normalized_query, maxsplit=1)]
    return [part for part in parts if part]


def _build_match_part_groups(query):
    """Return candidate part groupings for title/artist alignment checks."""
    explicit_parts = _extract_query_parts(query)
    if len(explicit_parts) == 2:
        return [explicit_parts]

    normalized_query = _normalize_search_text(query).replace('"', '').replace("'", "")
    tokens = normalized_query.split()
    part_groups = []

    if len(tokens) >= 3:
        for split_index in range(len(tokens) - 1, 0, -1):
            left_part = " ".join(tokens[:split_index]).strip()
            right_part = " ".join(tokens[split_index:]).strip()
            if left_part and right_part:
                part_groups.append([left_part, right_part])

    part_groups.append([normalized_query])
    return part_groups


def _contains_all_terms(haystack, needle):
    """Return True when every token from needle appears in haystack."""
    haystack_tokens = set(_canonicalize_comparison_text(haystack).split())
    needle_tokens = set(_canonicalize_comparison_text(needle).split())
    return bool(needle_tokens) and needle_tokens.issubset(haystack_tokens)


def _noise_rank(result):
    """Prefer canonical releases over live/remix/cover style results."""
    title_tokens = set(_canonicalize_comparison_text(result.get("title", "")).split())
    return len(NOISY_RESULT_TERMS.intersection(title_tokens))


def _build_search_queries(query):
    """Build a small set of query variants for robust matching."""
    normalized_query = _normalize_search_text(query)
    quoted_stripped_query = normalized_query.replace('"', '').replace("'", "")
    candidate_queries = [normalized_query]

    if quoted_stripped_query != normalized_query:
        candidate_queries.append(quoted_stripped_query)

    parts = re.split(r"\s+-\s+", quoted_stripped_query, maxsplit=1)
    if len(parts) == 2:
        left_part, right_part = (part.strip() for part in parts)
        if left_part and right_part:
            candidate_queries.append(f"{left_part} {right_part}")
            candidate_queries.append(f"{right_part} {left_part}")
            candidate_queries.append(right_part)
            candidate_queries.append(left_part)

    unique_queries = []
    for candidate_query in candidate_queries:
        if candidate_query and candidate_query not in unique_queries:
            unique_queries.append(candidate_query)
    return unique_queries


def _extract_title_artist(query):
    """Extract title and artist from a query formatted like 'title - artist'."""
    normalized_query = _normalize_search_text(query).replace('"', '').replace("'", "")
    parts = re.split(r"\s+-\s+", normalized_query, maxsplit=1)
    if len(parts) != 2:
        return normalized_query, None

    title_part, artist_part = (part.strip() for part in parts)
    return title_part, artist_part or None


def _matches_perfect_query(result, query):
    """Return True when the result exactly matches the user's query."""
    normalized_title = _canonicalize_comparison_text(result.get('title', ''))
    if not normalized_title:
        return False

    query_parts = [
        _canonicalize_comparison_text(part)
        for part in _extract_query_parts(query)
        if _canonicalize_comparison_text(part)
    ]
    if len(query_parts) == 2:
        normalized_artists = [
            _canonicalize_comparison_text(artist.get('name', ''))
            for artist in result.get('artists', [])
            if _canonicalize_comparison_text(artist.get('name', ''))
        ]
        if not normalized_artists:
            return False

        artist_candidates = set(normalized_artists)
        if len(normalized_artists) > 1:
            artist_candidates.add(" ".join(normalized_artists))

        left_part, right_part = query_parts
        return (
            normalized_title == left_part and right_part in artist_candidates
        ) or (
            normalized_title == right_part and left_part in artist_candidates
        )

    normalized_query = _canonicalize_comparison_text(query)
    return normalized_title == normalized_query


def _pick_search_result(results, query, perfect_query=None):
    """Prefer song results, then videos, while favoring artist matches when available."""
    playable_results = [
        result
        for result in results
        if result.get('resultType') in {'song', 'album', 'video'} and result.get('videoId')
    ]

    def result_type_rank(result):
        return {
            'song': 0,
            'album': 1,
            'video': 2,
        }.get(result.get('resultType'), 3)

    def query_alignment_rank(result):
        title_text = result.get('title', '')
        artist_text = ' '.join(artist.get('name', '') for artist in result.get('artists', []))
        combined_text = f"{title_text} {artist_text}".strip()
        best_rank = 5

        for query_parts in _build_match_part_groups(query):
            if len(query_parts) >= 2:
                left_part, right_part = query_parts[0], query_parts[1]
                title_matches_left = _contains_all_terms(title_text, left_part)
                title_matches_right = _contains_all_terms(title_text, right_part)
                artist_matches_left = _contains_all_terms(artist_text, left_part)
                artist_matches_right = _contains_all_terms(artist_text, right_part)

                if (title_matches_left and artist_matches_right) or (title_matches_right and artist_matches_left):
                    best_rank = min(best_rank, 0)
                    continue
                if title_matches_left or title_matches_right:
                    best_rank = min(best_rank, 1)
                    continue
                if _contains_all_terms(combined_text, left_part) and _contains_all_terms(combined_text, right_part):
                    best_rank = min(best_rank, 2)
                    continue
                if artist_matches_left or artist_matches_right:
                    best_rank = min(best_rank, 3)
                    continue
                best_rank = min(best_rank, 4)
                continue

            single_part = query_parts[0]
            if _contains_all_terms(title_text, single_part):
                best_rank = min(best_rank, 0)
                continue
            if _contains_all_terms(combined_text, single_part):
                best_rank = min(best_rank, 1)
                continue
            best_rank = min(best_rank, 2)

        return best_rank

    ranked_results = sorted(
        playable_results,
        key=lambda result: (
            query_alignment_rank(result),
            result_type_rank(result),
            _noise_rank(result),
            len(_canonicalize_comparison_text(result.get('title', ''))),
        ),
    )

    if perfect_query:
        for result in ranked_results:
            if _matches_perfect_query(result, perfect_query):
                return result
        return None

    if ranked_results:
        return ranked_results[0]
    return None


def check_headers_file(headers_file, non_interactive=False):
    """Check if headers file exists and offer to create it if not.
    
    Args:
        headers_file (str): Path to the authentication headers file.
        non_interactive (bool): Whether to run in non-interactive mode.
        
    Returns:
        bool: True if file exists or was created, False if creation was cancelled.
    """
    if not os.path.exists(headers_file):
        print(f"Authentication file '{headers_file}' not found.")
        
        if non_interactive:
            print("Non-interactive mode: Cannot create authentication file. Exiting.")
            return False
            
        print("Let's create one automatically:")
        
        print("\n1. Open YouTube Music in your browser (https://music.youtube.com)")
        print("2. Make sure you're logged in to your account")
        print("3. We'll use ytmusicapi's setup assistant to create your authentication file\n")
        
        create_choice = input("Would you like to set up authentication now? (y/n) [y]: ").strip().lower()
        if create_choice == "" or create_choice == "y":
            return create_auth_file(headers_file)
        else:
            print("Setup cancelled. Please create the authentication file manually.")
            return False
    return True


def create_auth_file(headers_file):
    """Create an authentication file using ytmusicapi setup assistant.
    
    Args:
        headers_file (str): Path where the authentication file should be created.
        
    Returns:
        bool: True if file was created successfully, False otherwise.
    """
    try:
        from ytmusicapi import setup
        # Run the setup process to create headers file
        setup(filepath=headers_file)
        print("Authentication file created successfully!")
        return True
    except Exception as setup_error:
        print(f"Error during setup: {setup_error}")
        print("\nAlternative manual method:")
        print("1. Open YouTube Music in your browser")
        print("2. Open developer tools (F12 or Ctrl+Shift+I)")
        print("3. Go to Network tab")
        print("4. Find a request to 'browse' or 'next'")
        print("5. Copy the request headers")
        print(f"6. Create '{headers_file}' with the copied headers")
        return False


def initialize_ytmusic(headers_file='headers_auth.json', non_interactive=False):
    """Initialize YouTube Music API with browser authentication.
    
    Args:
        headers_file (str): Path to the authentication headers file.
        non_interactive (bool): Whether to run in non-interactive mode.
        
    Returns:
        YTMusic: Initialized YouTube Music API client.
        
    Raises:
        SystemExit: If initialization fails.
    """
    try:
        print("Initializing YouTube Music API...")
                
        if not check_headers_file(headers_file, non_interactive):
            raise FileNotFoundError(f"Authentication file '{headers_file}' could not be loaded or created.")
        validate_auth_headers_file(headers_file)
        
        # Try to initialize YTMusic with the headers file
        try:
            yt = YTMusic(headers_file)
            # Test the connection by making a simple API call
            yt.get_library_songs(limit=1)
            print("YouTube Music API initialized successfully.")
            return yt
        except Exception as auth_error:
            # If initialization fails, the headers file might be invalid
            print(f"Failed to authenticate with YouTube Music: {auth_error}")
            print(f"The headers file '{headers_file}' might be invalid or expired.")
            
            if not non_interactive:
                recreate_choice = input("Would you like to recreate the authentication file? (y/n) [y]: ").strip().lower()
                if recreate_choice == "" or recreate_choice == "y":
                    # Run the setup process again
                    if create_auth_file(headers_file):
                        validate_auth_headers_file(headers_file)
                        # Try to initialize again with the new file
                        yt = YTMusic(headers_file)
                        print("YouTube Music API initialized successfully with new credentials.")
                        return yt
                    else:
                        raise RuntimeError("Failed to recreate authentication file.")
                else:
                    raise PermissionError("Setup cancelled. Please fix the authentication file manually.")
            else:
                raise PermissionError(
                    "Non-interactive mode: Cannot recreate authentication file or auth is invalid. "
                    "Copy fresh headers from a signed-in https://music.youtube.com request."
                ) from auth_error
    except Exception as e:
        print(f"Error initializing YouTube Music API: {e}")
        traceback.print_exc()
        raise e


def search_song(yt, query, perfect_match=False):
    """Search for a song on YouTube Music.
    
    Args:
        yt (YTMusic): Initialized YouTube Music API client.
        query (str): The song query to search for.
        perfect_match (bool, optional): Whether to require a perfect match. Defaults to False.
        
    Returns:
        dict: The search result entry, or None if not found.
    """
    search_queries = _build_search_queries(query)
    perfect_query = query if perfect_match else None

    for search_query in search_queries:
        results = yt.search(search_query, ignore_spelling=True, limit=20)
        if not results:
            continue

        selected_result = _pick_search_result(
            results,
            query=query,
            perfect_query=perfect_query,
        )
        if selected_result:
            if perfect_match:
                print(f"  Perfect match found for '{query}': {selected_result.get('title')}")
            return selected_result

    if perfect_match:
        print(f"  No perfect match found for '{query}'. Skipping.")
    else:
        print(f"  No song or video results found for '{query}'. Skipping.")
    return None