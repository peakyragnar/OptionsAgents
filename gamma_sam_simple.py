#!/usr/bin/env python3
"""
Gamma Tool Sam - Simple test version
Just to verify Flask is working
"""

from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    """Test endpoint"""
    return """
    <html>
    <head><title>Gamma Tool Sam Test</title></head>
    <body>
        <h1>Gamma Tool Sam - Test Page</h1>
        <p>Flask is working! ✅</p>
        <p>Try the API: <a href="/api/test">/api/test</a></p>
    </body>
    </html>
    """

@app.route('/api/test')
def test_api():
    """Test API endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Flask is working!',
        'port': 5555
    })

if __name__ == '__main__':
    print("Starting test server on port 5555...")
    print("Open: http://localhost:5555")
    app.run(host='127.0.0.1', port=5555, debug=True)