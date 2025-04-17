"""Utility functions for TxtToYoutubeMusic."""

import sys
import chardet

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'  # Reset to default color

def read_song_queries(file_path="songs.txt"):
    """Read song queries from a text file.
    
    Args:
        file_path (str): Path to the file containing song queries.
        
    Returns:
        list: List of song queries.
        
    Raises:
        SystemExit: If file reading fails.
    """
    try:
        # First detect the encoding of the file
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            detected = chardet.detect(raw_data)
            encoding = detected['encoding']
        
        # Now read with the correct encoding
        with open(file_path, 'r', encoding=encoding) as f:
            # Read non-empty lines and strip whitespace.
            song_queries = [line.strip() for line in f if line.strip()]
        
        print(f"File read successfully using {encoding} encoding.")
        return song_queries
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)