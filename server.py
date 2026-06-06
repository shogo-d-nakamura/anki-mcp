#!/usr/bin/env python
"""
MCP server for Anki card creation using AnkiConnect
"""
import logging
import sys
import json
import re
import os
import subprocess
import platform
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Logger configuration
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG', '').lower() == 'true' else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_ankiconnect_url():
    """Get AnkiConnect URL, handling different environments (WSL2, Ubuntu, macOS)"""
    # First check if URL is explicitly set via environment variable
    if 'ANKICONNECT_URL' in os.environ:
        url = os.environ['ANKICONNECT_URL']
        logger.info(f"Using ANKICONNECT_URL from environment: {url}")
        return url
    
    # Detect the platform
    system = platform.system()
    
    # Check if we're in WSL2
    is_wsl = 'WSL_DISTRO_NAME' in os.environ or 'WSL_INTEROP' in os.environ
    
    if is_wsl:
        logger.info("Detected WSL2 environment")
        # In WSL2, try multiple approaches to connect to Windows host
        
        # Method 1: Use host.docker.internal (works in some WSL2 setups)
        test_urls = [
            "http://host.docker.internal:8765",
            "http://172.17.0.1:8765",  # Common Docker bridge IP
            "http://localhost:8765",    # Sometimes WSL2 forwards localhost
        ]
        
        # Method 2: Try to get Windows host IP from various sources
        try:
            # Get IP from /etc/resolv.conf (WSL2 specific)
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        ip = line.split()[1]
                        if ip != '127.0.0.1':
                            test_urls.insert(0, f"http://{ip}:8765")
                            break
        except:
            pass
        
        # Method 3: Try to get IP using ip route (Linux specific)
        try:
            result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0 and 'via' in result.stdout:
                ip = result.stdout.split('via')[1].split()[0]
                test_urls.insert(0, f"http://{ip}:8765")
        except:
            pass
        
        # Test each URL
        import socket
        for url in test_urls:
            try:
                host = url.replace("http://", "").split(":")[0]
                port = 8765
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    logger.info(f"AnkiConnect found at {url}")
                    return url
            except:
                continue
        
        logger.warning("Could not connect to AnkiConnect from WSL2. Make sure:")
        logger.warning("1. Anki is running on Windows with AnkiConnect enabled")
        logger.warning("2. Windows Firewall allows connections from WSL2")
        logger.warning("3. AnkiConnect is configured to accept connections from WSL2 IP range")
        logger.warning("4. Set ANKICONNECT_URL environment variable to Windows host IP")
    
    # For native Linux/macOS, just use localhost
    logger.info(f"Running on {system} - using localhost")
    return "http://127.0.0.1:8765"

ANKICONNECT_URL = get_ankiconnect_url()

def ankiconnect_request(action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Send request to AnkiConnect"""
    if params is None:
        params = {}
    
    request_data = {
        "action": action,
        "version": 6,
        "params": params
    }
    
    # Add API key if configured
    api_key = os.environ.get('ANKICONNECT_API_KEY')
    if api_key:
        request_data["key"] = api_key
        logger.debug(f"Using API key: {api_key[:10]}...")
    
    logger.debug(f"Sending request to {ANKICONNECT_URL}: {action}")
    
    try:
        request_json = json.dumps(request_data).encode('utf-8')
        request_obj = urllib.request.Request(ANKICONNECT_URL, request_json)
        response = urllib.request.urlopen(request_obj)
        response_data = json.loads(response.read().decode('utf-8'))
        
        if response_data.get('error'):
            logger.error(f"AnkiConnect returned error: {response_data['error']}")
            raise Exception(f"AnkiConnect error: {response_data['error']}")
        
        logger.debug(f"Request successful: {action}")
        return response_data
    except urllib.error.URLError as e:
        logger.error(f"Failed to connect to {ANKICONNECT_URL}: {e}")
        raise Exception(f"Failed to connect to AnkiConnect at {ANKICONNECT_URL}. Make sure Anki is running with AnkiConnect add-on enabled. Error: {e}")
    except Exception as e:
        logger.error(f"AnkiConnect request failed: {e}")
        raise Exception(f"AnkiConnect request failed: {e}")

# Check for required module imports
try:
    from mcp.server.fastmcp import FastMCP
    required_modules_available = True
except ImportError as e:
    print(f"Failed to import required modules: {str(e)}", file=sys.stderr)
    print("Please install required packages: uv pip install -e .", file=sys.stderr)
    # Implement minimal MCP server
    if 'mcp' in str(e):
        print("MCP module is not installed. Starting minimal server.", file=sys.stderr)
        try:
            # Minimal implementation using standard library only
            print("Starting minimal MCP server...", file=sys.stderr)
            import http.server
            import socketserver
            import json
            
            PORT = 8080
            
            class MinimalHandler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "status": "error",
                        "message": "Required packages are not installed. Please run `uv pip install -e .`."
                    }
                    self.wfile.write(json.dumps(response).encode())
                
                def do_POST(self):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "error": "Required packages are not installed. Please run `uv pip install -e .`."
                    }
                    self.wfile.write(json.dumps(response).encode())
            
            print(f"Starting minimal server on port {PORT}...", file=sys.stderr)
            with socketserver.TCPServer(("", PORT), MinimalHandler) as httpd:
                print(f"Server is running on port {PORT}", file=sys.stderr)
                httpd.serve_forever()
        except Exception as server_error:
            print(f"Failed to start minimal server: {str(server_error)}", file=sys.stderr)
            sys.exit(1)
    sys.exit(1)

# Initialize MCP server
mcp = FastMCP("Anki Card Creator")


def apply_highlight(text: str, highlight_words: List[str], color: Dict[str, int] = None) -> str:
    """
    Apply highlighting to specified words in text using HTML formatting
    
    Args:
        text: The text to highlight words in
        highlight_words: List of words to highlight
        color: RGB color dictionary with keys 'Red', 'Green', 'Blue'
        
    Returns:
        Text with highlighted words formatted as HTML
    """
    if not highlight_words:
        return text
    
    # Default highlight color: RGB(255, 255, 180) - light yellow
    if color is None:
        color = {"Red": 255, "Green": 255, "Blue": 180}
    
    # Convert RGB to hex (ensure values are integers)
    r = int(color['Red'])
    g = int(color['Green']) 
    b = int(color['Blue'])
    hex_color = f"#{r:02x}{g:02x}{b:02x}"
    
    # Apply highlighting to each word
    highlighted_text = text
    for word in highlight_words:
        # Check if word contains non-ASCII characters (like Japanese)
        if any(ord(char) > 127 for char in word):
            # For non-ASCII text (Japanese), use exact match without word boundaries
            pattern = re.escape(word)
        else:
            # For ASCII text (English), use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(word)}\b'
        
        replacement = f'<span style="background-color: {hex_color}">{word}</span>'
        highlighted_text = re.sub(pattern, replacement, highlighted_text, flags=re.IGNORECASE)
    
    return highlighted_text


HIGHLIGHT_SPAN_RE = re.compile(
    r'<span\s+style="background-color:\s*#[0-9a-fA-F]{6}"\s*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)


def strip_highlight(text: str) -> str:
    """Remove <span style="background-color: #hex">...</span> wrappers produced by apply_highlight()."""
    if not text:
        return text
    return HIGHLIGHT_SPAN_RE.sub(r'\1', text)


def _ext_from_url(url: str) -> str:
    """Infer image extension from URL path; default to .png."""
    path = url.split('?', 1)[0].split('#', 1)[0]
    lower = path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"):
        if lower.endswith(ext):
            return ext
    return ".png"


def _store_image_from_url(url: str) -> str:
    """Download image via AnkiConnect storeMediaFile and return the stored filename."""
    import hashlib
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    filename = f"anki_mcp_{digest}{_ext_from_url(url)}"
    ankiconnect_request("storeMediaFile", {"filename": filename, "url": url})
    return filename


@mcp.tool()
def add_anki_card(
    front: str,
    back: str,
    deck: str = "English",
    model: str = "Basic",
    tags: str = "",
    highlight_front: List[str] = None,
    highlight_back: List[str] = None,
    highlight_color: Dict[str, int] = None,
    allow_duplicate: bool = False,
    image_url_front: Optional[str] = None,
    image_url_back: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new card to Anki using AnkiConnect

    Args:
        front: Front side text (English)
        back: Back side text (Japanese)
        deck: Deck name (default: "English")
        model: Card type/model (default: "Basic")
        tags: Space-separated tags for the card
        highlight_front: List of words to highlight on front side
        highlight_back: List of words to highlight on back side
        highlight_color: RGB color for highlighting (default: {Red: 255, Green: 255, Blue: 180})
        allow_duplicate: If True, allow adding even if Anki considers the note a duplicate
        image_url_front: Optional image URL to attach to the front side (appended as <img>)
        image_url_back: Optional image URL to attach to the back side (appended as <img>)

    Returns:
        Dictionary containing operation result and card details
    """
    try:
        # Check if required fields are provided
        if not front:
            return {"error": "Front side text is required"}
        if not back:
            return {"error": "Back side text is required"}
            
        logger.info(f"Adding Anki card with front: '{front[:50]}...' to deck: {deck}")
        
        # Apply highlighting if specified
        if highlight_front:
            front = apply_highlight(front, highlight_front, highlight_color)
        if highlight_back:
            back = apply_highlight(back, highlight_back, highlight_color)

        # Attach images if specified
        attached_images = {}
        if image_url_front:
            filename = _store_image_from_url(image_url_front)
            front = f'{front}<br><img src="{filename}">'
            attached_images["front"] = filename
        if image_url_back:
            filename = _store_image_from_url(image_url_back)
            back = f'{back}<br><img src="{filename}">'
            attached_images["back"] = filename
        
        # Check if deck exists, create if it doesn't
        try:
            deck_names_response = ankiconnect_request("deckNames")
            existing_decks = deck_names_response.get('result', [])
            
            if deck not in existing_decks:
                logger.info(f"Creating new deck: {deck}")
                ankiconnect_request("createDeck", {"deck": deck})
        except Exception as deck_error:
            logger.warning(f"Error checking/creating deck: {deck_error}")
        
        # Check if model exists
        try:
            model_names_response = ankiconnect_request("modelNames")
            available_models = model_names_response.get('result', [])
            
            if model not in available_models:
                return {
                    "error": f"Model '{model}' not found. Available models: {available_models}",
                    "success": False
                }
        except Exception as model_error:
            logger.warning(f"Error checking models: {model_error}")
        
        # Prepare note fields
        fields = {
            "Front": front,
            "Back": back
        }
        
        # Convert tags string to list
        tag_list = tags.strip().split() if tags.strip() else []
        
        # Add the note using AnkiConnect
        note_payload = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "tags": tag_list
        }
        if allow_duplicate:
            note_payload["options"] = {"allowDuplicate": True}

        response = ankiconnect_request("addNote", {"note": note_payload})
        note_id = response.get('result')

        if note_id:
            return {
                "success": True,
                "note_id": note_id,
                "front": front,
                "back": back,
                "deck": deck,
                "model": model,
                "tags": tags,
                "highlighted_words_front": highlight_front or [],
                "highlighted_words_back": highlight_back or [],
                "attached_images": attached_images,
                "message": f"Successfully added card to deck '{deck}'"
            }
        else:
            return {
                "error": "Failed to add note - no note ID returned",
                "success": False
            }
            
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Error occurred while adding Anki card: {error_msg}")
        
        # Clean up error message for better user experience
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        elif "duplicate" in error_msg.lower():
            error_msg = "Duplicate card detected - card already exists"
        elif not error_msg or error_msg.strip() == "":
            error_msg = "Unknown error occurred while adding card"
        
        return {
            "error": error_msg,
            "success": False
        }


@mcp.tool()
def list_anki_decks() -> Dict[str, Any]:
    """
    Get list of all available Anki decks using AnkiConnect
    
    Returns:
        Dictionary containing list of decks with details
    """
    try:
        # Get deck names
        deck_names_response = ankiconnect_request("deckNames")
        decks = deck_names_response.get('result', [])
        
        # Get deck statistics
        deck_details = {}
        for deck_name in decks:
            try:
                # Get card and note counts for this deck
                deck_cards_response = ankiconnect_request("findCards", {"query": f'"deck:{deck_name}"'})
                deck_notes_response = ankiconnect_request("findNotes", {"query": f'"deck:{deck_name}"'})
                
                card_count = len(deck_cards_response.get('result', []))
                note_count = len(deck_notes_response.get('result', []))
                
                deck_details[deck_name] = {
                    "name": deck_name,
                    "card_count": card_count,
                    "note_count": note_count
                }
            except Exception as deck_error:
                logger.warning(f"Could not get stats for deck {deck_name}: {deck_error}")
                deck_details[deck_name] = {
                    "name": deck_name,
                    "card_count": "unknown",
                    "note_count": "unknown"
                }
        
        return {
            "decks": decks,
            "deck_count": len(decks),
            "deck_details": deck_details,
            "message": f"Found {len(decks)} available decks"
        }
        
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while retrieving decks"
        logger.exception(f"Error occurred while retrieving Anki decks: {error_msg}")
        
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        
        return {
            "error": error_msg,
            "success": False
        }


@mcp.tool()
def list_anki_models() -> Dict[str, Any]:
    """
    Get list of all available Anki note types/models using AnkiConnect
    
    Returns:
        Dictionary containing list of models with details
    """
    try:
        model_names_response = ankiconnect_request("modelNames")
        models = model_names_response.get('result', [])
        
        return {
            "models": models,
            "model_count": len(models),
            "message": f"Found {len(models)} available note types/models"
        }
        
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while retrieving models"
        logger.exception(f"Error occurred while retrieving Anki models: {error_msg}")
        
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        
        return {
            "error": error_msg,
            "success": False
        }


@mcp.tool()
def get_anki_info() -> Dict[str, Any]:
    """
    Get general information about the Anki collection using AnkiConnect
    
    Returns:
        Dictionary containing collection statistics and configuration
    """
    try:
        # Get deck names and models
        deck_names_response = ankiconnect_request("deckNames")
        model_names_response = ankiconnect_request("modelNames")
        
        available_decks = deck_names_response.get('result', [])
        available_models = model_names_response.get('result', [])
        
        # Calculate totals
        total_decks = len(available_decks)
        total_models = len(available_models)
        
        # Try to get collection info (may not be available in all AnkiConnect versions)
        total_notes = "unknown"
        total_cards = "unknown"
        
        try:
            # Try to get total card/note counts by querying all cards
            all_cards_response = ankiconnect_request("findCards", {"query": "*"})
            all_notes_response = ankiconnect_request("findNotes", {"query": "*"})
            
            if 'result' in all_cards_response:
                total_cards = len(all_cards_response['result'])
            if 'result' in all_notes_response:
                total_notes = len(all_notes_response['result'])
        except Exception as count_error:
            logger.warning(f"Could not get total card/note counts: {count_error}")
        
        return {
            "total_notes": total_notes,
            "total_cards": total_cards,
            "total_decks": total_decks,
            "total_models": total_models,
            "available_decks": available_decks,
            "available_models": available_models,
            "message": f"Anki collection contains {total_notes} notes, {total_cards} cards across {total_decks} decks"
        }
        
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while retrieving collection info"
        logger.exception(f"Error occurred while retrieving Anki information: {error_msg}")
        
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        
        return {
            "error": error_msg,
            "success": False
        }


@mcp.tool()
def search_anki_cards(
    query: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search for Anki cards/notes using Anki's search syntax

    Args:
        query: Search query using Anki syntax (e.g. "deck:English", "tag:vocab", "front:hello", or plain keywords)
        limit: Maximum number of notes to return (default: 10)

    Returns:
        Dictionary containing matching notes with their fields, tags, and metadata
    """
    try:
        if not query:
            return {"error": "Search query is required", "success": False}

        logger.info(f"Searching Anki notes with query: '{query}', limit: {limit}")

        # Find matching note IDs
        find_response = ankiconnect_request("findNotes", {"query": query})
        all_note_ids = find_response.get('result', [])
        total_found = len(all_note_ids)

        if total_found == 0:
            return {
                "notes": [],
                "total_found": 0,
                "returned": 0,
                "message": f"No notes found for query: '{query}'"
            }

        # Limit results
        note_ids = all_note_ids[:limit]

        # Get full note info
        notes_response = ankiconnect_request("notesInfo", {"notes": note_ids})
        raw_notes = notes_response.get('result', [])

        # Flatten note data
        notes = []
        for note in raw_notes:
            fields = {}
            for field_name, field_data in note.get('fields', {}).items():
                fields[field_name] = field_data.get('value', '')

            notes.append({
                "note_id": note.get('noteId'),
                "model": note.get('modelName'),
                "tags": note.get('tags', []),
                "fields": fields
            })

        return {
            "notes": notes,
            "total_found": total_found,
            "returned": len(notes),
            "message": f"Found {total_found} note(s), returning {len(notes)}"
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while searching cards"
        logger.exception(f"Error occurred while searching Anki cards: {error_msg}")

        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."

        return {"error": error_msg, "success": False}


@mcp.tool()
def update_anki_card(
    note_id: int,
    front: Optional[str] = None,
    back: Optional[str] = None,
    tags: Optional[str] = None,
    deck: Optional[str] = None,
    highlight_front: Optional[List[str]] = None,
    highlight_back: Optional[List[str]] = None,
    highlight_color: Optional[Dict[str, int]] = None,
    clear_highlights: bool = False,
    append_front: Optional[str] = None,
    append_back: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing Anki note's fields, tags, or deck

    Field update order (per side): clear_highlights -> append -> highlight.
    If `front`/`back` is provided it becomes the new base text; otherwise the
    existing field value is used as base.

    Args:
        note_id: The note ID to update
        front: New front side text (optional, replaces existing front)
        back: New back side text (optional, replaces existing back)
        tags: New space-separated tags - replaces all existing tags (optional)
        deck: Move card(s) to this deck (optional)
        highlight_front: List of words to highlight on front (re-highlights after clear)
        highlight_back: List of words to highlight on back (re-highlights after clear)
        highlight_color: RGB color for highlighting (default: {Red: 255, Green: 255, Blue: 180})
        clear_highlights: If True, remove existing highlight <span> wrappers before other edits
        append_front: Text to append to the front side (after clear, before highlight)
        append_back: Text to append to the back side (after clear, before highlight)

    Returns:
        Dictionary containing update result details
    """
    try:
        field_change_requested = (
            front is not None or back is not None
            or highlight_front is not None or highlight_back is not None
            or append_front is not None or append_back is not None
            or clear_highlights
        )
        if not field_change_requested and tags is None and deck is None:
            return {
                "error": "At least one of front, back, tags, deck, highlight_front, highlight_back, append_front, append_back, or clear_highlights must be provided",
                "success": False,
            }

        logger.info(f"Updating Anki note {note_id}")

        # Verify note exists
        notes_response = ankiconnect_request("notesInfo", {"notes": [note_id]})
        existing_notes = notes_response.get('result', [])
        if not existing_notes or not existing_notes[0].get('noteId'):
            return {"error": f"Note with ID {note_id} not found", "success": False}

        existing_note = existing_notes[0]
        existing_fields = existing_note.get('fields', {})
        updated = []

        # Build updated fields
        if field_change_requested:
            fields: Dict[str, str] = {}

            def _build_side(new_value, existing_key, clear, append_text, highlight_words):
                base = new_value if new_value is not None else existing_fields.get(existing_key, {}).get('value', '')
                changed = new_value is not None
                if clear:
                    cleared = strip_highlight(base)
                    if cleared != base:
                        changed = True
                    base = cleared
                if append_text is not None:
                    base = base + append_text
                    changed = True
                if highlight_words:
                    base = apply_highlight(base, highlight_words, highlight_color)
                    changed = True
                return base, changed

            front_value, front_changed = _build_side(
                front, "Front", clear_highlights, append_front, highlight_front
            )
            back_value, back_changed = _build_side(
                back, "Back", clear_highlights, append_back, highlight_back
            )

            if front_changed:
                fields["Front"] = front_value
            if back_changed:
                fields["Back"] = back_value

            if fields:
                ankiconnect_request("updateNoteFields", {"note": {"id": note_id, "fields": fields}})
                updated.extend(list(fields.keys()))

        # Update tags
        if tags is not None:
            current_tags = set(existing_note.get('tags', []))
            new_tags = set(tags.strip().split()) if tags.strip() else set()

            tags_to_remove = current_tags - new_tags
            tags_to_add = new_tags - current_tags

            if tags_to_remove:
                ankiconnect_request("removeTags", {"notes": [note_id], "tags": " ".join(tags_to_remove)})
            if tags_to_add:
                ankiconnect_request("addTags", {"notes": [note_id], "tags": " ".join(tags_to_add)})
            updated.append("tags")

        # Move to different deck
        if deck is not None:
            # Auto-create deck if needed
            try:
                deck_names_response = ankiconnect_request("deckNames")
                existing_decks = deck_names_response.get('result', [])
                if deck not in existing_decks:
                    logger.info(f"Creating new deck: {deck}")
                    ankiconnect_request("createDeck", {"deck": deck})
            except Exception as deck_error:
                logger.warning(f"Error checking/creating deck: {deck_error}")

            # Get card IDs for this note and move them
            cards_response = ankiconnect_request("findCards", {"query": f"nid:{note_id}"})
            card_ids = cards_response.get('result', [])
            if card_ids:
                ankiconnect_request("changeDeck", {"cards": card_ids, "deck": deck})
            updated.append("deck")

        return {
            "success": True,
            "note_id": note_id,
            "updated": updated,
            "message": f"Successfully updated note {note_id}: {', '.join(updated)}"
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while updating card"
        logger.exception(f"Error occurred while updating Anki card: {error_msg}")

        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."

        return {"error": error_msg, "success": False}


@mcp.tool()
def delete_anki_cards(
    note_ids: List[int]
) -> Dict[str, Any]:
    """
    Delete Anki notes by their IDs

    Note: AnkiConnect silently ignores non-existent note IDs.

    Args:
        note_ids: List of note IDs to delete

    Returns:
        Dictionary containing deletion result
    """
    try:
        if not note_ids:
            return {"error": "At least one note ID is required", "success": False}

        logger.info(f"Deleting {len(note_ids)} Anki note(s): {note_ids}")

        ankiconnect_request("deleteNotes", {"notes": note_ids})

        return {
            "success": True,
            "deleted_count": len(note_ids),
            "deleted_note_ids": note_ids,
            "message": f"Successfully deleted {len(note_ids)} note(s)"
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while deleting cards"
        logger.exception(f"Error occurred while deleting Anki cards: {error_msg}")

        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."

        return {"error": error_msg, "success": False}


@mcp.tool()
def add_anki_cards_batch(
    cards: List[Dict[str, Any]],
    deck: str = "English",
    model: str = "Basic",
    tags: str = "",
    highlight_color: Dict[str, int] = None,
    allow_duplicate: bool = False
) -> Dict[str, Any]:
    """
    Add multiple cards to Anki at once

    Args:
        cards: List of card dicts, each with "front" and "back" (required), plus optional "deck", "model", "tags", "highlight_front", "highlight_back", "image_url_front", "image_url_back", "allow_duplicate"
        deck: Default deck name (default: "English")
        model: Default card type/model (default: "Basic")
        tags: Default space-separated tags
        highlight_color: RGB color for highlighting (default: {Red: 255, Green: 255, Blue: 180})
        allow_duplicate: Default duplicate policy for cards that don't override it

    Returns:
        Dictionary containing batch operation results with success/failure counts
    """
    try:
        if not cards:
            return {"error": "At least one card is required", "success": False}

        logger.info(f"Batch adding {len(cards)} Anki card(s)")

        # Validate default model
        try:
            model_names_response = ankiconnect_request("modelNames")
            available_models = model_names_response.get('result', [])
        except Exception as model_error:
            logger.warning(f"Error checking models: {model_error}")
            available_models = []

        # Collect all deck names and create missing ones
        all_decks = set()
        for card in cards:
            all_decks.add(card.get("deck", deck))

        try:
            deck_names_response = ankiconnect_request("deckNames")
            existing_decks = set(deck_names_response.get('result', []))
            for deck_name in all_decks - existing_decks:
                logger.info(f"Creating new deck: {deck_name}")
                ankiconnect_request("createDeck", {"deck": deck_name})
        except Exception as deck_error:
            logger.warning(f"Error checking/creating decks: {deck_error}")

        # Build notes list
        notes = []
        for card in cards:
            card_front = card.get("front", "")
            card_back = card.get("back", "")

            if not card_front or not card_back:
                notes.append(None)  # Will be skipped
                continue

            card_deck = card.get("deck", deck)
            card_model = card.get("model", model)
            card_tags_str = card.get("tags", tags)
            card_tags = card_tags_str.strip().split() if card_tags_str.strip() else []

            # Apply highlighting
            if card.get("highlight_front"):
                card_front = apply_highlight(card_front, card["highlight_front"], highlight_color)
            if card.get("highlight_back"):
                card_back = apply_highlight(card_back, card["highlight_back"], highlight_color)

            # Attach images if specified
            if card.get("image_url_front"):
                filename = _store_image_from_url(card["image_url_front"])
                card_front = f'{card_front}<br><img src="{filename}">'
            if card.get("image_url_back"):
                filename = _store_image_from_url(card["image_url_back"])
                card_back = f'{card_back}<br><img src="{filename}">'

            note_entry = {
                "deckName": card_deck,
                "modelName": card_model,
                "fields": {"Front": card_front, "Back": card_back},
                "tags": card_tags,
            }
            card_allow_dup = card.get("allow_duplicate", allow_duplicate)
            if card_allow_dup:
                note_entry["options"] = {"allowDuplicate": True}
            notes.append(note_entry)

        # Filter out None entries (invalid cards)
        valid_notes = [n for n in notes if n is not None]
        skipped = len(notes) - len(valid_notes)

        if not valid_notes:
            return {"error": "No valid cards to add (all missing front or back)", "success": False}

        # Batch add
        response = ankiconnect_request("addNotes", {"notes": valid_notes})
        result_ids = response.get('result', [])

        success_count = sum(1 for nid in result_ids if nid is not None)
        fail_count = len(result_ids) - success_count

        return {
            "success": True,
            "total": len(cards),
            "added": success_count,
            "failed": fail_count,
            "skipped": skipped,
            "note_ids": result_ids,
            "message": f"Batch complete: {success_count} added, {fail_count} failed, {skipped} skipped out of {len(cards)} total"
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while batch adding cards"
        logger.exception(f"Error occurred while batch adding Anki cards: {error_msg}")

        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."

        return {"error": error_msg, "success": False}


@mcp.tool()
def get_deck_due_counts(
    decks: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get new/learning/review due counts for Anki decks

    Args:
        decks: List of deck names to check (optional, defaults to all decks)

    Returns:
        Dictionary containing due counts per deck
    """
    try:
        # Get deck list if not specified
        if not decks:
            deck_names_response = ankiconnect_request("deckNames")
            decks = deck_names_response.get('result', [])

        logger.info(f"Getting due counts for {len(decks)} deck(s)")

        # Get stats
        stats_response = ankiconnect_request("getDeckStats", {"decks": decks})
        raw_stats = stats_response.get('result', {})

        deck_stats = {}
        total_due = 0
        for deck_id, stats in raw_stats.items():
            new = stats.get('new_count', 0)
            learn = stats.get('learn_count', 0)
            review = stats.get('review_count', 0)
            due = new + learn + review
            total_due += due

            deck_stats[stats.get('name', deck_id)] = {
                "new": new,
                "learning": learn,
                "review": review,
                "total_due": due,
                "total_in_deck": stats.get('total_in_deck', 0)
            }

        return {
            "deck_stats": deck_stats,
            "deck_count": len(deck_stats),
            "total_due": total_due,
            "message": f"{total_due} card(s) due across {len(deck_stats)} deck(s)"
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while getting due counts"
        logger.exception(f"Error occurred while getting deck due counts: {error_msg}")

        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."

        return {"error": error_msg, "success": False}


@mcp.tool()
def get_anki_note(note_id: int) -> Dict[str, Any]:
    """
    Get the current contents of a single Anki note by ID.

    Returns all field values, tags, model name, and the deck of the first card
    belonging to the note. Useful to verify the state of a note before/after
    an update (e.g. whether highlight spans are present).

    Args:
        note_id: The note ID to fetch

    Returns:
        Dictionary with note_id, model, tags, fields (name -> value), deck
    """
    try:
        notes_response = ankiconnect_request("notesInfo", {"notes": [note_id]})
        existing_notes = notes_response.get('result', [])
        if not existing_notes or not existing_notes[0].get('noteId'):
            return {"error": f"Note with ID {note_id} not found", "success": False}

        note = existing_notes[0]
        fields = {name: data.get('value', '') for name, data in note.get('fields', {}).items()}

        deck_name = None
        try:
            cards_response = ankiconnect_request("findCards", {"query": f"nid:{note_id}"})
            card_ids = cards_response.get('result', [])
            if card_ids:
                cards_info = ankiconnect_request("cardsInfo", {"cards": card_ids[:1]})
                cards = cards_info.get('result', [])
                if cards:
                    deck_name = cards[0].get('deckName')
        except Exception as deck_error:
            logger.warning(f"Could not resolve deck for note {note_id}: {deck_error}")

        return {
            "success": True,
            "note_id": note.get('noteId'),
            "model": note.get('modelName'),
            "tags": note.get('tags', []),
            "fields": fields,
            "deck": deck_name,
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while fetching note"
        logger.exception(f"Error occurred while fetching Anki note: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def check_anki_duplicates(
    cards: List[Dict[str, Any]],
    deck: str = "English",
    model: str = "Basic"
) -> Dict[str, Any]:
    """
    Check whether each card would be considered a duplicate by Anki without adding it.

    Uses AnkiConnect's canAddNotes action. Accepts the same card shape as
    add_anki_cards_batch (front/back required; deck/model/tags optional per card).

    Args:
        cards: List of card dicts with at least "front" and "back"
        deck: Default deck name for cards that don't override it
        model: Default model name for cards that don't override it

    Returns:
        Dictionary with per-card results indicating whether each can be added
    """
    try:
        if not cards:
            return {"error": "At least one card is required", "success": False}

        notes_payload = []
        for card in cards:
            card_front = card.get("front", "")
            card_back = card.get("back", "")
            card_deck = card.get("deck", deck)
            card_model = card.get("model", model)
            card_tags_str = card.get("tags", "")
            card_tags = card_tags_str.strip().split() if card_tags_str.strip() else []
            notes_payload.append({
                "deckName": card_deck,
                "modelName": card_model,
                "fields": {"Front": card_front, "Back": card_back},
                "tags": card_tags,
            })

        response = ankiconnect_request("canAddNotes", {"notes": notes_payload})
        flags = response.get('result', [])

        results = []
        for card, can_add in zip(cards, flags):
            results.append({
                "front": card.get("front", ""),
                "back": card.get("back", ""),
                "can_add": bool(can_add),
            })

        addable = sum(1 for r in results if r["can_add"])
        return {
            "success": True,
            "total": len(results),
            "addable": addable,
            "duplicates": len(results) - addable,
            "results": results,
            "message": f"{addable}/{len(results)} card(s) can be added; {len(results) - addable} would be duplicates",
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while checking duplicates"
        logger.exception(f"Error occurred while checking Anki duplicates: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def create_anki_deck(deck_name: str) -> Dict[str, Any]:
    """
    Create a new Anki deck. Sub-decks use "Parent::Child" syntax.

    AnkiConnect's createDeck is idempotent — calling it for an existing deck
    succeeds without error.

    Args:
        deck_name: Name of the deck to create (e.g. "English::ML")

    Returns:
        Dictionary with the created deck name
    """
    try:
        if not deck_name:
            return {"error": "deck_name is required", "success": False}
        response = ankiconnect_request("createDeck", {"deck": deck_name})
        return {
            "success": True,
            "deck": deck_name,
            "deck_id": response.get('result'),
            "message": f"Deck '{deck_name}' is ready",
        }
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while creating deck"
        logger.exception(f"Error occurred while creating Anki deck: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def get_anki_model_fields(model_name: str) -> Dict[str, Any]:
    """
    Get the field names for an Anki note model (e.g. Basic, Cloze).

    Args:
        model_name: Name of the model/note type

    Returns:
        Dictionary with the list of field names in order
    """
    try:
        if not model_name:
            return {"error": "model_name is required", "success": False}
        response = ankiconnect_request("modelFieldNames", {"modelName": model_name})
        fields = response.get('result', [])
        return {
            "success": True,
            "model": model_name,
            "fields": fields,
            "field_count": len(fields),
        }
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while fetching model fields"
        logger.exception(f"Error occurred while fetching model fields: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def add_anki_tags(note_ids: List[int], tags: str) -> Dict[str, Any]:
    """
    Add tags to one or more notes without touching existing tags.

    Args:
        note_ids: List of note IDs
        tags: Space-separated tags to add

    Returns:
        Dictionary with success status
    """
    try:
        if not note_ids:
            return {"error": "At least one note ID is required", "success": False}
        if not tags or not tags.strip():
            return {"error": "tags is required", "success": False}
        ankiconnect_request("addTags", {"notes": note_ids, "tags": tags.strip()})
        return {
            "success": True,
            "note_ids": note_ids,
            "tags_added": tags.strip().split(),
            "message": f"Added tag(s) to {len(note_ids)} note(s)",
        }
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while adding tags"
        logger.exception(f"Error occurred while adding Anki tags: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def remove_anki_tags(note_ids: List[int], tags: str) -> Dict[str, Any]:
    """
    Remove tags from one or more notes without touching other existing tags.

    Args:
        note_ids: List of note IDs
        tags: Space-separated tags to remove

    Returns:
        Dictionary with success status
    """
    try:
        if not note_ids:
            return {"error": "At least one note ID is required", "success": False}
        if not tags or not tags.strip():
            return {"error": "tags is required", "success": False}
        ankiconnect_request("removeTags", {"notes": note_ids, "tags": tags.strip()})
        return {
            "success": True,
            "note_ids": note_ids,
            "tags_removed": tags.strip().split(),
            "message": f"Removed tag(s) from {len(note_ids)} note(s)",
        }
    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while removing tags"
        logger.exception(f"Error occurred while removing Anki tags: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def move_anki_cards_to_deck(note_ids: List[int], deck: str) -> Dict[str, Any]:
    """
    Move all cards belonging to the given notes into the specified deck.

    Creates the deck if it does not already exist.

    Args:
        note_ids: List of note IDs whose cards should be moved
        deck: Destination deck (sub-decks use "Parent::Child" syntax)

    Returns:
        Dictionary with the count of moved cards
    """
    try:
        if not note_ids:
            return {"error": "At least one note ID is required", "success": False}
        if not deck:
            return {"error": "deck is required", "success": False}

        try:
            deck_names_response = ankiconnect_request("deckNames")
            existing_decks = deck_names_response.get('result', [])
            if deck not in existing_decks:
                logger.info(f"Creating new deck: {deck}")
                ankiconnect_request("createDeck", {"deck": deck})
        except Exception as deck_error:
            logger.warning(f"Error checking/creating deck: {deck_error}")

        nid_query = " OR ".join(f"nid:{nid}" for nid in note_ids)
        cards_response = ankiconnect_request("findCards", {"query": nid_query})
        card_ids = cards_response.get('result', [])

        if not card_ids:
            return {
                "success": True,
                "note_ids": note_ids,
                "moved_cards": 0,
                "deck": deck,
                "message": "No cards found for the given note IDs",
            }

        ankiconnect_request("changeDeck", {"cards": card_ids, "deck": deck})
        return {
            "success": True,
            "note_ids": note_ids,
            "moved_cards": len(card_ids),
            "deck": deck,
            "message": f"Moved {len(card_ids)} card(s) to '{deck}'",
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while moving cards"
        logger.exception(f"Error occurred while moving Anki cards: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def get_due_anki_cards(
    deck: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get the contents of cards that are currently due for review.

    Args:
        deck: Optional deck name to scope to (omit for all decks)
        limit: Maximum number of cards to return (default: 20)

    Returns:
        Dictionary listing due cards with their note fields, deck, interval, and due
    """
    try:
        query = "is:due"
        if deck:
            query = f'"deck:{deck}" is:due'

        find_response = ankiconnect_request("findCards", {"query": query})
        all_card_ids = find_response.get('result', [])
        total_due = len(all_card_ids)

        if total_due == 0:
            return {
                "cards": [],
                "total_due": 0,
                "returned": 0,
                "message": f"No due cards found for query: '{query}'",
            }

        card_ids = all_card_ids[:limit]
        cards_response = ankiconnect_request("cardsInfo", {"cards": card_ids})
        raw_cards = cards_response.get('result', [])

        cards = []
        for card in raw_cards:
            fields = {name: data.get('value', '') for name, data in card.get('fields', {}).items()}
            cards.append({
                "card_id": card.get('cardId'),
                "note_id": card.get('note'),
                "deck": card.get('deckName'),
                "model": card.get('modelName'),
                "fields": fields,
                "interval": card.get('interval'),
                "due": card.get('due'),
                "queue": card.get('queue'),
                "reps": card.get('reps'),
                "lapses": card.get('lapses'),
            })

        return {
            "cards": cards,
            "total_due": total_due,
            "returned": len(cards),
            "message": f"{total_due} due card(s) match; returning {len(cards)}",
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while fetching due cards"
        logger.exception(f"Error occurred while fetching due cards: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def get_anki_card_reviews(note_ids: List[int]) -> Dict[str, Any]:
    """
    Get the review history for cards belonging to the given notes.

    Args:
        note_ids: List of note IDs whose card reviews should be fetched

    Returns:
        Dictionary mapping card_id -> list of review records.
        Each review record is a list:
            [reviewTime, cardId, usn, buttonPressed, newInterval,
             previousInterval, newFactor, reviewDuration, reviewType]
        (See AnkiConnect getReviewsOfCards documentation.)
    """
    try:
        if not note_ids:
            return {"error": "At least one note ID is required", "success": False}

        nid_query = " OR ".join(f"nid:{nid}" for nid in note_ids)
        cards_response = ankiconnect_request("findCards", {"query": nid_query})
        card_ids = cards_response.get('result', [])

        if not card_ids:
            return {
                "success": True,
                "note_ids": note_ids,
                "reviews": {},
                "total_reviews": 0,
                "message": "No cards found for the given note IDs",
            }

        response = ankiconnect_request(
            "getReviewsOfCards",
            {"cards": [str(cid) for cid in card_ids]},
        )
        reviews = response.get('result', {}) or {}

        total = sum(len(v) for v in reviews.values())
        return {
            "success": True,
            "note_ids": note_ids,
            "card_ids": card_ids,
            "reviews": reviews,
            "total_reviews": total,
            "message": f"Fetched {total} review record(s) across {len(card_ids)} card(s)",
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while fetching card reviews"
        logger.exception(f"Error occurred while fetching card reviews: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


@mcp.tool()
def add_image_to_anki_note(
    note_id: int,
    image_url: str,
    field: str = "Back",
    position: str = "append"
) -> Dict[str, Any]:
    """
    Download an image from a URL into Anki's media folder and embed it in a field of an existing note.

    Args:
        note_id: The note ID to attach the image to
        image_url: URL of the image to download
        field: Field name to embed the image into (default: "Back")
        position: "append" (default) or "prepend" - where to place the <img> tag

    Returns:
        Dictionary with the resulting filename and the updated field
    """
    try:
        if not image_url:
            return {"error": "image_url is required", "success": False}
        if position not in ("append", "prepend"):
            return {"error": "position must be 'append' or 'prepend'", "success": False}

        notes_response = ankiconnect_request("notesInfo", {"notes": [note_id]})
        existing_notes = notes_response.get('result', [])
        if not existing_notes or not existing_notes[0].get('noteId'):
            return {"error": f"Note with ID {note_id} not found", "success": False}

        existing_fields = existing_notes[0].get('fields', {})
        if field not in existing_fields:
            return {
                "error": f"Field '{field}' not found on note {note_id}. Available: {list(existing_fields.keys())}",
                "success": False,
            }

        filename = _store_image_from_url(image_url)
        img_tag = f'<img src="{filename}">'
        current = existing_fields[field].get('value', '')
        if position == "append":
            new_value = f'{current}<br>{img_tag}' if current else img_tag
        else:
            new_value = f'{img_tag}<br>{current}' if current else img_tag

        ankiconnect_request(
            "updateNoteFields",
            {"note": {"id": note_id, "fields": {field: new_value}}},
        )

        return {
            "success": True,
            "note_id": note_id,
            "field": field,
            "filename": filename,
            "position": position,
            "message": f"Attached image to '{field}' of note {note_id} as {filename}",
        }

    except Exception as e:
        error_msg = str(e) or "Unknown error occurred while attaching image"
        logger.exception(f"Error occurred while attaching image: {error_msg}")
        if "Failed to connect to AnkiConnect" in error_msg:
            error_msg = "Failed to connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on enabled."
        return {"error": error_msg, "success": False}


def main():
    """Main entry point for the MCP server"""
    try:
        print("Starting MCP server for Anki card creation...", file=sys.stderr)
        mcp.run()
    except Exception as e:
        print(f"Server startup error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
