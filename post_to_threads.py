from flask import Flask, request, jsonify
import os
import requests # For making API calls to Threads Insights API (will use later)
# Add any other imports your /process_post route needs, like instagrapi, etc.
# from instagrapi import Client # Example if your posting route uses it

app = Flask(__name__)

# +-------------------------------------------------------------------+
# | YOUR EXISTING /process_post ENDPOINT LOGIC                        |
# +-------------------------------------------------------------------+
@app.route('/process_post', methods=['POST'])
def process_post_route():
    # PASTE YOUR EXISTING CODE FOR THE /process_post ENDPOINT HERE
    # This is the code that takes post_id and account_name,
    # retrieves post content from Google Sheets,
    # posts to Threads using instagrapi,
    # and updates the Google Sheet with "Posted" status.
    
    # Example placeholder - REPLACE THIS with your actual code
    print("LOG: /process_post endpoint called")
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON input for posting"}), 400
    post_id = data.get('post_id')
    account_name_for_posting = data.get('account_name')
    if not post_id or not account_name_for_posting:
        return jsonify({"error": "Missing post_id or account_name for posting"}), 400
    
    # Simulate posting
    print(f"LOG: Simulating post for post_id: {post_id} to account: {account_name_for_posting}")
    # In reality, here you'd use instagrapi with credentials for account_name_for_posting
    
    # Simulate success
    return jsonify({
        "status": "success_simulation", 
        "message": f"Simulated posting for {post_id} to {account_name_for_posting}",
        "threads_post_id": "simulated_1234567890" # Return a simulated ID
    }), 200


# +-------------------------------------------------------------------+
# | NEW /get_thread_insights ENDPOINT LOGIC                           |
# +-------------------------------------------------------------------+
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
    # Use the exact environment variable name from your Railway settings
    # This must match what you have in Railway for your TESTACCOUNT's insights token
    token_env_var_name_used = f"THREADS_ACCESS_TOKEN_{account_name_from_n8n.upper()}"

    # For initial testing, let's be very specific for TESTACCOUNT
    if account_name_from_n8n.upper() == "TESTACCOUNT":
        # Ensure this EXACT variable name exists in your Railway environment variables
        token_env_var_name_used = 'THREADS_ACCESS_TOKEN_TESTACCOUNT' 
        access_token = os.getenv(token_env_var_name_used)
    # Add elif blocks here later for ACC1, ACC2, etc.
    # elif account_name_from_n8n.upper() == "ACC1":
    #     token_env_var_name_used = 'THREADS_ACCESS_TOKEN_ACC1' 
    #     access_token = os.getenv(token_env_var_name_used)
    else:
        print(f"LOG: Account name '{account_name_from_n8n}' not yet explicitly configured for insights token.")
        # Fallback to the dynamic construction if you've named other env vars this way
        access_token = os.getenv(token_env_var_name_used) 


    print(f"LOG: Attempting to retrieve token for '{account_name_from_n8n}' using env var name: '{token_env_var_name_used}'")

    if not access_token:
        print(f"CRITICAL ERROR: Token NOT FOUND for account '{account_name_from_n8n}' using env var '{token_env_var_name_used}'. Please check Railway environment variables.")
        return jsonify({"error": f"Server configuration error: Token for account '{account_name_from_n8n}' not set up correctly. Expected env var: {token_env_var_name_used}"}), 500
    else:
        # Just print a part of the token to confirm it's loaded, NEVER the full token to logs in production for security
        print(f"LOG: Successfully retrieved token (first 5 chars for verification: {access_token[:5]}...).")


    # --- Stage 1 Test: Placeholder response - just send back what you received and token status ---
    # --- We will replace this with the actual Threads API call logic in the next step ---
    response_data = {
        "message": "Railway endpoint /get_thread_insights reached successfully!",
        "received_threads_post_id": threads_post_id,
        "received_account_name": account_name_from_n8n,
        "attempted_token_env_var": token_env_var_name_used,
        "token_found_and_loaded": True,
        "next_step": "Call actual Threads Insights API using this token."
    }
    print(f"LOG: Sending placeholder response back to N8N: {response_data}")
    return jsonify(response_data), 200


# This part is important for Railway to run your Flask app
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080)) # Railway provides the PORT env var
    app.run(debug=False, host='0.0.0.0', port=port) # debug=False for production on Railway
