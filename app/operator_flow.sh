#!/bin/bash
# Operator lifecycle test: login → generate → consume → invalidate

BASE_URL="https://srpihhllc.pythonanywhere.com"

# Automatically source live credentials from environment or pipeline sync variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
elif [ -f ../.env ]; then
    export $(cat ../.env | grep -v '#' | xargs)
fi

# 🛡️ Use Admin values provided by your pipeline, falling back to seed defaults if unset
USERNAME="${ADMIN_EMAIL:-admin@example.com}"
PASSWORD="${ADMIN_PASSWORD:-AdminPass123!}"

echo "🔐 Step 0: Login to fetch JWT"
# FIX: Targeted the precise API blueprint routing prefix path
LOGIN_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"email\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  $BASE_URL/api/v1/auth/login)

echo "Login response: $LOGIN_RESPONSE"

JWT_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token // .data.access_token')
if [ "$JWT_TOKEN" == "null" ] || [ -z "$JWT_TOKEN" ]; then
  echo "❌ Failed to fetch JWT token. Check credentials or login endpoint."
  exit 1
fi

echo "✅ Got JWT token"

echo "🔑 Step 1: Generate operator code"
GEN_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"ttl_seconds":300,"length":10}' \
  $BASE_URL/admin/api/v1/codes/generate)

echo "Generate response: $GEN_RESPONSE"

CODE=$(echo $GEN_RESPONSE | jq -r '.operator_code // .data.code')
echo "Operator code is: $CODE"

echo "🚪 Step 2: Consume operator code"
CONSUME_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"code\":\"$CODE\"}" \
  $BASE_URL/admin/api/v1/operator_mode)

echo "Consume response: $CONSUME_RESPONSE"

echo "🧹 Step 3: Invalidate all operator codes"
INVALIDATE_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  $BASE_URL/admin/api/v1/codes/invalidate)

echo "Invalidate response: $INVALIDATE_RESPONSE"

echo "✅ Flow complete. Now open: $BASE_URL/admin/cockpit"