"""TxtToYoutubeMusic main script.

This script creates YouTube Music playlists from text files containing song queries.
"""

import argparse
import datetime
import logging
import sys
import traceback

# Import from our package modules
from txt_to_ytmusic.logger import setup_logging
from txt_to_ytmusic.utils import read_song_queries
from txt_to_ytmusic.ytmusic_api import initialize_ytmusic
from txt_to_ytmusic.playlist_manager import (
    create_playlist, 
    add_songs_to_playlist
)


def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Create YouTube Music playlists from text files containing song queries."
    )
    parser.add_argument(
        "-f", "--file",
        default="songs.txt",
        help="Path to the input file containing song queries (default: songs.txt)"
    )
    parser.add_argument(
        "-t", "--title",
        help="Playlist title (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "-d", "--description",
        help="Playlist description (default: same as title)"
    )
    parser.add_argument(
        "-p", "--privacy",
        choices=["public", "private", "unlisted"],
        default=None,
        help="Playlist privacy setting (default: will prompt user)"
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Allow duplicate songs in playlist (default: False)"
    )
    parser.add_argument(
        "--auth",
        default="headers_auth.json",
        help="Path to the authentication file (default: headers_auth.json)"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode using defaults or provided arguments"
    )
    
    return parser.parse_args()


def main():
    """Main function that orchestrates the entire process.
    
    This function coordinates reading song queries, initializing the YouTube
    Music API, creating a playlist, adding songs, and providing a summary.
    """
    # Parse command line arguments first, for logging setup
    args = parse_arguments()
    
    # Setup logging with INFO level
    logger = setup_logging(logging.INFO)
    
    try:
        print("\n")
        logger.info("Starting TxtToYoutubeMusic")
        
        # Preparation phase - Get user inputs and initialize services
        song_queries = read_song_queries(args.file)
        if not song_queries:
            logger.error(f"No song queries found in file: {args.file}")
            sys.exit(1)
            
        logger.info(f"Found {len(song_queries)} song queries in {args.file}")
        
        # Initialize YouTube Music API
        try:
            yt = initialize_ytmusic(args.auth, non_interactive=args.non_interactive)
        except Exception as e:
            logger.critical(f"Failed to initialize YouTube Music API: {e}")
            traceback.print_exc()
            sys.exit(1)
        
        # Determine privacy status from args
        privacy_status = args.privacy.upper() if args.privacy else None
        
        # Create the playlist
        try:
            playlist_id, playlist_title = create_playlist(
                yt, 
                privacy_status=privacy_status,
                title=args.title,
                description=args.description,
                non_interactive=args.non_interactive
            )
        except Exception as e:
            logger.critical(f"Failed to create playlist: {e}")
            traceback.print_exc()
            sys.exit(1)
        
        # Handle duplicates setting
        allow_duplicates = args.duplicates
        
        # If not in non-interactive mode, ask about duplicates
        if not args.non_interactive and not args.duplicates:
            allow_dup_input = input("Allow duplicate songs in playlist? (y/n) [n]: ").strip().lower()
            allow_duplicates = allow_dup_input == 'y'
        
        logger.info(f"Duplicate songs allowed: {allow_duplicates}")
        
        # Begin performance measurement (after user input to avoid skewing metrics)
        start_time = datetime.datetime.now()
        logger.info(f"Starting song processing at {start_time}")
        
        # Process songs and add them to the playlist
        try:
            results = add_songs_to_playlist(yt, playlist_id, song_queries, allow_duplicates=allow_duplicates)
            logger.info(f"Song processing completed with {len(results['successful'])} successful additions")
        except Exception as e:
            logger.critical(f"Failed during song processing: {e}")
            traceback.print_exc()
            print("\nAn error occurred during song processing. Check logs for details.")
            sys.exit(1)
        
        # Calculate processing time
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # Format time for human readability (minutes only if necessary)
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        if minutes > 0:
            execution_time = f"{minutes} min. {seconds} sec."
        else:
            execution_time = f"{seconds} sec."
        
        logger.info(f"Total processing time: {execution_time}")
        
        # Print summary
        print("\n" + "="*50)
        print("TxtToYoutubeMusic EXECUTION SUMMARY")
        print("="*50)
        print(f"Playlist created: {playlist_title}")
        print(f"Playlist ID: {playlist_id}")
        print(f"Total songs processed: {results['total']}")
        print(f"Successfully added: {len(results['successful'])} songs")
        print(f"Failed to add: {len(results['failed'])} songs")
        print(f"Songs not found: {len(results['not_found'])} songs")
        print(f"Duplicates skipped: {len(results['duplicates'])} songs")
        print(f"Song processing time: {execution_time}")
        
        # If there were any failures, provide more details
        if results['failed'] or results['not_found'] or results['duplicates']:
            print("\nDetails:")
            if results['not_found']:
                print(f"Songs not found ({len(results['not_found'])}):")
                for song in results['not_found']:
                    print(f"  - {song}")
            if results['failed']:
                print(f"Failed additions ({len(results['failed'])}):")
                for song in results['failed']:
                    print(f"  - {song}")
            if results['duplicates']:
                print(f"Duplicate songs ({len(results['duplicates'])}):")
                for song in results['duplicates']:
                    print(f"  - {song}")
                
                # Create a file with the duplicate songs for reference
                duplicates_file = "songs_duplicates.txt"
                try:
                    with open(duplicates_file, "w", encoding="utf-8") as f:
                        for song in results['duplicates']:
                            f.write(f"{song}\n")
                    print(f"\nDuplicate songs have been saved to '{duplicates_file}'")
                except Exception as e:
                    logger.error(f"Could not save duplicates list: {e}")
                    print(f"Could not save duplicates list: {e}")
        
        print("\nTo access your playlist:")
        print(f"https://music.youtube.com/playlist?list={playlist_id}")
        print("="*50)
        
        logger.info(f"TxtToYoutubeMusic execution completed successfully. Playlist ID: {playlist_id}")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        logger.warning("Operation cancelled by user (KeyboardInterrupt)")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        traceback.print_exc()
        sys.exit(1)
        
    return 0


if __name__ == '__main__':
    main()