import os
import json
import time
import requests # Used for both posting (potentially) and insights
import gspread
from google.oauth2.service_account import Credentials
import sys
import traceback # Keep this uncommented for debugging if needed
from flask import Flask, request, jsonify # Ensure Flask, request, jsonify are imported

# --- Your Existing Configuration (and any new ones needed for insights) ---
GOOGLE_CREDENTIALS_JSON_CONTENT = os.environ.get('GOOGLE_CREDENTIALS_JSON_CONTENT')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
READY_TO_POST_WORKSHEET_NAME = os.environ.get('READY_TO_POST_WORKSHEET_NAME', 'Ready_To_Post')
THREADS_API_BASE_URL = os.environ.get('THREADS_API_BASE_URL', 'https://graph.threads.net/v1.0/') # Used by your posting logic
POST_DELAY_SECONDS = int(os.environ.get('POST_DELAY_SECONDS', 30)) # Ensure it's an int

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Your Existing Helper Functions (get_google_sheet_client, get_post_data, update_post_status, etc.) ---
# PASTE ALL YOUR EXISTING HELPER FUNCTIONS HERE (e.g., get_google_sheet_client, get_post_data, update_post_status, make_threads_api_request, create_threads_container, publish_threads_container)
# ... (ensure they are correctly defined) ...

# Example:
def get_google_sheet_client():
    """Authenticates with Google Sheets using service account JSON content from env var."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        print("Attempting to load credentials from environment variable GOOGLE_CREDENTIALS_JSON_CONTENT")
        if not GOOGLE_CREDENTIALS_JSON_CONTENT:
             print("Error: GOOGLE_CREDENTIALS_JSON_CONTENT environment variable is not set in Railway.", file=sys.stderr)
             return None
        try:
            service_account_info = json.loads(GOOGLE_CREDENTIALS_JSON_CONTENT)
            print("Successfully loaded service account info from environment variable.")
        except json.JSONDecodeError as e:
             print(f"Error reading credentials from env var: Could not decode JSON from GOOGLE_CREDENTIALS_JSON_CONTENT. Content might be invalid JSON.", file=sys.stderr)
             traceback.print_exc(file=sys.stderr)
             return None
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        print("Successfully created credentials object from env var.")
        client = gspread.authorize(credentials)
        print(f"Successfully authorized gspread client for sheet: {GOOGLE_SHEET_URL}")
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        print("Successfully opened Google Sheet object.")
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets after loading credentials.", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None

# --- (Paste your other helper functions here too) ---
def get_post_data(sheet, post_id):
    # Your implementation
    pass

def update_post_status(sheet, row_index, status, threads_post_id=None, notes=None):
    # Your implementation
    pass

def make_threads_api_request(endpoint, method='POST', params=None, data=None, headers=None, retries=3, delay=10):
    # Your implementation (if used for posting directly, or adapt for insights if needed)
    # For insights, we'll likely make a direct requests.get() call later in the insights endpoint itself
    pass

def create_threads_container(user_id, access_token, text_content, reply_to_id=None):
    # Your implementation
    pass

def publish_threads_container(user_id, access_token, creation_id):
    # Your implementation
    pass

# --- Your Existing Core Bot Logic Function for Posting ---
def process_post(post_id_to_post, account_name_to_use):
    # PASTE YOUR EXISTING `process_post` FUNCTION LOGIC HERE
    # This function is called by your `/process_post` Flask route.
    print(f"LOG: Simulating `process_post` for Post_ID: {post_id_to_post}, Account: {account_name_to_use}")
    # Replace with your actual logic that uses instagrapi or direct API calls
    # based on the account_name_to_use to fetch its specific credentials
    # (e.g., THREADS_USER_ID_{ACCOUNT_NAME}, THREADS_ACCESS_TOKEN_{ACCOUNT_NAME})
    # from environment variables.
    
    # This is just a placeholder to ensure the structure is complete
    # Your actual function will do the sheet reading, API calls for posting, and sheet updating.
    
    # Example: Fetching credentials (you likely have this or similar)
    # threads_user_id = os.environ.get(f'THREADS_USER_ID_{account_name_to_use.upper()}')
    # threads_access_token = os.environ.get(f'THREADS_ACCESS_TOKEN_{account_name_to_use.upper()}')
    # if not threads_user_id or not threads_access_token:
    #     return {'status': 'failure', 'error_message': f"Credentials not found for account {account_name_to_use}"}

    # ... your posting logic ...

    # Return a dictionary like:
    return {'status': 'success_simulation', 'threads_post_id': 'simulated_id_123'}


# --- Existing Flask Endpoint for Posting ---
@app.route('/process_post', methods=['POST'])
def process_post_endpoint():
    # PASTE YOUR EXISTING `/process_post` FLASK ROUTE LOGIC HERE
    # This typically gets post_id and account_name from request.json,
    # then calls your process_post() function.
    print("LOG: /process_post endpoint called")
    request_data = request.get_json()
    if not request_data or 'post_id' not in request_data or 'account_name' not in request_data:
        return jsonify({'status': 'error', 'message': 'Invalid request data for posting.'}), 400
    
    post_id = request_data['post_id']
    account_name = request_data['account_name']
    
    print(f"LOG: Calling process_post function with Post_ID: {post_id}, Account: {account_name}")
    result = process_post(post_id, account_name) # Call your main posting logic
    print(f"LOG: Returning result for /process_post for Post_ID {post_id}: {result}")
    return jsonify(result), 200


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# | NEW Flask Endpoint for Getting Thread Insights                    |
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@app.route('/get_thread_insights', methods=['POST'])
def get_thread_insights_route():
    print("LOG: Received request at /get_thread_insights") 

    try:
        n8n_data = request.get_json()
        if not n8n_data:
            print("LOG: No JSON data received from N8N for insights")
            return jsonify({"error": "No JSON data received from N8N"}), 400
        print(f"LOG: Received data from N8N for insights: {n8n_data}")
    except Exception as e:
        print(f"ERROR: Error getting JSON from insights request: {e}")
        return jsonify({"error": "Invalid JSON format in insights request"}), 400

    threads_post_id = n8n_data.get('threads_post_id')
    account_name_from_n8n = n8n_data.get('account_name') 

    if not threads_post_id or not account_name_from_n8n:
        print("LOG: Missing threads_post_id or account_name in insights request")
        return jsonify({"error": "Missing 'threads_post_id' or 'account_name' in N8N data for insights"}), 400

    access_token = None
    # **IMPORTANT**: Use the exact environment variable name you have set on Railway
    # for TESTACCOUNT's insights-capable token.
    # If your env var for TESTACCOUNT is THREADS_ACCESS_TOKEN_TESTACCOUNT, use that.
    # If it's just TESTACCOUNT_TOKEN, use that.
    # For now, this logic specifically handles "TESTACCOUNT".
    # You will need to add similar `elif` blocks for "ACC1", "ACC2", etc.,
    # once you have their tokens and corresponding environment variable names.
    
    token_env_var_name_used = None # To store which env var name was attempted

    if account_name_from_n8n.upper() == "TESTACCOUNT":
        # !!! REPLACE 'THREADS_ACCESS_TOKEN_TESTACCOUNT' WITH YOUR ACTUAL ENV VAR NAME FOR TESTACCOUNT !!!
        token_env_var_name_used = 'THREADS_ACCESS_TOKEN_TESTACCOUNT' 
        access_token = os.getenv(token_env_var_name_used)
    # Example for ACC1 (you'll add these later):
    # elif account_name_from_n8n.upper() == "ACC1":
    #     token_env_var_name_used = 'THREADS_ACCESS_TOKEN_ACC1' # Or whatever you name it
    #     access_token = os.getenv(token_env_var_name_used)
    else:
        # Fallback for other account names, construct dynamically
        # This assumes your env vars for ACC1-ACC10 will be THREADS_ACCESS_TOKEN_ACC1, THREADS_ACCESS_TOKEN_ACC2 etc.
        token_env_var_name_used = f"THREADS_ACCESS_TOKEN_{account_name_from_n8n.upper()}"
        access_token = os.getenv(token_env_var_name_used)

    print(f"LOG: Attempting to retrieve token for '{account_name_from_n8n}' using env var name: '{token_env_var_name_used}'")

    if not access_token:
        print(f"CRITICAL ERROR: Token NOT FOUND for account '{account_name_from_n8n}' using env var '{token_env_var_name_used}'. Please check Railway environment variables.")
        return jsonify({"error": f"Server configuration error: Token for account '{account_name_from_n8n}' not set up. Expected env var: {token_env_var_name_used}"}), 500
    else:
        print(f"LOG: Successfully retrieved token (token length: {len(access_token)}).")

    # --- STAGE 1: Placeholder response - just send back what you received to confirm ---
    # --- We will add the actual Threads API call logic here in the next step ---
    response_data = {
        "message": "Railway endpoint /get_thread_insights reached successfully! (Stage 1 Test - Token Retrieval)",
        "received_threads_post_id": threads_post_id,
        "received_account_name": account_name_from_n8n,
        "attempted_token_env_var": token_env_var_name_used,
        "token_found_and_loaded": True,
        "next_step": "Implement actual Threads Insights API call using this token."
    }
    print(f"LOG: Sending placeholder response back to N8N: {response_data}")
    return jsonify(response_data), 200


# --- Main Execution (Starts Flask Server) ---
if __name__ == "__main__":
    print("Starting Flask web server...")
    port = int(os.environ.get("PORT", 8080)) # Default to 8080 for local, Railway sets PORT
    app.run(debug=False, host='0.0.0.0', port=port) # debug=False for production on Railway
