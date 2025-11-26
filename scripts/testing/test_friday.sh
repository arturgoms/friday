#!/bin/bash

# Test script for Friday AI
API_KEY="5b604c9f8e2d1be2978d91b51f2b3fe70b64f2b552cea1870e764dd6016c0de9"

echo "================================"
echo "Testing Friday AI Assistant"
echo "================================"
echo ""

# Health check
echo "1. Health Check:"
curl -s http://localhost:8080/health -H "X-API-Key: $API_KEY" | python3 -m json.tool
echo ""
echo ""

# RAG test
echo "2. RAG Test (asking 'Who is Camila?'):"
curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Who is Camila?", "use_rag": true, "use_memory": false, "use_web": false, "save_memory": false}' \
  | python3 -c "import sys, json; data = json.load(sys.stdin); print('Answer:', data['answer'][:200] + '...'); print('Used RAG:', data['used_rag'])"
echo ""
echo ""

# Memory test - Create
echo "3. Memory Creation Test:"
TIMESTAMP=$(date +%s)
MEMORY_RESPONSE=$(curl -s -X POST http://localhost:8080/remember \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"content\": \"Test memory ${TIMESTAMP}: My favorite test food is pizza\", \"title\": \"Test Memory ${TIMESTAMP}\", \"tags\": [\"test\"]}")
echo "$MEMORY_RESPONSE" | python3 -m json.tool
MEMORY_FILE=$(echo "$MEMORY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('filepath', ''))")
echo ""

# Memory test - Retrieve
echo "4. Memory Retrieval Test:"
curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"message\": \"What is my favorite test food?\", \"use_rag\": false, \"use_memory\": true, \"use_web\": false, \"save_memory\": false}" \
  | python3 -c "import sys, json; data = json.load(sys.stdin); print('Answer:', data['answer'][:150] + '...'); print('Used Memory:', data['used_memory'])"
echo ""
echo ""

# Cleanup test memory
echo "5. Cleanup Test Memory:"

# Get the memory ID from ChromaDB by listing and finding our test memory
MEMORY_LIST=$(curl -s -H "X-API-Key: $API_KEY" http://localhost:8080/admin/memories?limit=200)
MEMORY_ID=$(echo "$MEMORY_LIST" | python3 -c "
import sys, json
data = json.load(sys.stdin)
memories = data.get('memories', [])
# Search for our test memory by content
test_mem = [m for m in memories if 'favorite test food is pizza' in m.get('full_content', '')]
print(test_mem[0]['id'] if test_mem else '')
" 2>/dev/null)

if [ -n "$MEMORY_ID" ]; then
  echo "Deleting memory from ChromaDB: $MEMORY_ID"
  curl -s -X DELETE -H "X-API-Key: $API_KEY" "http://localhost:8080/admin/memories/$MEMORY_ID" | python3 -c "import sys, json; print('✅', json.load(sys.stdin).get('message', 'Deleted'))"
else
  echo "⚠️  Could not find test memory ID in ChromaDB"
  echo "Debug: Checking what memories exist..."
  echo "$MEMORY_LIST" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"Total memories: {data.get('count', 0)}\"); [print(f\"  - {m['content']}\") for m in data.get('memories', [])[:5]]"
fi

# Also remove the file if it exists
if [ -n "$MEMORY_FILE" ] && [ -f "$MEMORY_FILE" ]; then
  rm -f "$MEMORY_FILE"
  echo "✅ Removed test memory file: $MEMORY_FILE"
fi
echo ""

# Time accuracy test
echo "6. Time/Date Accuracy Test:"
SYSTEM_TIME=$(TZ='America/Sao_Paulo' date '+%I:%M %p')
SYSTEM_DATE=$(TZ='America/Sao_Paulo' date '+%A, %B %d, %Y')
echo "System time (UTC-3): $SYSTEM_TIME"
echo "System date: $SYSTEM_DATE"
echo ""
echo "Testing Friday's time awareness..."
RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "What time is it right now?", "use_rag": false, "use_memory": false, "use_web": false, "save_memory": false}')
FRIDAY_TIME=$(echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['answer'])" | grep -oP '\d{1,2}:\d{2} [AP]M' | head -1)
echo "Friday's response: $FRIDAY_TIME"
if [ "$SYSTEM_TIME" = "$FRIDAY_TIME" ]; then
  echo "✅ Time matches!"
else
  echo "⚠️  Time mismatch (expected: $SYSTEM_TIME, got: $FRIDAY_TIME)"
fi
echo ""

# Debug info
echo "7. System Info:"
curl -s http://localhost:8080/admin/debug -H "X-API-Key: $API_KEY" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"Vault: {data['vault_path']}\"); print(f\"MD Files: {data['num_md_files']}\"); print(f\"Indexed Chunks: {data['obsidian_chunks']}\"); print(f\"Memory Entries: {data['memory_entries']}\")"
echo ""
echo ""

echo "================================"
echo "All tests complete!"
echo "================================"
