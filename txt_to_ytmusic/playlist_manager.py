"""Playlist management functionality for TxtToYoutubeMusic."""

import datetime
import logging
import sys
import time
import traceback

from tqdm import tqdm
from .utils import GREEN, YELLOW, RED, RESET


def generate_default_playlist_info():
    """Generate default timestamp-based playlist title and description.
    
    Returns:
        tuple: (default_title, default_description)
    """
    current_time = datetime.datetime.now()
    timestamp = current_time.strftime("%y%m%d%H%M%S")  # Format: yymmddhhmmss
    default_title = f"TxtToYoutubeMusic_{timestamp}"
    default_description = f"TxtToYoutubeMusic_{timestamp}"
    return default_title, default_description


def get_playlist_details(default_title, default_description, title=None, description=None, non_interactive=False):
    """Get playlist title and description from user or arguments.
    
    Args:
        default_title (str): Default title if user provides no input.
        default_description (str): Default description if user provides no input.
        title (str, optional): Title from arguments. Defaults to None.
        description (str, optional): Description from arguments. Defaults to None.
        non_interactive (bool): Whether to run in non-interactive mode.
        
    Returns:
        tuple: (playlist_title, playlist_description)
    """
    # If title or description are provided via arguments, use them directly
    playlist_title = title if title else None
    playlist_description = description if description else None
    
    # If we're in non-interactive mode, use defaults for any missing values
    if non_interactive:
        if not playlist_title:
            playlist_title = default_title
        if not playlist_description:
            playlist_description = default_description
    else:
        # Only prompt for title if it wasn't provided via arguments
        if not playlist_title:
            user_title = input(f"Enter playlist title [{default_title}]: ").strip()
            playlist_title = user_title if user_title else default_title
        
        # Print the title that will be used
        print(f"Using playlist title: {playlist_title}")
        
        # Only prompt for description if it wasn't provided via arguments
        if not playlist_description:
            user_description = input(f"Enter playlist description [{default_description}]: ").strip()
            playlist_description = user_description if user_description else default_description
        
        # Print the description that will be used
        print(f"Using playlist description: {playlist_description}")
    
    return playlist_title, playlist_description


def get_privacy_status(privacy_status=None, non_interactive=False):
    """Get playlist privacy setting from user or arguments.
    
    Args:
        privacy_status (str, optional): Privacy status from arguments. Defaults to None.
        non_interactive (bool): Whether to run in non-interactive mode.
        
    Returns:
        str: Privacy status ('PUBLIC', 'PRIVATE', or 'UNLISTED')
    """
    if non_interactive:
        return privacy_status if privacy_status else "PRIVATE"
    
    valid_options = ['public', 'private', 'unlisted']
    prompt_message = "Enter playlist visibility (public/private/unlisted) [private]: "
    user_input = input(prompt_message).strip().lower()
    
    # Default to private if input is empty
    if not user_input:
        privacy_status = "PRIVATE"
    elif user_input == 'public':
        privacy_status = "PUBLIC"
    elif user_input == 'private':
        privacy_status = "PRIVATE"
    elif user_input == 'unlisted':
        privacy_status = "UNLISTED"
    else:
        print(f"Invalid visibility option: '{user_input}'. Using 'private' as default.")
        privacy_status = "PRIVATE"
        
    print(f"Setting playlist visibility to: {privacy_status}")
    return privacy_status


def create_playlist(yt, privacy_status=None, title=None, description=None, non_interactive=False):
    """Create a new YouTube Music playlist with timestamp-based name.
    
    Args:
        yt (YTMusic): Initialized YouTube Music API client.
        privacy_status (str, optional): Playlist visibility - 'PUBLIC', 'PRIVATE', or 'UNLISTED'. Defaults to None (will prompt user).
        title (str, optional): Playlist title. Defaults to None.
        description (str, optional): Playlist description. Defaults to None.
        non_interactive (bool): Whether to run in non-interactive mode.
        
    Returns:
        tuple: (playlist_id, playlist_title)
        
    Raises:
        SystemExit: If playlist creation fails.
    """
    try:
        # Generate automatic timestamp-based title and description for defaults
        default_title, default_description = generate_default_playlist_info()
        
        # Get playlist details from user or arguments
        playlist_title, playlist_description = get_playlist_details(
            default_title, default_description, title, description, non_interactive
        )
        
        # Get privacy setting from user or arguments
        if privacy_status is None:
            privacy_status = get_privacy_status(privacy_status, non_interactive)
        
        # Create playlist with explicit string parameters
        print("Creating playlist...")
        
        # Make sure we're passing string values
        if not isinstance(playlist_title, str):
            playlist_title = str(playlist_title)
        if not isinstance(playlist_description, str):
            playlist_description = str(playlist_description)
            
        # Create playlist with explicit parameters
        playlist_id = yt.create_playlist(
            title=playlist_title,
            description=playlist_description,
            privacy_status=privacy_status
        )
        
        if not playlist_id:
            print("Error: Playlist creation returned None")
            sys.exit(1)
            
        print(f"Playlist '{playlist_title}' created successfully with ID: {playlist_id}")
        return playlist_id, playlist_title
    except Exception as e:
        print(f"Error creating playlist: {e}")
        print("Debug: Ensure browser authentication is properly set up.")
        # Print more details about the error
        traceback.print_exc()
        sys.exit(1)


def add_item_to_playlist(yt, playlist_id, video_id, query, retries=0, max_retries=2, retry_delay=6, allow_duplicates=False, unique_songs=None):
    """Add a single item to a playlist with retry logic.
    
    Args:
        yt (YTMusic): Initialized YouTube Music API client.
        playlist_id (str): ID of the target playlist.
        video_id (str): ID of the video to add.
        query (str): Original query (for logging purposes).
        retries (int): Current retry count.
        max_retries (int): Maximum number of retries.
        retry_delay (int): Base delay between retries in seconds.
        allow_duplicates (bool): Whether to allow duplicate songs.
        unique_songs (set, optional): Set of already added video_ids to avoid duplicates.
        
    Returns:
        tuple: (status, unique_songs) where status is "success", "duplicate", or "failure" 
        and unique_songs is the updated set of tracked video_ids
    """
    # Initialize the unique songs set if it doesn't exist
    if unique_songs is None:
        unique_songs = set()
        
    # Check if the video_id is already in our tracking set
    if video_id in unique_songs and not allow_duplicates:
        return "duplicate", unique_songs
        
    try:
        # Try to add the video to the playlist, using the duplicates parameter from ytmusicapi
        response = yt.add_playlist_items(playlist_id, [video_id], duplicates=allow_duplicates)
        
        # Check if the response indicates success
        if response and 'status' in response and response['status'] == 'STATUS_SUCCEEDED':
            # Add this video_id to our tracking set
            unique_songs.add(video_id)
            return "success", unique_songs
        elif response:
            # If we have a response but it doesn't indicate clear success
            logging.warning(f"Unexpected response for '{query}': {response}")
            return "success", unique_songs  # Assume success if we got any response without error
        else:
            logging.error(f"Empty response for '{query}', but no exception raised")
            return "failure", unique_songs
            
    except Exception as e:
        error_str = str(e).lower()  # Convert to lowercase for case-insensitive matching
        
        if "http 409: conflict" in error_str:
            # If it's a conflict but not clearly a duplicate, retry
            if retries < max_retries:
                retries += 1
                wait_time = retry_delay * retries
                logging.info(f"Conflict detected for '{query}'. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                time.sleep(wait_time)
                # Recursive call with increased retry count
                return add_item_to_playlist(yt, playlist_id, video_id, query, retries, max_retries, retry_delay, allow_duplicates, unique_songs)
            
        logging.error(f"Error processing '{query}': {e}")
        return "failure", unique_songs


def add_songs_to_playlist(yt, playlist_id, song_queries, max_retries=2, retry_delay=6, allow_duplicates=False):
    """Add songs from queries to the created playlist with retry mechanism.
    
    Args:
        yt (YTMusic): Initialized YouTube Music API client.
        playlist_id (str): ID of the target playlist.
        song_queries (list): List of song queries to search for.
        max_retries (int, optional): Maximum number of retries on conflict. Defaults to 2.
        retry_delay (int, optional): Base delay between retries in seconds. Defaults to 6.
        allow_duplicates (bool, optional): Whether to allow duplicate songs. Defaults to False.
        
    Returns:
        dict: Results containing counts of successful, failed, and not found songs.
    """
    # Import here to avoid circular import
    from .ytmusic_api import search_song
    
    total_queries = len(song_queries)
    successful_additions = []
    failed_additions = []
    not_found = []
    duplicates = []
    unique_songs = set()  # Initialize empty set to track unique video IDs
    
    # Create a single progress bar for the entire process
    with tqdm(total=total_queries, desc="Processing songs", unit="song") as pbar:
        for idx, query in enumerate(song_queries, start=1):
            # Update progress bar with only the song number for consistency
            current = idx
            total = total_queries
            pbar.set_description(f"Song {current}/{total}")
            
            # Search for the song
            result = search_song(yt, query)
            
            if not result:
                not_found.append(query)
                # Print info on a separate line, below the progress bar
                print(f"\r\033[K{RED}Not found: {query}{RESET}")
                pbar.update(1)
                continue
            
            video_id = result.get('videoId')
            if not video_id:
                # Print info on a separate line
                print(f"\r\033[K{RED}No video ID: {query}{RESET}")
                failed_additions.append(query)
                pbar.update(1)
                continue
            
            # Add to playlist with retry logic and track unique songs
            status, unique_songs = add_item_to_playlist(
                yt, playlist_id, video_id, query,
                0, max_retries, retry_delay, 
                allow_duplicates, unique_songs
            )
            
            title = result.get('title', query)
            artist = result.get('artists', [{}])[0].get('name', '') if result.get('artists') else ''
            
            if status == "success":
                # Print success info on a separate line
                if artist:
                    print(f"\r\033[K{GREEN}Added: {title} by {artist}{RESET}")
                else:
                    print(f"\r\033[K{GREEN}Added: {title}{RESET}")
                successful_additions.append(query)
            elif status == "duplicate":
                # Print duplicate info on a separate line
                print(f"\r\033[K{YELLOW}Duplicate: {query}{RESET}")
                duplicates.append(query)
            else:
                # Print failure info on a separate line
                print(f"\r\033[K{RED}Failed: {query}{RESET}")
                failed_additions.append(query)
            
            # Update the progress bar without changing its size
            pbar.update(1)
    
    # Print summary after progress bar completes
    print(f"\nUnique songs tracked: {len(unique_songs)}")
    return {
        'total': total_queries,
        'successful': successful_additions,
        'failed': failed_additions,
        'not_found': not_found,
        'duplicates': duplicates
    }