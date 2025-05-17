import os
import json
import time
import requests
import gspread
from google.oauth2.service_account import Credentials
import sys
import traceback # Keep this uncommented for debugging if needed
from flask import Flask, request, jsonify
from datetime import datetime # --- NEW --- Import datetime

# --- Configuration ---
GOOGLE_CREDENTIALS_JSON_CONTENT = os.environ.get('GOOGLE_CREDENTIALS_JSON_CONTENT')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
READY_TO_POST_WORKSHEET_NAME = os.environ.get('READY_TO_POST_WORKSHEET_NAME', 'Ready_To_Post')
POSTED_LOGS_WORKSHEET_NAME = 'Posted_Logs' # --- NEW --- Worksheet name for posted logs
THREADS_API_BASE_URL = os.environ.get('THREADS_API_BASE_URL', 'https://graph.threads.net/v1.0/') # Used by your posting logic
POST_DELAY_SECONDS = int(os.environ.get('POST_DELAY_SECONDS', 30))


# --- Initialize Flask App ---
app = Flask(__name__)

# --- Helper Functions ---
def get_google_sheet_client():
    """Authenticates with Google Sheets using service account JSON content from env var."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        print("LOG: Attempting to load credentials from GOOGLE_CREDENTIALS_JSON_CONTENT")
        if not GOOGLE_CREDENTIALS_JSON_CONTENT:
             print("ERROR: GOOGLE_CREDENTIALS_JSON_CONTENT environment variable is not set in Railway.", file=sys.stderr)
             return None
        try:
            service_account_info = json.loads(GOOGLE_CREDENTIALS_JSON_CONTENT)
            print("LOG: Successfully loaded service account info from environment variable.")
        except json.JSONDecodeError as e:
             print(f"ERROR: Could not decode JSON from GOOGLE_CREDENTIALS_JSON_CONTENT: {e}", file=sys.stderr)
             traceback.print_exc(file=sys.stderr)
             return None
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        print("LOG: Successfully created credentials object.")
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        print(f"LOG: Successfully authorized and opened Google Sheet: {GOOGLE_SHEET_URL}")
        return sheet
    except Exception as e:
        print(f"ERROR: Error connecting to Google Sheets: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None

def get_post_data(sheet, post_id):
    """Reads a specific row from the Ready_To_Post sheet by Post_ID."""
    try:
        print(f"LOG: Attempting to access worksheet: {READY_TO_POST_WORKSHEET_NAME}")
        worksheet = sheet.worksheet(READY_TO_POST_WORKSHEET_NAME)
        print(f"LOG: Successfully accessed worksheet: {READY_TO_POST_WORKSHEET_NAME}")

        headers = worksheet.row_values(1)
        print(f"LOG: Sheet headers: {headers}")

        if 'Post_ID' not in headers:
            print(f"ERROR: 'Post_ID' header not found in worksheet '{READY_TO_POST_WORKSHEET_NAME}'. Available headers: {headers}", file=sys.stderr)
            return None, None

        post_id_col_index = headers.index('Post_ID') + 1
        print(f"LOG: Attempting to find Post_ID '{post_id}' in column {post_id_col_index}...")

        try:
            cell = worksheet.find(str(post_id), in_column=post_id_col_index)
        except gspread.exceptions.CellNotFound:
            cell = None # Handle gracefully if find raises an exception instead of returning None

        if not cell:
            print(f"ERROR: Post_ID '{post_id}' not found in column 'Post_ID' of {READY_TO_POST_WORKSHEET_NAME}.", file=sys.stderr)
            return None, None

        print(f"LOG: Found Post_ID '{post_id}' at row {cell.row}.")
        row_values = worksheet.row_values(cell.row)
        post_data = dict(zip(headers, row_values))

        if post_data.get('Status') != 'Ready':
            print(f"WARNING: Post_ID '{post_id}' status is '{post_data.get('Status')}', not 'Ready'. Skipping.", file=sys.stderr)
            return None, cell.row
        
        print(f"LOG: Post {post_id} is Ready. Data loaded: {post_data}")
        return post_data, cell.row
    except gspread.exceptions.WorksheetNotFound:
        print(f"ERROR: Worksheet '{READY_TO_POST_WORKSHEET_NAME}' not found.", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"ERROR: Exception in get_post_data for Post_ID {post_id}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None, None

def update_post_status(sheet, row_index, status, threads_post_id=None, notes=None):
    """Updates the Status, Threads_Post_ID, and Notes columns for a row in Ready_To_Post."""
    try:
        print(f"LOG: Attempting to update row {row_index} in {READY_TO_POST_WORKSHEET_NAME} to Status: '{status}'")
        worksheet = sheet.worksheet(READY_TO_POST_WORKSHEET_NAME)
        header_row = worksheet.row_values(1)

        update_cells_list = []
        if 'Status' in header_row:
            status_col = header_row.index('Status') + 1
            update_cells_list.append(gspread.Cell(row_index, status_col, status))
        else:
            print(f"WARNING: 'Status' column not found in {READY_TO_POST_WORKSHEET_NAME} for update.", file=sys.stderr)

        if threads_post_id and 'Threads_Post_ID' in header_row:
            threads_id_col = header_row.index('Threads_Post_ID') + 1
            update_cells_list.append(gspread.Cell(row_index, threads_id_col, str(threads_post_id)))
        elif threads_post_id:
             print(f"WARNING: 'Threads_Post_ID' column not found in {READY_TO_POST_WORKSHEET_NAME} for update.", file=sys.stderr)

        if notes and 'Notes' in header_row:
            notes_col = header_row.index('Notes') + 1
            update_cells_list.append(gspread.Cell(row_index, notes_col, notes))
        elif notes:
            print(f"WARNING: 'Notes' column not found in {READY_TO_POST_WORKSHEET_NAME} for update.", file=sys.stderr)

        if update_cells_list:
            worksheet.update_cells(update_cells_list)
            print(f"LOG: Successfully updated {READY_TO_POST_WORKSHEET_NAME} for row {row_index}.")
        else:
            print(f"LOG: No valid columns found or values provided to update in {READY_TO_POST_WORKSHEET_NAME} for row {row_index}.")

    except Exception as e:
        print(f"ERROR: Exception in update_post_status for row {row_index}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

# --- NEW --- Function to log to "Posted_Logs" sheet
def log_to_posted_sheet(sheet, original_post_id, threads_post_id, account_name, timestamp_posted):
    """Appends a new row to the Posted_Logs sheet."""
    try:
        print(f"LOG: Attempting to log to worksheet: {POSTED_LOGS_WORKSHEET_NAME}")
        worksheet = sheet.worksheet(POSTED_LOGS_WORKSHEET_NAME)
        print(f"LOG: Successfully accessed worksheet: {POSTED_LOGS_WORKSHEET_NAME}")

        # This order must match your "Posted_Logs" sheet columns:
        # Original_Post_ID, Threads_Post_ID, Account, Timestamp_Posted, Insights_Last_Checked, Views, Likes, Replies
        row_to_append = [
            original_post_id,     # e.g., TEST-001
            str(threads_post_id), # The ID from Threads API
            account_name,
            timestamp_posted,     # ISO format string
            '',                   # Insights_Last_Checked (initially blank)
            '',                   # Views (initially blank)
            '',                   # Likes (initially blank)
            ''                    # Replies (initially blank)
            # Add more empty strings if you have more metric columns in "Posted_Logs"
        ]
        
        worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        print(f"LOG: Successfully appended to {POSTED_LOGS_WORKSHEET_NAME} for Original_Post_ID: {original_post_id}, Threads_Post_ID: {threads_post_id}")
        return True
    except gspread.exceptions.WorksheetNotFound:
        print(f"ERROR: Worksheet '{POSTED_LOGS_WORKSHEET_NAME}' not found. Please ensure it exists with this exact name.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Exception in log_to_posted_sheet for Original_Post_ID {original_post_id}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False

def make_threads_api_request(endpoint, method='POST', params=None, data=None, headers=None, retries=3, delay=10):
    """Makes a request to the Threads API with retry logic."""
    url = f"{THREADS_API_BASE_URL}{endpoint}"
    attempt = 0
    while attempt < retries:
        try:
            print(f"LOG: API Call Attempt {attempt + 1}/{retries} to {method} {url}")
            if method.upper() == 'POST':
                response = requests.post(url, params=params, json=data, headers=headers, timeout=60)
            elif method.upper() == 'GET':
                 response = requests.get(url, params=params, headers=headers, timeout=60)
            else:
                print(f"ERROR: Unsupported HTTP method '{method}' for make_threads_api_request.", file=sys.stderr)
                return None
            
            print(f"LOG: API Response Status: {response.status_code}")
            response.raise_for_status() 
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR: API request failed (Attempt {attempt + 1}/{retries}): {e}", file=sys.stderr)
            attempt += 1
            if attempt < retries:
                print(f"LOG: Retrying in {delay} seconds...", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"ERROR: Max retries reached for {url}. Giving up.", file=sys.stderr)
                return None
        except Exception as e:
             print(f"ERROR: An unexpected error occurred during API request (Attempt {attempt + 1}/{retries}): {e}", file=sys.stderr)
             traceback.print_exc(file=sys.stderr)
             attempt += 1
             if attempt < retries:
                 print(f"LOG: Retrying in {delay} seconds...", file=sys.stderr)
                 time.sleep(delay)
             else:
                 print(f"ERROR: Max retries reached for {url} after unexpected error. Giving up.", file=sys.stderr)
                 return None
    return None

def create_threads_container(user_id, access_token, text_content, reply_to_id=None):
    endpoint = f"{user_id}/threads"
    params = {
        'media_type': 'TEXT',
        'text': text_content,
        'access_token': access_token
    }
    if reply_to_id:
        params['reply_to_id'] = reply_to_id
    print(f"LOG: Creating container for user {user_id}, reply_to: {reply_to_id}")
    response_data = make_threads_api_request(endpoint, method='POST', params=params)
    if response_data and 'id' in response_data:
        print(f"LOG: Created container with ID: {response_data['id']}")
        return response_data['id']
    print(f"ERROR: Failed to create container. Response: {response_data}", file=sys.stderr)
    return None

def publish_threads_container(user_id, access_token, creation_id):
    endpoint = f"{user_id}/threads_publish"
    params = {
        'creation_id': creation_id,
        'access_token': access_token
    }
    print(f"LOG: Publishing container {creation_id} for user {user_id}")
    response_data = make_threads_api_request(endpoint, method='POST', params=params)
    if response_data and 'id' in response_data:
        print(f"LOG: Published container with Media ID: {response_data['id']}")
        return response_data['id']
    print(f"ERROR: Failed to publish container. Response: {response_data}", file=sys.stderr)
    return None

# --- Core Bot Logic Function for Posting ---
def process_post(post_id_to_post, account_name_to_use):
    print(f"LOG: Processing post for Post_ID: {post_id_to_post}, Account: {account_name_to_use}")
    account_name_upper = account_name_to_use.upper()

    threads_user_id = os.getenv(f'THREADS_USER_ID_{account_name_upper}')
    threads_access_token = os.getenv(f'THREADS_ACCESS_TOKEN_{account_name_upper}')

    if not threads_user_id or not threads_access_token:
        error_note = f"Posting credentials (User ID or Access Token) not found for account '{account_name_to_use}'. Expected env vars: THREADS_USER_ID_{account_name_upper} and THREADS_ACCESS_TOKEN_{account_name_upper}"
        print(f"ERROR: {error_note}", file=sys.stderr)
        return {'status': 'failure', 'error_message': error_note}

    sheet = get_google_sheet_client()
    if not sheet:
        return {'status': 'failure', 'error_message': 'Failed to connect to Google Sheets.'}

    post_data, row_index = get_post_data(sheet, post_id_to_post)
    if not post_data or row_index is None:
        return {'status': 'failure', 'error_message': 'Post data not found, not Ready, or error reading sheet.'}

    blocks_content = [
        post_data.get('Block_1_Content', ''), post_data.get('Block_2_Content', ''),
        post_data.get('Block_3_Content', ''), post_data.get('Block_4_Content', '')
    ]

    if not any(block.strip() for block in blocks_content):
        error_note = f"No content found for Post_ID {post_id_to_post} in any block."
        print(f"ERROR: {error_note}", file=sys.stderr)
        update_post_status(sheet, row_index, "Error", notes=error_note)
        return {'status': 'failure', 'error_message': error_note}

    update_post_status(sheet, row_index, "Posting")
    print(f"LOG: Starting to post Post_ID {post_id_to_post} for account {account_name_to_use}")

    root_threads_media_id = None
    previous_block_media_id = None
    posting_successful = True

    for i, block_content_raw in enumerate(blocks_content):
        block_content = block_content_raw.strip()
        block_number = i + 1
        if not block_content:
            print(f"LOG: Block {block_number} is empty. Skipping.")
            continue

        print(f"LOG: Attempting to post Block {block_number}...")
        creation_id = create_threads_container(
            threads_user_id, threads_access_token, block_content,
            reply_to_id=previous_block_media_id
        )
        if not creation_id:
            error_note = f"Failed to create container for Block {block_number}"
            print(f"ERROR: {error_note}", file=sys.stderr)
            update_post_status(sheet, row_index, "Error", notes=error_note)
            posting_successful = False
            break
        
        print(f"LOG: Waiting {POST_DELAY_SECONDS} seconds before publishing Block {block_number}...")
        time.sleep(POST_DELAY_SECONDS)
        
        published_media_id = publish_threads_container(
            threads_user_id, threads_access_token, creation_id
        )
        if not published_media_id:
            error_note = f"Failed to publish container for Block {block_number}"
            print(f"ERROR: {error_note}", file=sys.stderr)
            update_post_status(sheet, row_index, "Error", notes=error_note)
            posting_successful = False
            break
            
        if block_number == 1:
            root_threads_media_id = published_media_id
        previous_block_media_id = published_media_id

    output_data = {'account_name': account_name_to_use}
    if posting_successful and root_threads_media_id:
        print(f"LOG: Successfully posted thread. Root ID: {root_threads_media_id}")
        # First, update status in Ready_To_Post (existing logic)
        update_post_status(sheet, row_index, "Posted", threads_post_id=root_threads_media_id)
        
        # --- MODIFIED/NEW --- Call to log to "Posted_Logs" sheet
        # Use UTC time for consistency if preferred: datetime.utcnow().isoformat() + "Z"
        timestamp_now_iso = datetime.now().isoformat() 
        
        log_success = log_to_posted_sheet(
            sheet=sheet, # Use the same sheet client
            original_post_id=post_id_to_post, 
            threads_post_id=root_threads_media_id,
            account_name=account_name_to_use,
            timestamp_posted=timestamp_now_iso
        )
        if not log_success:
            print(f"WARNING: Failed to log successful post (Original_Post_ID: {post_id_to_post}) to {POSTED_LOGS_WORKSHEET_NAME}", file=sys.stderr)
            # Consider if this failure should affect the overall status returned to N8N.
            # For now, it just logs a warning and the original success status is maintained.
        # --- END MODIFIED/NEW ---
            
        output_data['status'] = 'success'
        output_data['threads_post_id'] = root_threads_media_id
    elif posting_successful and not root_threads_media_id: 
        error_note = "All content blocks were empty. Nothing was posted."
        print(f"WARNING: {error_note}", file=sys.stderr)
        update_post_status(sheet, row_index, "Error", notes=error_note) 
        output_data['status'] = 'failure' 
        output_data['error_message'] = error_note
    else: 
        output_data['status'] = 'failure'
        output_data['error_message'] = "Posting failed during block processing."

    return output_data


# --- Flask Endpoint for Posting ---
@app.route('/process_post', methods=['POST'])
def process_post_endpoint():
    print("LOG: Received request at /process_post endpoint.")
    request_data = request.get_json()
    if not request_data or 'post_id' not in request_data or 'account_name' not in request_data:
        print("ERROR: Invalid request data for /process_post. Missing post_id or account_name.", file=sys.stderr)
        return jsonify({'status': 'error', 'message': 'Invalid request data. Requires post_id and account_name.'}), 400
    
    post_id = request_data['post_id']
    account_name = request_data['account_name']
    
    print(f"LOG: Calling process_post function with Post_ID: {post_id}, Account: {account_name}")
    result = process_post(post_id, account_name)
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

    account_name_upper = account_name_from_n8n.upper()
    insights_token_env_var_name = f"THREADS_ACCESS_TOKEN_{account_name_upper}"
    access_token = os.getenv(insights_token_env_var_name) 

    print(f"LOG: Attempting to retrieve insights token for '{account_name_from_n8n}' using env var name: '{insights_token_env_var_name}'")

    if not access_token:
        print(f"CRITICAL ERROR: Insights Token NOT FOUND for account '{account_name_from_n8n}' using env var '{insights_token_env_var_name}'. Ensure this environment variable is set on Railway and the token has 'threads_manage_insights' permission.")
        return jsonify({"error": f"Server configuration error: Insights Token for account '{account_name_from_n8n}' not set up. Expected env var: {insights_token_env_var_name}"}), 500
    else:
        print(f"LOG: Successfully retrieved insights token (token length: {len(access_token)}).")

    metrics_list = "likes,replies,reposts,quotes,shares,views" 
    insights_api_call_url = f"https://graph.threads.net/v1.0/{threads_post_id}/insights" 
    
    api_params = {
        "metric": metrics_list,
        "access_token": access_token 
    }
    
    print(f"LOG: Calling Threads Insights API: GET {insights_api_call_url} for account {account_name_from_n8n}")

    try:
        response = requests.get(insights_api_call_url, params=api_params, timeout=30) 
        
        print(f"LOG: Threads Insights API Response Status Code: {response.status_code}")
        print(f"LOG: Threads Insights API Response Content (first 500 chars): {response.text[:500]}...")
        response.raise_for_status()
        
        threads_api_response_data = response.json()
        print(f"LOG: Successfully received and parsed JSON from Threads Insights API: {threads_api_response_data}")
        
        extracted_metrics = {}
        if 'data' in threads_api_response_data and isinstance(threads_api_response_data['data'], list):
            for metric_entry in threads_api_response_data['data']:
                metric_name = metric_entry.get('name')
                if metric_entry.get('values') and isinstance(metric_entry['values'], list) and len(metric_entry['values']) > 0:
                    metric_value = metric_entry['values'][0].get('value')
                    if metric_name and metric_value is not None:
                        extracted_metrics[metric_name] = metric_value
        
        if not extracted_metrics: 
            print("LOG: No specific metrics extracted from Threads API response. This might be normal if the post has no engagement yet, or if 'views' is still in development and returns no data for this post.")
            return jsonify({
                "message": "Successfully called Threads API, but no specific metric values were extracted (e.g., post has no engagement, or some metrics are in development).",
                "raw_threads_api_response": threads_api_response_data 
            }), 200 
            
        print(f"LOG: Sending extracted insights back to N8N: {extracted_metrics}")
        return jsonify(extracted_metrics), 200

    except requests.exceptions.HTTPError as http_err:
        error_content = "No response content"
        if http_err.response is not None:
            error_content = http_err.response.text
        error_details = f"HTTP error occurred calling Threads Insights API: {http_err} - Response: {error_content}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to fetch from Threads Insights API (HTTP Error)", "details": str(http_err), "response_text": error_content}), getattr(http_err.response, 'status_code', 500)
    except requests.exceptions.RequestException as req_err:
        error_details = f"Request error occurred calling Threads Insights API: {req_err}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to fetch from Threads Insights API (Request Error)", "details": str(req_err)}), 500
    except ValueError as json_err: 
        response_text_for_error = ""
        if 'response' in locals() and response is not None:
            response_text_for_error = response.text
        error_details = f"JSON decode error from Threads Insights API response: {json_err} - Response: {response_text_for_error}"
        print(f"ERROR: {error_details}")
        return jsonify({"error": "Failed to parse Threads Insights API response", "details": str(json_err), "response_text": response_text_for_error}), 500
    except Exception as e:
        error_details = f"An unexpected error occurred in /get_thread_insights: {e}"
        print(f"ERROR: {error_details}")
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": "An internal server error occurred in insights endpoint", "details": str(e)}), 500

# --- Main Execution (Starts Flask Server) ---
if __name__ == "__main__":
    print("Starting Flask web server to listen for N8N requests...")
    port = int(os.environ.get("PORT", 8080)) 
    app.run(debug=False, host='0.0.0.0', port=port)
