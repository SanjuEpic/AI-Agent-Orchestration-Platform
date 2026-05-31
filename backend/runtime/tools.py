import os
import math
import datetime
import json
import httpx
from typing import Optional
from bs4 import BeautifulSoup

# Define a local sandbox folder in the workspace root
SANDBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sandbox")

# Offline mock results for deterministic local testing
MOCK_SEARCH_RESULTS = {
    "rome weather": "Rome, Italy: Currently 22°C (72°F), Clear Skies and Sunny. Wind 8 km/h. 0% chance of rain.",
    "rome attractions": "1. Colosseum (Ancient Roman amphitheater - note: box office closed Tuesdays for construction). 2. Roman Forum (Outdoor ancient ruins). 3. Trevi Fountain (Baroque marble fountain).",
    "acme corp": "Acme Corp is a mid-sized cloud storage enterprise. CEO: John Acme. CTO: Sarah Jenkins. Offices: New York, Seattle.",
    "weather in paris": "Paris, France: 14°C (57°F), Overcast with Light Drizzle. Wind 12 km/h. 75% chance of rain.",
    "paris attractions": "1. Eiffel Tower (historic wrought-iron lattice tower). 2. Louvre Museum (famous art museum). 3. Notre-Dame Cathedral.",
    "lead info": "Acme Corp is evaluating purchases of 500+ cloud seats. High-value target."
}

def _execute_ddg_search(query: str) -> str:
    """Helper function to execute standard DuckDuckGo search."""
    import urllib.parse
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    try:
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return f"[SEARCH ERROR] Received HTTP {response.status_code} from search engine."
            
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("div", class_="result")
        
        items = []
        for art in articles:
            title_a = art.find("a", class_="result__a")
            snippet_div = art.find("a", class_="result__snippet") or art.find("div", class_="result__snippet")
            
            if title_a:
                href = title_a.get("href", "")
                # Skip sponsored/ad links
                if "y.js" in href or "duckduckgo.com/y.js" in href:
                    continue
                    
                title = title_a.get_text(strip=True)
                
                # Unquote the DDG redirect URL to get the direct organic link
                if "uddg=" in href:
                    parsed_href = urllib.parse.urlparse(href)
                    queries = urllib.parse.parse_qs(parsed_href.query)
                    href = queries.get("uddg", [href])[0]
                
                snippet = snippet_div.get_text(strip=True) if snippet_div else ""
                items.append(f"Title: {title}\nURL: {href}\nSnippet: {snippet}")
                if len(items) >= 3:
                    break
        
        if items:
            return "\n\n".join(items)
        return f"No organic search results found for: {query}"
    except Exception as e:
        return f"[SEARCH ERROR / OFFLINE FALLBACK] Could not execute live search. Query: '{query}'. Error: {str(e)}"

def web_search(query: str) -> str:
    """Search the web for info using DuckDuckGo with local mock fallbacks for offline reliability.
    Automatically enriches the query with the current month/year when seeking recent or temporal info."""
    query_lower = query.lower().strip()
    # Check mock fallbacks first for instant testing
    for key, val in MOCK_SEARCH_RESULTS.items():
        if key in query_lower or query_lower in key:
            return f"[LOCAL MOCK SEARCH RESULT FOR '{query}']:\n{val}"
            
    import re
    
    # Auto-enrich query with current year/month if looking for news or recent info
    enriched_query = query
    recent_keywords = ["latest", "recent", "news", "current", "update", "today", "yesterday", "this week", "this month", "this year", "now", "viral"]
    if any(kw in query_lower for kw in recent_keywords):
        if not re.search(r'\b(202\d)\b', query_lower):
            now = datetime.datetime.now()
            current_month_year = now.strftime('%B %Y')
            enriched_query = f"{query} {current_month_year}"

    # Try searching with the enriched query first
    result = _execute_ddg_search(enriched_query)
    if ("No organic search results found" in result or "[SEARCH ERROR]" in result) and enriched_query != query:
        # Fallback to the original query if the month/year was too specific or failed
        result = _execute_ddg_search(query)
        
    return result

def web_scrape(url: str) -> str:
    """Fetch a web page and parse its text, returning a summary of the first 2000 characters."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return f"Error: Received HTTP {response.status_code} from {url}"
            
        soup = BeautifulSoup(response.text, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator="\n")
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = "\n".join(chunk for chunk in chunks if chunk)
        
        return f"Content of {url} (truncated to 2000 chars):\n\n" + clean_text[:2000]
    except Exception as e:
        return f"Scraping failed for {url}. Error: {str(e)}"

def calculator(expression: str) -> str:
    """Safely calculate mathematical equations locally using a controlled evaluation sandbox."""
    import ast
    
    # Only allow numeric literals and basic arithmetic operators
    allowed_chars = set("0123456789+-*/(). \t")
    clean_expr = "".join(c for c in expression if c in allowed_chars)
    if not clean_expr:
        return "Error: Empty or invalid mathematical expression."
        
    try:
        # Parse the expression into an AST and validate it contains only safe node types
        tree = ast.parse(clean_expr, mode='eval')
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num,
                                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                                     ast.FloorDiv, ast.USub, ast.UAdd)):
                return f"Error: Unsupported operation in expression."
        
        # Compile and evaluate the validated AST (no builtins, no names)
        code = compile(tree, "<calculator>", "eval")
        result = eval(code, {"__builtins__": {}}, {})
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation failed: {str(e)}"

def get_datetime(dummy: Optional[str] = None) -> str:
    """Get current local datetime and timezone info for agent time-awareness."""
    now = datetime.datetime.now()
    return f"Current Local Datetime: {now.strftime('%Y-%m-%d %H:%M:%S')} (ISO: {now.isoformat()})"

def workspace_sandbox(args_json: str) -> str:
    """Read or write text files within a sandboxed project workspace folder.
    
    Expects a JSON string with keys: action (read|write), filename, and optionally content (for write).
    Example: {"action": "write", "filename": "notes.txt", "content": "Hello world"}
    Example: {"action": "read", "filename": "notes.txt"}
    """
    try:
        params = json.loads(args_json) if isinstance(args_json, str) else args_json
    except json.JSONDecodeError:
        return "Error: Invalid JSON argument. Expected: {\"action\": \"read|write\", \"filename\": \"...\", \"content\": \"...\"}"
    
    action = params.get("action", "")
    filename = params.get("filename", "")
    content = params.get("content")
    
    if not filename:
        return "Error: Missing 'filename' parameter."
    
    if not os.path.exists(SANDBOX_DIR):
        os.makedirs(SANDBOX_DIR)
        
    # Prevent directory traversal attacks
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(SANDBOX_DIR, safe_filename)
    
    try:
        if action.lower() == "write":
            if content is None:
                return "Error: Missing 'content' body for write operation."
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote file: {safe_filename} inside sandbox directory."
            
        elif action.lower() == "read":
            if not os.path.exists(file_path):
                return f"Error: File '{safe_filename}' does not exist inside sandbox."
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
            return f"Content of '{safe_filename}':\n\n{data}"
            
        else:
            return f"Error: Unknown action '{action}'. Use 'read' or 'write'."
    except Exception as e:
        return f"Sandbox file operation failed: {str(e)}"

def http_request(args_json: str) -> str:
    """Make HTTP requests to external webhooks or APIs.
    
    Expects a JSON string with keys: method (GET|POST|PUT), url, and optionally headers, body.
    Example: {"method": "GET", "url": "https://api.example.com/data"}
    Example: {"method": "POST", "url": "https://hooks.slack.com/...", "body": "{\"text\": \"Hello\"}"}
    """
    try:
        params = json.loads(args_json) if isinstance(args_json, str) else args_json
    except json.JSONDecodeError:
        return "Error: Invalid JSON argument. Expected: {\"method\": \"GET\", \"url\": \"...\", \"body\": \"...\"}"
    
    method = params.get("method", "GET")
    url = params.get("url", "")
    headers_raw = params.get("headers")
    body = params.get("body")
    
    if not url:
        return "Error: Missing 'url' parameter."
    
    try:
        headers = {}
        if headers_raw:
            headers = json.loads(headers_raw) if isinstance(headers_raw, str) else headers_raw
            
        # Add basic client identifier
        if "User-Agent" not in headers:
            headers["User-Agent"] = "AI-Agent-Orchestrator/1.0"
            
        method_upper = method.upper()
        if method_upper == "GET":
            response = httpx.get(url, headers=headers, timeout=10.0)
        elif method_upper in ("POST", "PUT"):
            # Determine correct content encoding
            data_content = body
            if body and isinstance(body, str) and body.startswith("{") and body.endswith("}"):
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            response = httpx.request(method_upper, url, headers=headers, content=data_content, timeout=10.0)
        else:
            return f"Error: Unsupported HTTP method '{method}'"
            
        return f"HTTP {response.status_code}\nHeaders: {dict(response.headers)}\nResponse:\n{response.text[:1500]}"
    except Exception as e:
        return f"HTTP Request to {url} failed: {str(e)}"

def check_weather(location: str) -> str:
    """Fetch current real-time weather conditions for a location name using Open-Meteo's free APIs (no key required)."""
    location = location.strip()
    if not location:
        return "Error: Location parameter is empty."
        
    try:
        # Step 1: Geocode city name to lat/lon
        import urllib.parse
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        headers = {"User-Agent": "AI-Agent-Orchestrator/1.0"}
        
        import time
        res_geo = None
        for attempt in range(3):
            try:
                res_geo = httpx.get(geocode_url, headers=headers, timeout=10.0)
                if res_geo.status_code == 200:
                    break
                elif res_geo.status_code in (500, 502, 503, 504):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                else:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
        
        if not res_geo or res_geo.status_code != 200:
            status_code = res_geo.status_code if res_geo else "Unknown"
            return f"Geocoding failed for '{location}': HTTP {status_code}"
            
        geo_data = res_geo.json()
        results = geo_data.get("results")
        if not results:
            return f"Error: Could not find coordinates for location '{location}'."
            
        loc_data = results[0]
        lat = loc_data["latitude"]
        lon = loc_data["longitude"]
        name = loc_data.get("name", location)
        country = loc_data.get("country", "")
        
        # Step 2: Fetch current weather
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m&timezone=auto"
        
        res_weath = None
        for attempt in range(3):
            try:
                res_weath = httpx.get(weather_url, headers=headers, timeout=10.0)
                if res_weath.status_code == 200:
                    break
                elif res_weath.status_code in (500, 502, 503, 504):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                else:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
        
        if not res_weath or res_weath.status_code != 200:
            status_code = res_weath.status_code if res_weath else "Unknown"
            return f"Weather lookup failed for '{location}' (Lat: {lat}, Lon: {lon}): HTTP {status_code}"
            
        weath_data = res_weath.json()
        current = weath_data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        apparent = current.get("apparent_temperature", "N/A")
        wind = current.get("wind_speed_10m", "N/A")
        units = weath_data.get("current_units", {})
        
        temp_unit = units.get("temperature_2m", "°C")
        humidity_unit = units.get("relative_humidity_2m", "%")
        apparent_unit = units.get("apparent_temperature", "°C")
        wind_unit = units.get("wind_speed_10m", "km/h")
        
        return (
            f"Current Weather in {name}, {country}:\n"
            f"- Temperature: {temp}{temp_unit} (Feels like: {apparent}{apparent_unit})\n"
            f"- Humidity: {humidity}{humidity_unit}\n"
            f"- Wind Speed: {wind} {wind_unit}"
        )
    except Exception as e:
        return f"Failed to check weather for '{location}': {str(e)}"

def combined_web_search(query_or_url: str) -> str:
    """Search the web or scrape a specific URL.
    If the argument is a URL starting with http:// or https://, it scrapes the page clean text.
    Otherwise, it searches DuckDuckGo for the query and returns top organic snippets.
    """
    val = query_or_url.strip()
    if val.startswith("http://") or val.startswith("https://"):
        return web_scrape(val)
    return web_search(val)

# Tool descriptions used by the LLM prompt to understand what each tool does
TOOLS_DESCRIPTIONS = {
    "search": "Search the web or scrape a URL. If the argument is a URL starting with http:// or https://, it fetches and scrapes the page content. Otherwise, it searches DuckDuckGo for the query and returns snippets and links. Example: TOOL_CALL: {\"tool\": \"search\", \"argument\": \"https://example.com\"} or TOOL_CALL: {\"tool\": \"search\", \"argument\": \"latest AI news\"}",
    "calculator": "Evaluate a mathematical expression. Argument: the math expression string. Example: TOOL_CALL: {\"tool\": \"calculator\", \"argument\": \"(42 * 3) + 17\"}",
    "sandbox_io": "Read or write text files in the workspace sandbox folder. Argument: a JSON object with action, filename, and optionally content. Example: TOOL_CALL: {\"tool\": \"sandbox_io\", \"argument\": \"{\\\"action\\\": \\\"write\\\", \\\"filename\\\": \\\"notes.txt\\\", \\\"content\\\": \\\"Hello\\\"}\"}",
    "weather": "Fetch current real-time weather conditions for a city/location. Argument: the city/location name string. Example: TOOL_CALL: {\"tool\": \"weather\", \"argument\": \"Rome\"}"
}

# Unified mapping dictionary for runtime execution
TOOLS_REGISTRY = {
    "search": combined_web_search,
    "calculator": calculator,
    "sandbox_io": workspace_sandbox,
    "weather": check_weather
}
