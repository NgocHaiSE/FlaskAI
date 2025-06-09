# emergency_server.py - Simplest possible Flask server with CORS
# Use this to test if the issue is with your main app configuration

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Simple CORS setup
CORS(app)

# Alternative manual CORS setup if flask_cors doesn't work
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        response.headers.add('Access-Control-Allow-Origin', '*')
    
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'false')
    return response

@app.route('/api/test', methods=['GET', 'POST', 'OPTIONS'])
def test():
    print(f"📡 Request: {request.method} {request.path}")
    print(f"🌐 Origin: {request.headers.get('Origin', 'None')}")
    
    return jsonify({
        'status': 'success',
        'message': 'Emergency server working!',
        'method': request.method,
        'origin': request.headers.get('Origin'),
        'timestamp': str(__import__('datetime').datetime.now())
    })

@app.route('/api/user/login', methods=['POST', 'OPTIONS'])
def login():
    print(f"📡 Login Request: {request.method}")
    print(f"🌐 Origin: {request.headers.get('Origin', 'None')}")
    
    if request.method == 'OPTIONS':
        print("✅ Handling preflight")
        return '', 200
    
    data = request.get_json() or {}
    print(f"📦 Data received: {data}")
    
    # Simple mock response
    if data.get('username') and data.get('password'):
        return jsonify({
            'status': 'success',
            'message': 'Emergency login endpoint working',
            'token': 'emergency-token-123',
            'user': {
                'id': 1,
                'username': data.get('username'),
                'role_name': 'Test User'
            }
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Username and password required'
        }), 400

@app.route('/')
def home():
    return jsonify({
        'message': 'Emergency Flask Server',
        'endpoints': [
            'GET /api/test',
            'POST /api/user/login'
        ]
    })

if __name__ == '__main__':
    print("🚨 EMERGENCY FLASK SERVER")
    print("=" * 30)
    print("📍 URL: http://localhost:5000")
    print("🎯 Test endpoint: http://localhost:5000/api/test")
    print("🔑 Login endpoint: http://localhost:5000/api/user/login")
    print("=" * 30)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )

# Quick test commands for this server:
"""
# Test in terminal:
curl http://localhost:5000/api/test

# Test CORS preflight:
curl -X OPTIONS \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  http://localhost:5000/api/user/login -v

# Test login:
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"username":"test","password":"test"}' \
  http://localhost:5000/api/user/login

# Test in browser console:
fetch('http://localhost:5000/api/test')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error)

fetch('http://localhost:5000/api/user/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({username: 'test', password: 'test'})
})
.then(r => r.json())
.then(console.log)
.catch(console.error)
"""