#!/bin/bash

# Test script for n8n webhook connection
# This tests the exact same connection that the WordPress plugin is trying to make

echo "Testing n8n webhook connection..."
echo "URL: http://localhost:5678/webhook/dehum-chat"
echo "Username: dehum"
echo "Password: LurINHgygtCjHJKIjnms"
echo ""

# Test the webhook with curl (same method WordPress uses internally)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'dehum:LurINHgygtCjHJKIjnms' | base64)" \
  -d '{"message": "Hello from test script"}' \
  -v \
  http://localhost:5678/webhook/dehum-chat

echo ""
echo ""
echo "=== RESULTS INTERPRETATION ==="
echo "✅ SUCCESS: If you see a JSON response with 'success: true'"
echo "❌ 401 Unauthorized: Username or password is wrong"
echo "❌ 404 Not Found: Webhook URL is wrong or n8n workflow not active"
echo "❌ Connection refused: n8n server is not running or wrong port"
echo "❌ Could not resolve host: URL/hostname is wrong" 