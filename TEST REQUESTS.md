# Setup

1. pip install -r requirements.txt
2. export GROQ_API_KEY="your_key_here"   (get a free key at https://console.groq.com)
3. uvicorn main:app --reload --port 8000

# Test 1 — Standard business request

curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Create meeting minutes for our weekly engineering standup. Attendees were Priya, Arjun and Neha. We discussed sprint progress, a bug in the payment module, and next sprint planning."}'

# Test 2 — Complex / ambiguous / conflicting request

curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "We need a proposal for a new client but I havent decided if this is a fixed-price or time-and-materials project yet, the client wants it delivered in 2 weeks but our team says 6 weeks minimum, and we dont have a budget number finalized. Just put something together."}'

Notes for the video:
- Test 1 shows straightforward multi-step planning + document generation.
- Test 2 forces the agent to state explicit assumptions (e.g., choosing a
  hybrid pricing model, proposing a phased timeline reconciling 2 vs 6 weeks,
  inserting a placeholder budget range) — this is the "autonomous
  decision-making under ambiguity" part the assignment is testing.
- Both responses include the full task_list (the agent's self-generated
  TODO list) and a download_url for the final .docx.
- Open the generated docx to show the "Assumptions Made by the Agent" section
  and the "Agent Execution Log" table at the end — these make the autonomy
  visible to a reviewer.