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


@mcp.tool()
def add_anki_card(
    front: str,
    back: str,
    deck: str = "English",
    model: str = "Basic",
    tags: str = "",
    highlight_front: List[str] = None,
    highlight_back: List[str] = None,
    highlight_color: Dict[str, int] = None
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
        note_params = {
            "note": {
                "deckName": deck,
                "modelName": model,
                "fields": fields,
                "tags": tag_list
            }
        }
        
        response = ankiconnect_request("addNote", note_params)
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
