#!/bin/bash

# Test script for Friday AI
API_KEY="5b604c9f8e2d1be2978d91b51f2b3fe70b64f2b552cea1870e764dd6016c0de9"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Helper function to print test results
test_result() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    if [ "$1" = "pass" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        if [ -n "$3" ]; then
            echo -e "${YELLOW}  Expected: $3${NC}"
        fi
        if [ -n "$4" ]; then
            echo -e "${YELLOW}  Got: $4${NC}"
        fi
    fi
}

echo "================================"
echo "Testing Friday AI Assistant"
echo "================================"
echo ""

# Wait for API to be ready
echo -e "${BLUE}Waiting for API to be ready...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
API_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health -H "X-API-Key: $API_KEY" 2>/dev/null)
    if [ "$HEALTH_CHECK" = "200" ]; then
        API_READY=true
        echo "✓ API is ready"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ "$API_READY" = false ]; then
    echo -e "${RED}✗ API is not responding after $MAX_RETRIES attempts${NC}"
    echo "Please check if Friday service is running: systemctl status friday.service"
    exit 1
fi
echo ""

# Health check
echo -e "${BLUE}1. Health Check:${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8080/health -H "X-API-Key: $API_KEY")
echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
if [ "$HEALTH_STATUS" = "running" ]; then
    test_result "pass" "API is running"
else
    test_result "fail" "API health check" "running" "$HEALTH_STATUS"
fi
echo ""

# RAG test - Let the router decide (testing intent routing)
echo -e "${BLUE}2. RAG Test (asking about Camila - testing intent router):${NC}"
echo "Query: 'Tell me about Camila from my notes'"
RAG_RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Tell me about Camila from my notes"}')

# Check if response is valid JSON
if echo "$RAG_RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "$RAG_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print('Answer:', data['answer'][:300] + '...'); print('Used RAG:', data['used_rag']); print('Used Web:', data.get('used_web', False))"
    
    # Validate RAG response
    USED_RAG=$(echo "$RAG_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('used_rag', False))" 2>/dev/null)
    USED_WEB=$(echo "$RAG_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('used_web', False))" 2>/dev/null)
    RAG_ANSWER=$(echo "$RAG_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('answer', '').lower())" 2>/dev/null)
else
    echo -e "${RED}Error: Invalid JSON response${NC}"
    echo "Response: ${RAG_RESPONSE:0:200}"
    test_result "fail" "RAG API returned valid JSON" "JSON response" "Invalid/HTML response"
    USED_RAG="False"
    USED_WEB="False"
    RAG_ANSWER=""
fi

if [ "$USED_RAG" = "True" ]; then
    test_result "pass" "RAG was used (not web search)"
else
    if [ "$USED_WEB" = "True" ]; then
        test_result "fail" "RAG was used instead of web" "used_rag=True" "used_web=True (intent router overrode RAG)"
    else
        test_result "fail" "RAG was used" "True" "$USED_RAG"
    fi
fi

# Check if answer contains expected keywords about YOUR Camila (not Queen Camilla!)
if echo "$RAG_ANSWER" | grep -qE "(veterinarian|vet|camilafds1995@gmail\.com)"; then
    test_result "pass" "Answer contains specific information about YOUR Camila (veterinarian/email)"
elif echo "$RAG_ANSWER" | grep -qi "queen"; then
    test_result "fail" "Answer is about YOUR Camila" "veterinarian/email" "Got Queen Camilla instead (web search was used)"
    echo -e "${YELLOW}  Hint: The query triggered web search instead of RAG. Try asking more specifically about 'my notes'${NC}"
elif echo "$RAG_ANSWER" | grep -qi "wife"; then
    # Check if it mentions veterinarian context along with wife
    if echo "$RAG_ANSWER" | grep -qE "(veterinarian|vet)"; then
        test_result "pass" "Answer mentions wife in correct context with veterinarian"
    else
        test_result "fail" "Answer is about YOUR Camila" "wife + veterinarian" "mentions wife but wrong context"
    fi
else
    test_result "fail" "Answer contains expected information" "wife, veterinarian, or email" "none found"
    echo -e "${YELLOW}  Full answer: ${RAG_ANSWER:0:200}...${NC}"
fi
echo ""

# Memory test - Create
echo -e "${BLUE}3. Memory Creation Test:${NC}"
TIMESTAMP=$(date +%s)
MEMORY_RESPONSE=$(curl -s -X POST http://localhost:8080/remember \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"content\": \"Test memory ${TIMESTAMP}: My favorite test food is pizza\", \"title\": \"Test Memory ${TIMESTAMP}\", \"tags\": [\"test\"]}")

# Check if response is valid JSON
if echo "$MEMORY_RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "$MEMORY_RESPONSE" | python3 -m json.tool
    MEMORY_FILE=$(echo "$MEMORY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('filepath', ''))" 2>/dev/null)
    MEMORY_STATUS=$(echo "$MEMORY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)

    if [ "$MEMORY_STATUS" = "success" ]; then
        test_result "pass" "Memory was created successfully"
    else
        test_result "fail" "Memory creation" "success" "$MEMORY_STATUS"
    fi
else
    echo -e "${RED}Error: Invalid JSON response${NC}"
    echo "Response: ${MEMORY_RESPONSE:0:200}"
    test_result "fail" "Memory creation API returned valid JSON" "JSON response" "Invalid/HTML response"
    MEMORY_FILE=""
    MEMORY_STATUS="error"
fi
echo ""

# Sleep briefly to allow indexing
sleep 2

# Memory test - Retrieve (let router decide)
echo -e "${BLUE}4. Memory Retrieval Test (testing intent router):${NC}"
echo "Query: 'What is my favorite test food?'"
MEMORY_RETRIEVAL=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"message\": \"What is my favorite test food?\"}")

echo "$MEMORY_RETRIEVAL" | python3 -c "import sys, json; data = json.load(sys.stdin); print('Answer:', data['answer'][:200]); print('Used Memory:', data['used_memory'])"

# Validate memory retrieval
USED_MEMORY=$(echo "$MEMORY_RETRIEVAL" | python3 -c "import sys, json; print(json.load(sys.stdin).get('used_memory', False))" 2>/dev/null)
MEMORY_ANSWER=$(echo "$MEMORY_RETRIEVAL" | python3 -c "import sys, json; print(json.load(sys.stdin).get('answer', '').lower())" 2>/dev/null)

if [ "$USED_MEMORY" = "True" ]; then
    test_result "pass" "Memory was used"
else
    test_result "fail" "Memory was used" "True" "$USED_MEMORY"
fi

# Check if answer mentions pizza
if echo "$MEMORY_ANSWER" | grep -qi "pizza"; then
    test_result "pass" "Answer correctly retrieved pizza from memory"
else
    test_result "fail" "Answer retrieved pizza from memory" "contains 'pizza'" "pizza not found"
    echo -e "${YELLOW}  Full answer: ${MEMORY_ANSWER:0:150}...${NC}"
fi
echo ""

# Cleanup test memory
echo -e "${BLUE}5. Cleanup Test Memory:${NC}"

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
  DELETE_RESPONSE=$(curl -s -X DELETE -H "X-API-Key: $API_KEY" "http://localhost:8080/admin/memories/$MEMORY_ID")
  DELETE_MSG=$(echo "$DELETE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)
  
  if echo "$DELETE_MSG" | grep -qi "deleted"; then
      test_result "pass" "Test memory cleaned up from ChromaDB"
  else
      test_result "fail" "Memory cleanup" "deleted" "$DELETE_MSG"
  fi
else
  echo -e "${YELLOW}⚠️  Could not find test memory ID in ChromaDB${NC}"
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
echo -e "${BLUE}6. Time/Date Accuracy Test:${NC}"
SYSTEM_TIME=$(TZ='America/Sao_Paulo' date '+%I:%M %p')
SYSTEM_HOUR=$(TZ='America/Sao_Paulo' date '+%I')
SYSTEM_DATE=$(TZ='America/Sao_Paulo' date '+%A, %B %d, %Y')
echo "System time (UTC-3): $SYSTEM_TIME"
echo "System date: $SYSTEM_DATE"
echo ""
echo "Testing Friday's time awareness..."
echo "Query: 'What time is it right now?'"
TIME_RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "What time is it right now?"}')

# Check if there's an error
TIME_ERROR=$(echo "$TIME_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('detail', ''))" 2>/dev/null)
if [ -n "$TIME_ERROR" ]; then
  echo -e "${RED}Error: $TIME_ERROR${NC}"
  if echo "$TIME_ERROR" | grep -q "get_current_time"; then
    test_result "fail" "Time query (service needs restart)" "time response" "DateTools missing get_current_time method"
    echo -e "${YELLOW}  Note: Run 'friday restart friday' to load updated date_tools.py${NC}"
  else
    test_result "fail" "Time query" "time response" "$TIME_ERROR"
  fi
else
  FRIDAY_ANSWER=$(echo "$TIME_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('answer', ''))" 2>/dev/null)
  FRIDAY_TIME=$(echo "$FRIDAY_ANSWER" | grep -oP '\d{1,2}:\d{2} [AP]M' | head -1)

  echo "Friday's response: $FRIDAY_TIME"
  echo "Full answer: ${FRIDAY_ANSWER:0:150}..."

  # Check if time is close (within same hour is acceptable due to response time)
  if [ -z "$FRIDAY_TIME" ]; then
    test_result "fail" "Time extraction from answer" "time format HH:MM AM/PM" "no time found"
  elif [ "$SYSTEM_TIME" = "$FRIDAY_TIME" ]; then
    test_result "pass" "Time matches exactly"
  elif echo "$FRIDAY_ANSWER" | grep -q "$SYSTEM_HOUR"; then
    test_result "pass" "Time is in correct hour (close enough)"
  else
    test_result "fail" "Time accuracy" "around $SYSTEM_TIME" "$FRIDAY_TIME"
  fi

  # Check timezone awareness
  if echo "$FRIDAY_ANSWER" | grep -qE "(UTC-3|BRT|Brasília|timezone)"; then
    test_result "pass" "Friday is timezone-aware"
  else
    echo -e "${YELLOW}Note: Friday didn't explicitly mention timezone${NC}"
  fi
fi
echo ""

# Debug info
echo -e "${BLUE}7. System Info:${NC}"
DEBUG_INFO=$(curl -s http://localhost:8080/admin/debug -H "X-API-Key: $API_KEY")
echo "$DEBUG_INFO" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"Vault: {data['vault_path']}\"); print(f\"MD Files: {data['num_md_files']}\"); print(f\"Indexed Chunks: {data['obsidian_chunks']}\"); print(f\"Memory Entries: {data['memory_entries']}\")"

# Validate system info
OBSIDIAN_CHUNKS=$(echo "$DEBUG_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('obsidian_chunks', 0))" 2>/dev/null)
if [ "$OBSIDIAN_CHUNKS" -gt 0 ]; then
  test_result "pass" "Obsidian vault is indexed ($OBSIDIAN_CHUNKS chunks)"
else
  test_result "fail" "Obsidian vault is indexed" ">0 chunks" "$OBSIDIAN_CHUNKS chunks"
fi
echo ""

echo "================================"
echo -e "${BLUE}Test Summary${NC}"
echo "================================"
echo -e "Total Tests:  $TESTS_TOTAL"
echo -e "${GREEN}Passed:       $TESTS_PASSED${NC}"
echo -e "${RED}Failed:       $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo -e "${GREEN}✓ All tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
  exit 1
fi
