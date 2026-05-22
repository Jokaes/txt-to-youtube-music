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

### Graphical User Interface (GUI)

By default, running `main.py` without arguments will launch the Graphical User Interface (GUI):

```
python main.py
```

The GUI offers:
- A user-friendly dashboard to configure files and matching options.
- An **Authentication Assistant** where you can paste raw HTTP request headers directly to configure your connection without typing inside a CLI console.
- Live progress bars and song-by-song statistics.
- Direct link to open the newly created YouTube Music playlist in your browser.

### Command-Line Interface (CLI)

To force Command-Line Interface mode or customize execution from a terminal, you can pass arguments:

```
python main.py --cli
```

Or with custom parameters:
```
python main.py -f songs.txt -t "My Playlist" -p private --cli
```

### Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `--gui` | Run the Graphical User Interface (default if no other args are provided) |
| `--cli` | Force running in Command Line Interface mode |
| `-f`, `--file` | Path to input file with song queries (default: songs.txt) |
| `-t`, `--title` | Playlist title (default: auto-generated with timestamp) |
| `-d`, `--description` | Playlist description (default: same as title) |
| `-p`, `--privacy` | Playlist privacy: public, private, or unlisted (default: will prompt) |
| `--duplicates` | Allow duplicate songs in playlist (default: False) |
| `--perfect-match` | Only add songs that perfectly match the query (ignoring case) |
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

Authentication uses request headers copied from a signed-in YouTube Music browser session.

GUI flow:
- Open the **Authentication Assistant**.
- Paste raw request headers copied from a `music.youtube.com` network request.
- The app validates and saves them to `headers_auth.json` or the file you selected.

CLI flow:
- Pass `--auth` to point at an existing authentication file.
- If you run in interactive CLI mode and the file is missing, the script can guide you through creating one.

To capture valid headers:
- Log into YouTube Music in your browser.
- Open Developer Tools and switch to the Network tab.
- Refresh the page and pick a request made to `music.youtube.com`.
- Copy the request headers and save them through the GUI assistant or your auth JSON file.

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

- If authentication fails, recreate the auth file or pass the correct file path with `--auth`
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