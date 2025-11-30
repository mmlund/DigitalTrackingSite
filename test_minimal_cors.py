"""
Minimal test Flask app to verify CORS is working.
This is a simplified version to isolate the CORS issue.
"""

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/track', methods=['GET', 'POST', 'OPTIONS'])
def track():
    """Simple tracking endpoint with CORS"""
    
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'preflight_ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 200
    
    # Handle actual requests
    response = jsonify({
        'status': 'ok',
        'message': 'CORS test successful',
        'method': request.method
    })
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response, 200

@app.route('/')
def index():
    return 'Tracking API is running', 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
