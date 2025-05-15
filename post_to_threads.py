import os
import json
import time
import requests # For making API calls
import gspread
from google.oauth2.service_account import Credentials
import sys
import traceback
from flask import Flask, request, jsonify

# --- Configuration ---
GOOGLE_CREDENTIALS_JSON_CONTENT = os.environ.get('GOOGLE_CREDENTIALS_JSON_CONTENT')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
READY_TO_POST_WORKSHEET_NAME = os.environ.get('READY_TO_POST_WORKSHEET_NAME', 'Ready_To_Post')
# THREADS_API_BASE_URL is used for posting, insights uses a different base for graph.threads.net
# POST_DELAY_SECONDS for your posting logic if it's still relevant there.
POST_DELAY_SECONDS = int(os.environ.get('POST_DELAY_SECONDS', 30))


# --- Initialize Flask App ---
app = Flask(__name__)

# --- Helper Functions ---
#### YOUR EXISTING CODE START ####
# PASTE ALL YOUR EXISTING HELPER FUNCTIONS HERE
# (e.g., get_google_sheet_client, get_post_data, update_post_status, 
# make_threads_api_request for posting if you used it, 
# create_threads_container, publish_threads_container)

# Example get_google_sheet_client (ensure yours is complete)
def get_google_sheet_client():
    """Authenticates with Google Sheets using service account JSON content from env var."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        # print("Attempting to load credentials from GOOGLE_CREDENTIALS_JSON_CONTENT") # Debug
        if not GOOGLE_CREDENTIALS_JSON_CONTENT:
             print("Error: GOOGLE_CREDENTIALS_JSON_CONTENT environment variable is not set.", file=sys.stderr)
             return None
        try:
            service_account_info = json.loads(GOOGLE_CREDENTIALS_JSON_CONTENT)
        except json.JSONDecodeError as e:
             print(f"Error decoding JSON from GOOGLE_CREDENTIALS_JSON_CONTENT: {e}", file=sys.stderr)
             return None
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        # print("Successfully connected to Google Sheet.") # Debug
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None

# --- (Ensure all your other original helper functions are pasted here) ---
def get_post_data(sheet, post_id):
    # YOUR IMPLEMENTATION for get_post_data
    # This function should read the "Ready_To_Post" sheet, find the row by post_id,
    # extract Block_1_Content, Block_2_Content, etc.
    # Return post_data (dict) and row_index.
    # Example:
    # worksheet = sheet.worksheet(READY_TO_POST_WORKSHEET_NAME)
    # ... find row, get values, create dict ...
    # return post_data_dict, cell.row
    print(f"Placeholder: get_post_data for {post_id}")
    return {"Block_1_Content": "Test Block 1", "Status": "Ready"}, 2 # Placeholder

def update_post_status(sheet, row_index, status, threads_post_id=None, notes=None):
    # YOUR IMPLEMENTATION for update_post_status
    # This function updates the Google Sheet row with the new status, ID, notes.
    print(f"Placeholder: update_post_status for row {row_index} to {status}")
    pass

#### YOUR EXISTING CODE END ####


# --- Core Bot Logic Function for Posting ---
#### YOUR EXISTING CODE START ####
def process_post(post_id_to_post, account_name_to_use):
    # PASTE YOUR EXISTING `process_post` FUNCTION LOGIC HERE
    # This function is called by your `/process_post` Flask route.
    # It should use instagrapi or direct API calls for posting,
    # retrieving credentials like THREADS_USER_ID_{ACCOUNT_NAME} 
    # and THREADS_ACCESS_TOKEN_{ACCOUNT_NAME} from environment variables.
    print(f"LOG: `process_post` called for Post_ID: {post_id_to_post}, Account: {account_name_to_use}")
    
    # Example: Fetching posting credentials
    # threads_user_id_for_posting = os.environ.get(f'THREADS_USER_ID_{account_name_to_use.upper()}')
    # threads_access_token_for_posting = os.environ.get(f'THREADS_ACCESS_TOKEN_{account_name_to_use.upper()}') # This might be the same token as for insights or a different one
    
    # if not threads_user_id_for_posting or not threads_access_token_for_posting:
    #     return {'status': 'failure', 'error_message': f"Posting credentials not found for account {account_name_to_use}"}

    # ... your actual sheet reading, instagrapi/API posting logic ...

    # For now, returning a simulation
    print(f"LOG: Simulating post for post_id: {post_id_to_post} to account: {account_name_to_use}")
    return {'status': 'success_simulation', 'threads_post_id': 'simulated_threads_id_12345'}
#### YOUR EXISTING CODE END ####


# --- Existing Flask Endpoint for Posting ---
@app.route('/process_post', methods=['POST'])
def process_post_endpoint():
    #### YOUR EXISTING CODE START ####
    # PASTE YOUR EXISTING `/process_post` FLASK ROUTE LOGIC HERE
    # This typically gets post_id and account_name from request.json,
    # then calls your process_post() function.
    print("LOG: /process_post endpoint called")
    request_data = request.get_json()
    if not request_data or 'post_id' not in request_data or 'account_name' not in request_data:
        return jsonify({'status': 'error', 'message': 'Invalid request data for posting. Requires post_id and account_name.'}), 400
    
    post_id = request_data['post_id']
    account_name = request_data['account_name']
    
    print(f"LOG: Calling process_post function with Post_ID: {post_id}, Account: {account_name}")
    result = process_post(post_id, account_name) 
    print(f"LOG: Returning result for /process_post for Post_ID {post_id}: {result}")
    return jsonify(result), 200
    #### YOUR EXISTING CODE END ####


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
    # **IMPORTANT**: This logic assumes your environment variable for TESTACCOUNT's
    # insights-capable token is named THREADS_ACCESS_TOKEN_TESTACCOUNT.
    # Adjust the string if your actual environment variable name is different.
    token_env_var_name_used = None 

    if account_name_from_n8n.upper() == "TESTACCOUNT":
        token_env_var_name_used = 'THREADS_ACCESS_TOKEN_TESTACCOUNT' # Ensure this exact name is in Railway
        access_token = os.getenv(token_env_var_name_used)
    # Add elif blocks here later for "ACC1", "ACC2", etc., when you have their tokens and env vars
    # For example:
    # elif account_name_from_n8n.upper() == "ACC1":
    #     token_env_var_name_used = 'THREADS_ACCESS_TOKEN_ACC1' 
    #     access_token = os.getenv(token_env_var_name_used)
    else:
        # Fallback or error for unconfigured accounts
        token_env_var_name_used = f"THREADS_ACCESS_TOKEN_{account_name_from_n8n.upper()}" # Attempt dynamic
        access_token = os.getenv(token_env_var_name_used)
        if not access_token: # If dynamic attempt fails and it's not TESTACCOUNT
             print(f"LOG: Account name '{account_name_from_n8n}' not explicitly configured and dynamic token retrieval failed.")
             return jsonify({"error": f"Account '{account_name_from_n8n}' not configured for insights token."}), 400

    print(f"LOG: Attempting to retrieve token for '{account_name_from_n8n}' using env var name: '{token_env_var_name_used}'")

    if not access_token:
        print(f"CRITICAL ERROR: Token NOT FOUND for account '{account_name_from_n8n}' using env var '{token_env_var_name_used}'. Check Railway env vars.")
        return jsonify({"error": f"Server configuration error: Token for '{account_name_from_n8n}' not found. Expected env var: {token_env_var_name_used}"}), 500
    else:
        print(f"LOG: Successfully retrieved token (token length: {len(access_token)}).")

    # --- Actual Threads Insights API Call ---
    metrics_list = "likes,replies,reposts,quotes,shares,views" 
    insights_api_url = f"https://graph.threads.net/v1.0/{threads_post_id}/insights"
    
    # For GET requests with parameters, use the 'params' argument in requests.get()
    api_params = {
        "metric": metrics_list,
        "access_token": access_token  # The token for the specific user whose media it is
    }
    
    print(f"LOG: Calling Threads Insights API: GET {insights_api_url} for account {account_name_from_n8n}")

    try:
        response = requests.get(insights_api_url, params=api_params, timeout=30) # 30-second timeout
        print(f"LOG: Threads API Response Status Code: {response.status_code}")
        print(f"LOG: Threads API Response Content: {response.text[:500]}...") # Log beginning of response text
        response.raise_for_status()  # Raise an HTTPError for bad responses (4XX or 5XX)
        
        threads_api_response_data = response.json()
        print(f"LOG: Successfully received and parsed JSON from Threads Insights API: {threads_api_response_data}")
        
        extracted_metrics = {}
        if 'data' in threads_api_response_data and isinstance(threads_api_response_data['data'], list):
            for metric_entry in threads_api_response_data['data']:
                metric_name = metric_entry.get('name')
                # Media insights have values as an array of objects, each with a 'value'
                if metric_entry.get('values') and isinstance(metric_entry['values'], list) and len(metric_entry['values']) > 0:
                    metric_value = metric_entry['values'][0].get('value')
                    if metric_name and metric_value is not None:
                        extracted_metrics[metric_name] = metric_value
                # This 'total_value' structure is more for User Insights, but good to have a robust parser
                elif 'total_value' in metric_entry and isinstance(metric_entry['total_value'], dict):
                    metric_value = metric_entry['total_value'].get('value')
                    if metric_name and metric_value is not None:
                        extracted_metrics[metric_name] = metric_value
        
        if not extracted_metrics:
            print("LOG: No specific metrics parsed from Threads API response. Might be empty or unexpected format.")
            return jsonify({
                "warning": "No specific metrics parsed from Threads API response.",
                "raw_threads_api_response": threads_api_response_data  # Send raw response for debugging
            }), 200 
            
        print(f"LOG: Sending extracted insights back to N8N: {extracted_metrics}")
        return jsonify(extracted_metrics), 200

    except requests.exceptions.HTTPError as http_err:
        error_content = "No response content"
        if http_err.response is not None:
            error_content = http_err.response.text
        error_details = f"HTTP error occurred calling Threads API: {http_err} - Response: {error_content}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to fetch from Threads API (HTTP Error)", "details": str(http_err), "response_text": error_content}), getattr(http_err.response, 'status_code', 500)
    except requests.exceptions.RequestException as req_err:
        error_details = f"Request error occurred calling Threads API: {req_err}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to fetch from Threads API (Request Error)", "details": str(req_err)}), 500
    except ValueError as json_err: 
        response_text_for_error = ""
        if 'response' in locals() and response is not None:
            response_text_for_error = response.text
        error_details = f"JSON decode error from Threads API response: {json_err} - Response: {response_text_for_error}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to parse Threads API response", "details": str(json_err), "response_text": response_text_for_error}), 500
    except Exception as e:
        error_details = f"An unexpected error occurred in /get_thread_insights: {e}"
        print(f"ERROR: {error_details}")
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": "An internal server error occurred in insights endpoint", "details": str(e)}), 500


# --- Main Execution (Starts Flask Server) ---
if __name__ == "__main__":
    print("Starting Flask web server to listen for N8N requests...")
    port = int(os.environ.get("PORT", 8080)) 
    app.run(debug=False, host='0.0.0.0', port=port) # Run on 0.0.0.0 to be accessible in Railway
