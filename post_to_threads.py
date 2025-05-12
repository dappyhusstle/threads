import os
import json
import time
import requests
import gspread
from google.oauth2.service_account import Credentials
import sys
import traceback # Uncommented for full traceback

# --- Configuration ---
# These will be loaded from environment variables set by Railway
# We will store the full JSON key content in this environment variable on Railway
GOOGLE_CREDENTIALS_JSON_CONTENT = os.environ.get('GOOGLE_CREDENTIALS_JSON_CONTENT')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
READY_TO_POST_WORKSHEET_NAME = os.environ.get('READY_TO_POST_WORKSHEET_NAME', 'Ready_To_Post')
THREADS_API_BASE_URL = os.environ.get('THREADS_API_BASE_URL', 'https://graph.threads.net/v1.0/')
POST_DELAY_SECONDS = 30 # Recommended delay between publishing each block

# --- Helper Functions ---

# UPDATED FUNCTION for Railway: get_google_sheet_client to read JSON content from env var with traceback
def get_google_sheet_client():
    """Authenticates with Google Sheets using service account JSON content from env var."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        print("Attempting to load credentials from environment variable GOOGLE_CREDENTIALS_JSON_CONTENT") # Added logging
        if not GOOGLE_CREDENTIALS_JSON_CONTENT:
             print("Error: GOOGLE_CREDENTIALS_JSON_CONTENT environment variable is not set in Railway.", file=sys.stderr)
             return None

        try:
            # Load from the environment variable string
            service_account_info = json.loads(GOOGLE_CREDENTIALS_JSON_CONTENT)
            print("Successfully loaded service account info from environment variable.") # Added logging
        except json.JSONDecodeError as e: # Catch JSONDecodeError specifically
             print(f"Error reading credentials from env var: Could not decode JSON from GOOGLE_CREDENTIALS_JSON_CONTENT. Content might be invalid JSON.", file=sys.stderr)
             print(f"Exception type (JSONDecodeError): {type(e)}", file=sys.stderr)
             print(f"Exception details (JSONDecodeError): {e}", file=sys.stderr)
             traceback.print_exc(file=sys.stderr) # Print traceback for JSON decode error
             return None
        except Exception as e: # Catch any other errors during credential processing
             print(f"Error processing credentials from environment variable: {e}", file=sys.stderr)
             print(f"Exception type: {type(e)}", file=sys.stderr)
             print(f"Exception details: {e}", file=sys.stderr)
             traceback.print_exc(file=sys.stderr) # Print traceback for other credential errors
             return None


        # Now use the info to create credentials
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        print("Successfully created credentials object from env var.") # Added logging

        client = gspread.authorize(credentials)
        print(f"Successfully authorized gspread client for sheet: {GOOGLE_SHEET_URL}") # Added logging
        sheet = client.open_by_url(GOOGLE_SHEET_URL)
        print("Successfully opened Google Sheet object.") # Added logging
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets after loading credentials.", file=sys.stderr)
        print(f"Exception type: {type(e)}", file=sys.stderr)
        print(f"Exception details: {e}", file=sys.stderr)
        # Optional: uncomment below to print full traceback on Railway logs
        # import traceback # This line is commented out here, but uncommented at the top
        traceback.print_exc(file=sys.stderr) # Uncommented for full traceback
        return None


# get_post_data function (same as previous version with added logging)
def get_post_data(sheet, post_id):
    """Reads a specific row from the Ready_To_Post sheet by Post_ID."""
    try:
        print(f"Attempting to access worksheet: {READY_TO_POST_WORKSHEET_NAME}") # Added logging
        worksheet = sheet.worksheet(READY_TO_POST_WORKSHEET_NAME)
        print(f"Successfully accessed worksheet: {READY_TO_POST_WORKSHEET_NAME}") # Added logging

        # Find the row by Post_ID - assuming Post_ID is in the first column (A)
        # We need to find the row index first
        print(f"Attempting to find Post_ID '{post_id}' in column 1...") # Added logging
        cell = worksheet.find(str(post_id), in_column=1)
        if not cell:
            print(f"Error: Post_ID '{post_id}' not found in {READY_TO_POST_WORKSHEET_NAME}.", file=sys.stderr)
            return None, None # Return None if not found

        print(f"Successfully found Post_ID '{post_id}' at row {cell.row}.") # Added logging
        row_values = worksheet.row_values(cell.row)
        print(f"Successfully read row values for row {cell.row}.") # Added logging

        # Assuming columns are in the order defined in the blueprint
        headers = worksheet.row_values(1) # Get headers from the first row
        print("Successfully read header row.") # Added logging

        # Map headers to values for easier access
        post_data = dict(zip(headers, row_values))

        # Check status
        if post_data.get('Status') != 'Ready':
            print(f"Warning: Post_ID '{post_id}' status is '{post_data.get('Status')}'. Skipping. Current status: {post_data.get('Status')}", file=sys.stderr) # Added current status to warning
            return None, cell.row # Return None if not ready, but provide row_index for error logging later

        print(f"Post {post_id} is Ready. Data loaded successfully.") # Added logging
        return post_data, cell.row # Return data and row index

    except gspread.WorksheetNotFound:
        print(f"Error reading post data: Worksheet '{READY_TO_POST_WORKSHEET_NAME}' not found in the Google Sheet.", file=sys.stderr)
        print("Please double-check the worksheet name in your .env file and Google Sheet.", file=sys.stderr)
        return None, None # Cannot proceed if worksheet is missing
    except Exception as e:
        # Catch any other errors during worksheet access or data reading
        print(f"Error reading post data for Post_ID {post_id} after worksheet access: {e}", file=sys.stderr) # Clarified error source
        return None, None # Return None on any other error

# update_post_status function (same as previous version with added logging)
def update_post_status(sheet, row_index, status, threads_post_id=None, notes=None):
    """Updates the Status, Threads_Post_ID, and Notes columns for a row."""
    # Need to re-get worksheet in case sheet object becomes stale (though less likely in a short script)
    try:
        print(f"Attempting to update status for row {row_index} to '{status}'...") # Added logging
        worksheet = sheet.worksheet(READY_TO_POST_WORKSHEET_NAME)
        header_row = worksheet.row_values(1) # Get headers again

        updates = {
            'Status': status
        }
        if threads_post_id:
             updates['Threads_Post_ID'] = threads_post_id
        if notes:
             updates['Notes'] = notes

        # Perform updates based on column headers dynamically
        for header, value in updates.items():
            if header in header_row:
                col_index = header_row.index(header) + 1
                worksheet.update_cell(row_index, col_index, value)
                print(f"Successfully updated column '{header}' for row {row_index}.") # Added logging
            else:
                 print(f"Warning: Column header '{header}' not found in {READY_TO_POST_WORKSHEET_NAME} for update.", file=sys.stderr)

        print(f"Finished status update attempts for row {row_index}.") # Added logging

    except Exception as e:
        print(f"Error updating status for row {row_index}: {e}", file=sys.stderr)
        # Note: If sheet update fails, the script might proceed, but the status won't be reflected.
        # Consider more robust error handling here if necessary.


# make_threads_api_request function (same as before)
def make_threads_api_request(endpoint, method='POST', params=None, data=None, headers=None, retries=3, delay=10):
    """Makes a request to the Threads API with retry logic."""
    url = f"{THREADS_API_BASE_URL}{endpoint}"
    attempt = 0
    while attempt < retries:
        try:
            print(f"Attempt {attempt + 1} of {retries} to call {method} {url}") # Log attempt

            if method.upper() == 'POST':
                response = requests.post(url, params=params, json=data, headers=headers)
            elif method.upper() == 'GET':
                 response = requests.get(url, params=params, headers=headers)

            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            print(f"Successful response from {url}")
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"API request failed (Attempt {attempt + 1}/{retries}): {e}", file=sys.stderr)
            attempt += 1
            if attempt < retries:
                print(f"Retrying in {delay} seconds...", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"Max retries reached for {url}. Giving up.", file=sys.stderr)
                return None
        except Exception as e:
             print(f"An unexpected error occurred during API request (Attempt {attempt + 1}/{retries}): {e}", file=sys.stderr)
             attempt += 1
             if attempt < retries:
                 print(f"Retrying in {delay} seconds...", file=sys.stderr)
                 time.sleep(delay)
             else:
                 print(f"Max retries reached for {url}. Giving up.", file=sys.stderr)
                 return None
    return None

# create_threads_container function (same as before)
def create_threads_container(user_id, access_token, text_content, reply_to_id=None):
    """Creates a media container for a text post or reply."""
    endpoint = f"{user_id}/threads"
    params = {
        'media_type': 'TEXT',
        'text': text_content,
        'access_token': access_token
    }
    if reply_to_id:
        params['reply_to_id'] = reply_to_id

    print(f"Creating container for user {user_id}, reply_to: {reply_to_id}")
    response_data = make_threads_api_request(endpoint, method='POST', params=params)

    if response_data and 'id' in response_data:
        print(f"Created container with ID: {response_data['id']}")
        return response_data['id']
    else:
        print("Failed to create container. Response data:", response_data, file=sys.stderr)
        return None

# publish_threads_container function (same as before)
def publish_threads_container(user_id, access_token, creation_id):
    """Publishes a media container."""
    endpoint = f"{user_id}/threads_publish"
    params = {
        'creation_id': creation_id,
        'access_token': access_token
    }
    print(f"Publishing container {creation_id} for user {user_id}")
    response_data = make_threads_api_request(endpoint, method='POST', params=params)

    if response_data and 'id' in response_data:
        print(f"Published container with Media ID: {response_data['id']}")
        return response_data['id']
    else:
        print("Failed to publish container. Response data:", response_data, file=sys.stderr)
        return None


# --- Main Execution ---

if __name__ == "__main__":
    # Expecting Post_ID and Account Name as command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python post_to_threads.py <post_id> <account_name>", file=sys.stderr)
        sys.exit(1)

    post_id_to_post = sys.argv[1]
    account_name_to_use = sys.argv[2]

    # Retrieve account-specific credentials from environment variables
    threads_user_id = os.environ.get(f'THREADS_USER_ID_{account_name_to_use.upper()}')
    threads_access_token = os.environ.get(f'THREADS_ACCESS_TOKEN_{account_name_to_use.upper()}')

    if not threads_user_id or not threads_access_token:
        error_note = f"Threads credentials not found for account '{account_name_to_use}'."
        print(f"Error: {error_note}", file=sys.stderr)
        sys.exit(1) # Exit if credentials missing

    # 1. Connect to Google Sheets and get post data
    sheet = get_google_sheet_client()
    if not sheet:
        # Error message already printed by get_google_sheet_client
        sys.exit(1) # Exit if sheet connection failed

    # --- ADDED LOGGING HERE (Keep this line) ---
    print("Successfully obtained sheet object, proceeding to get post data.")
    # --- END ADDED LOGGING ---

    post_data, row_index = get_post_data(sheet, post_id_to_post)

    if not post_data or row_index is None:
        re_sheet = get_google_sheet_client() # Attempt re-connection for logging
        if re_sheet and row_index is not None:
             update_post_status(re_sheet, row_index, "Error", notes="Post data not found or status not Ready.")
        elif re_sheet:
             pass # Error message already printed by get_post_data if row_index is None
        else:
             print("Error: Could not connect to sheet to log status after data fetch failure.", file=sys.stderr)
        sys.exit(1)

    blocks_content = [
        post_data.get('Block_1_Content', ''),
        post_data.get('Block_2_Content', ''),
        post_data.get('Block_3_Content', ''),
        post_data.get('Block_4_Content', '')
    ]

    if not any(block.strip() for block in blocks_content):
        error_note = f"No content found for Post_ID {post_id_to_post} in any block."
        print(f"Error: {error_note}", file=sys.stderr)
        update_post_status(sheet, row_index, "Error", notes=error_note)
        sys.exit(1)

    # 2. Update status to "Posting"
    try:
        update_post_status(sheet, row_index, "Posting")
        print(f"Successfully updated status to Posting for row {row_index}.")
    except Exception as e:
         print(f"Warning: Failed initial status update to 'Posting' for row {row_index}: {e}", file=sys.stderr)
         re_sheet = get_google_sheet_client() # Attempt re-connection
         if re_sheet:
             try:
                 update_post_status(re_sheet, row_index, "Posting")
                 print(f"Successfully updated status to Posting after re-connection for row {row_index}.")
             except Exception as e2:
                  print(f"Error: Failed status update to 'Posting' even after re-connection for row {row_index}: {e2}", file=sys.stderr)
         else:
             print("Error: Could not re-connect to sheet to update status to Posting.", file=sys.stderr)

    print(f"Starting to post Post_ID {post_id_to_post} for account {account_name_to_use}")

    # 3. Post blocks sequentially
    root_threads_media_id = None
    previous_block_media_id = None
    full_post_content = ""
    posting_successful = True

    for i, block_content in enumerate(blocks_content):
        block_number = i + 1
        if not block_content.strip():
             print(f"Warning: Block {block_number} is empty or contains only whitespace. Skipping.", file=sys.stderr)
             full_post_content += f"[Block {block_number} - Empty]\n---\n"
             continue

        print(f"Attempting to post Block {block_number}...")

        creation_id = create_threads_container(
            threads_user_id,
            threads_access_token,
            block_content.strip(),
            reply_to_id=previous_block_media_id
        )

        if not creation_id:
            print(f"Failed to create container for Block {block_number}. Aborting post.", file=sys.stderr)
            posting_successful = False
            try:
                re_sheet = get_google_sheet_client()
                if re_sheet and row_index is not None:
                    update_post_status(re_sheet, row_index, "Error", notes=f"Failed to create container for Block {block_number}")
                elif re_sheet:
                     print("Warning: Could not update sheet status after container creation failure (no row_index).", file=sys.stderr)
                else:
                     print("Error: Could not reconnect to sheet to log status after container creation failure.", file=sys.stderr)
            except Exception as sheet_err:
                 print(f"Error attempting to log sheet status after API failure: {sheet_err}", file=sys.stderr)
            break

        print(f"Waiting {POST_DELAY_SECONDS} seconds before publishing Block {block_number}...")
        time.sleep(POST_DELAY_SECONDS)

        published_media_id = publish_threads_container(
            threads_user_id,
            threads_access_token,
            creation_id
        )

        if not published_media_id:
            print(f"Failed to publish container for Block {block_number}. Aborting post.", file=sys.stderr)
            posting_successful = False
            try:
                re_sheet = get_google_sheet_client()
                if re_sheet and row_index is not None:
                    update_post_status(re_sheet, row_index, "Error", notes=f"Failed to publish container for Block {block_number}")
                elif re_sheet:
                     print("Warning: Could not update sheet status after container publishing failure (no row_index).", file=sys.stderr)
                else:
                     print("Error: Could not reconnect to sheet to log status after container publishing failure.", file=sys.stderr)
            except Exception as sheet_err:
                 print(f"Error attempting to log sheet status after API failure: {sheet_err}", file=sys.stderr)
            break

        if block_number == 1:
            root_threads_media_id = published_media_id
        previous_block_media_id = published_media_id

        full_post_content += block_content.strip() + "\n---\n"

    # 4. Update sheet status based on posting result
    try:
        sheet_for_final_update = get_google_sheet_client()
        if not sheet_for_final_update:
             print("Error: Could not get a fresh sheet connection for final status update.", file=sys.stderr)
             sheet_for_final_update = sheet

        output_data = {
            'account_name': account_name_to_use,
            'full_post_content': full_post_content.strip()
        }

        if posting_successful and root_threads_media_id:
            print(f"Successfully posted thread. Root ID: {root_threads_media_id}")
            if sheet_for_final_update and row_index is not None:
                update_post_status(sheet_for_final_update, row_index, "Posted", threads_post_id=root_threads_media_id)
            elif sheet_for_final_update:
                 print("Warning: Posting was successful but failed to update sheet status to 'Posted' (no row_index).", file=sys.stderr)
            else:
                 print("Warning: Posting was successful but failed to update sheet status to 'Posted' (no sheet connection).", file=sys.stderr)
            output_data['status'] = 'success'
            output_data['threads_post_id'] = root_threads_media_id
        else:
            error_note = "Posting failed or incomplete."
            print(f"Error: {error_note}", file=sys.stderr)
            if sheet_for_final_update and row_index is not None:
                update_post_status(sheet_for_final_update, row_index, "Error", notes=error_note)
            elif sheet_for_final_update:
                 print("Warning: Posting failed but failed to update sheet status to 'Error' (no row_index).", file=sys.stderr)
            else:
                 print("Warning: Posting failed but failed to update sheet status to 'Error' (no sheet connection).", file=sys.stderr)
            output_data['status'] = 'failure'
            output_data['error_message'] = error_note

    except Exception as e:
         print(f"Critical Error during final status update or output preparation: {e}", file=sys.stderr)
         output_data = {
            'account_name': account_name_to_use,
            'full_post_content': full_post_content.strip(),
            'status': 'failure',
            'error_message': f"Critical error during final processing: {e}"
         }

    print(json.dumps(output_data))

    if not posting_successful:
        sys.exit(1)
    else:
        sys.exit(0)
