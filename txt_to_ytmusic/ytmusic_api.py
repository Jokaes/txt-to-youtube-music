"""YouTube Music API interactions for TxtToYoutubeMusic."""

import json
import os
import traceback
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
    # Add quotes around the query for perfect match searches
    formatted_query = f'"{query}"' if perfect_match else query
    
    # First search for songs
    results = yt.search(formatted_query, filter='songs', ignore_spelling=True, limit=100)
    if not results:
        print(f"  No song results found for '{query}'. Skipping.")
        # Don't return None here - we'll try searching for videos below
    else:
        if perfect_match:
            # Look for a perfect match (ignoring case)
            query_lower = query.lower()
            for result in results:
                title = result.get('title', '').lower()
                if title == query_lower:
                    print(f"  Perfect match found for '{query}': {result.get('title')}")
                    return result
            
            # If perfect match was required but not found, return None
            print(f"  No perfect match found for '{query}'. Skipping.")
        else:
            # Take the first song result when perfect match is not required
            return results[0]
    
    # If no songs are found, fall back to videos with a separate search
    print(f"  No song results found for '{query}'. Falling back to video search.")
    video_results = yt.search(formatted_query, filter='videos', ignore_spelling=True, limit=100)
    
    if not video_results:
        print(f"  No video results found for '{query}'. Skipping.")
        return None
    
    if perfect_match and video_results:
        # Look for a perfect match in videos if songs weren't found
        query_lower = query.lower()
        for result in video_results:
            title = result.get('title', '').lower()
            if title == query_lower:
                print(f"  Perfect video match found for '{query}': {result.get('title')}")
                return result
        
        # If perfect match was required but not found, return None
        print(f"  No perfect video match found for '{query}'. Skipping.")
        return None
    
    return video_results[0]