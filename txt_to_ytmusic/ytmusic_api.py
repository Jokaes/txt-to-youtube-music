"""YouTube Music API interactions for TxtToYoutubeMusic."""

import os
import sys
import traceback
from ytmusicapi import YTMusic


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
            sys.exit(1)
        
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
                        # Try to initialize again with the new file
                        yt = YTMusic(headers_file)
                        print("YouTube Music API initialized successfully with new credentials.")
                        return yt
                    else:
                        print("Failed to recreate authentication file.")
                        sys.exit(1)
                else:
                    print("Setup cancelled. Please fix the authentication file manually.")
                    sys.exit(1)
            else:
                print("Non-interactive mode: Cannot recreate authentication file. Exiting.")
                sys.exit(1)
    except Exception as e:
        print(f"Error initializing YouTube Music API: {e}")
        traceback.print_exc()
        sys.exit(1)


def search_song(yt, query):
    """Search for a song on YouTube Music.
    
    Args:
        yt (YTMusic): Initialized YouTube Music API client.
        query (str): The song query to search for.
        
    Returns:
        dict: The search result entry, or None if not found.
    """
    results = yt.search(query)
    if not results:
        print(f"  No results found for '{query}'. Skipping.")
        return None
    
    # Filter results to only include songs
    song_results = [
        result for result in results 
        if result.get('resultType') == 'song'
    ]
    
    if song_results:
        # Take the first song result
        return song_results[0]
    else:
        # If no songs are found, fall back to videos
        print(f"  No song results found for '{query}'. Falling back to video.")
        video_results = [
            result for result in results 
            if result.get('resultType') == 'video'
        ]
        
        if not video_results:
            print(f"  No video results found for '{query}'. Skipping.")
            return None
        
        return video_results[0]