# Anki MCP Server

A Model Context Protocol (MCP) server that enables adding cards to Anki through AnkiConnect interface.

## Features

- Add cards to Anki with front-side (English) and back-side (Japanese) text
- Support for custom decks and note types
- Word highlighting with customizable colors
- Default configuration for English deck with Basic card type
- List available decks and note types
- Get collection statistics
- Full Unicode support for Japanese characters

## Prerequisites

### AnkiConnect Setup
1. **Install AnkiConnect add-on** in Anki:
   - Go to Tools → Add-ons → Get Add-ons
   - Enter code: `2055492159`
   - Restart Anki

2. **Configure AnkiConnect** (optional - default settings work):
   - Default port: `8765`
   - Default address: `127.0.0.1`
   - AnkiConnect config location: `~/.local/share/Anki2/[Profile]/collection.media/ankiconnect_config.json`

3. **Keep Anki running** while using the MCP server

## Installation
1. Create virtual environment and activate it:
```bash
uv venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
uv pip install -e .
```

3. Ensure Anki is running with AnkiConnect add-on enabled.

## Usage

### Starting the Server

```bash
python server.py
```

### MCP Client Configuration

To use this server with Claude Desktop or other MCP clients, add the following configuration:

#### Claude Desktop Configuration
Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    
    "Anki-MCP": {
      "command": "/path/to/bin/uv",
      "args": [
        "--directory", "/path/to/Anki-MCP",
        "run", "server.py"
      ]
    }
  },

  "globalShortcut": ""
}
```

#### Environment Variables (Optional)
```bash
export ANKICONNECT_URL="http://127.0.0.1:8765"  # Default AnkiConnect URL
```

### Available Tools

#### add_anki_card
Add a new card to Anki with highlighting support.

**Parameters:**
- `front` (required): Front side text (English)
- `back` (required): Back side text (Japanese)  
- `deck` (optional): Deck name (default: "English")
- `model` (optional): Card type/model (default: "Basic")
- `tags` (optional): Space-separated tags
- `highlight_front` (optional): List of words to highlight on front side
- `highlight_back` (optional): List of words to highlight on back side
- `highlight_color` (optional): RGB color dict (default: {Red: 255, Green: 255, Blue: 180})

**Example Response:**
```json
{
  "success": true,
  "note_id": 1749898112638,
  "front": "Hello, how are you?",
  "back": "こんにちは、元気ですか？",
  "deck": "English",
  "model": "Basic",
  "message": "Successfully added card to deck 'English'"
}
```

#### list_anki_decks
Get list of all available Anki decks with statistics.

**Example Response:**
```json
{
  "decks": ["English", "Japanese", "Vocabulary"],
  "deck_count": 3,
  "deck_details": {
    "English": {
      "name": "English",
      "card_count": 150,
      "note_count": 150
    }
  },
  "message": "Found 3 available decks"
}
```

#### list_anki_models
Get list of all available Anki note types/models.

**Example Response:**
```json
{
  "models": ["Basic", "Basic (and reversed card)", "Cloze"],
  "model_count": 3,
  "message": "Found 3 available note types/models"
}
```

#### get_anki_info
Get general information about the Anki collection.

**Example Response:**
```json
{
  "total_notes": 500,
  "total_cards": 650,
  "total_decks": 5,
  "total_models": 6,
  "available_decks": ["English", "Japanese"],
  "available_models": ["Basic", "Cloze"],
  "message": "Anki collection contains 500 notes, 650 cards across 5 decks"
}
```

## Configuration

### Default Settings
- **Deck**: English
- **Card Type**: Basic
- **Highlight Color**: RGB(255, 255, 180) - Light yellow
- **AnkiConnect URL**: `http://127.0.0.1:8765`

### AnkiConnect Port Configuration
The server connects to AnkiConnect on port **8765** by default. If you need to change this:

1. **Modify AnkiConnect settings** in Anki:
   - Go to Tools → Add-ons → AnkiConnect → Config
   - Change `webBindPort` to your desired port

2. **Update server configuration** in `server.py`:
   ```python
   ANKICONNECT_URL = "http://127.0.0.1:YOUR_PORT"
   ```

### Troubleshooting

**Connection Issues:**
- Ensure Anki is running
- Verify AnkiConnect add-on is installed and enabled
- Check that AnkiConnect is accessible at `http://127.0.0.1:8765`
- Test connection: `curl http://127.0.0.1:8765 -d '{"action":"version","version":6}'`

**Card Addition Issues:**
- Verify deck name exists (function will create if missing)
- Ensure model/note type exists in Anki
- Check for duplicate cards

## Requirements

- Python 3.10+
- MCP library (`mcp>=1.0.0`)
- Anki with AnkiConnect add-on
- Internet connection for initial setup