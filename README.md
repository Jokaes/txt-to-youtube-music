# TxtToYoutubeMusic

A Python utility that creates YouTube Music playlists from text files containing song queries. 

## Features

- Create new YouTube Music playlists from text files
- Handles authentication automatically
- Supports custom playlist titles, descriptions, and privacy settings
- Detects and manages duplicate song entries
- Provides detailed execution summary with statistics
- Logs operations for debugging and record keeping

## Requirements

- Python 3.7+
- YouTube Music account
- Required packages are listed in `requirements.txt`

## Installation

1. Clone or download this repository
2. Install dependencies:
```
pip install -r requirements.txt
```

## Usage

Basic usage:
```
python main.py
```

With command-line arguments:
```
python main.py -f songs.txt -t "My Playlist" -p private
```

### Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `-f`, `--file` | Path to input file with song queries (default: songs.txt) |
| `-t`, `--title` | Playlist title (default: auto-generated with timestamp) |
| `-d`, `--description` | Playlist description (default: same as title) |
| `-p`, `--privacy` | Playlist privacy: public, private, or unlisted (default: will prompt) |
| `--duplicates` | Allow duplicate songs in playlist (default: False) |
| `--auth` | Path to authentication file (default: headers_auth.json) |
| `--non-interactive` | Run in non-interactive mode using defaults or provided arguments |

### Input File Format

The input file should contain one song query per line. A query can be a song title, artist name, or combination:

```
Michael Jackson - Billie Jean
Bohemian Rhapsody
The Beatles Yesterday
Atarashii Gakko! - Otonablue
Wu‐Tang Clan - C.R.E.A.M.
Billie Eilish - Bad Guy
坂本英城 - Lifelight
Natalia Lafourcade - Hasta La Raíz
Daft Punk - Around the World
```

## Authentication

On first run, the script will guide you through setting up authentication with YouTube Music:

1. The script will prompt you to create an authentication file
2. You'll need to extract authentication headers from your browser:
   - Log into YouTube Music in your browser
   - Open Developer Tools (F12 or right-click > Inspect)
   - Go to the Network tab
   - Refresh the page and look for any request to YouTube Music
   - Find and copy the request headers
   - Provide this information when prompted by the script
3. Authentication data is saved to `headers_auth.json` for future use

## Examples

Create a playlist from a custom file with a specific title:
```
python main.py -f my_songs.txt -t "Summer Hits 2025" -d "My favorite summer songs"
```

Create a public playlist allowing duplicates:
```
python main.py --duplicates -p public
```

Run in non-interactive mode (useful for automation):
```
python main.py --non-interactive
```

## Logs

The `logs/` directory contains detailed execution logs with:
- Song search results
- Playlist creation status
- Error messages and exceptions
- Timestamps for all operations

Log files are named with a timestamp (e.g., `txttoytmusic_20250417_174941.log`).

## Troubleshooting

- If authentication fails, try recreating the auth file with `-f` option
- Check the logs directory for detailed operation logs

## Disclaimer

This tool is provided for educational and personal use only. By using this software:

- You accept full responsibility for your actions and any consequences that may result from using this tool with your YouTube account.
- The author is not responsible for any account suspensions, terminations, or other penalties that YouTube/Google may impose as a result of using this software.
- This tool uses unofficial API methods and may violate YouTube's Terms of Service.
- Use at your own risk.

## Contributing

Contributions are welcome! Here's how you can contribute:

1. Create an issue describing the feature or bug you want to address
2. Fork the repository
3. Create a feature branch (`git checkout -b feature/amazing-feature`)
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request referencing the issue you created

Please ensure your code follows the project's style and includes appropriate tests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Created by Jokaes - feel free to contact me here or in Discord.

## Acknowledgments

Built using [ytmusicapi](https://github.com/sigma67/ytmusicapi) - a great library for interacting with YouTube Music.