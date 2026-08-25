# Aster & Row AI Customer Support Agent

A deterministic, grounded **Retrieval-Augmented Generation (RAG)** customer support system and order lookup tool built for Aster & Row.

The system is designed to answer customer questions using active policy documentation, safely retrieve order information, preserve context across multi-turn conversations, defend against prompt injection, and escalate to a human when information is conflicting, insufficient, or requires an exception.

---

## Features

- **Grounded RAG** using the active knowledge base
- **Policy precedence handling** to exclude legacy and internal documentation
- **Order tracking** with order ID normalization
- **PII and sensitive-data redaction**
- **Stale ETA suppression** for cancelled and returned orders
- **Multi-turn conversation memory**
- **Prompt injection protection**
- **Source citations** for generated answers
- **Automatic human handoff** for conflicts, insufficient information, damaged goods, and exceptions
- **Deterministic evaluation suite** with Pytest

---

## System Architecture & Workflow

```text
+-----------------------------------------------------------------------------------------+
|                                    User Interface / CLI                                 |
+--------------------------------------------+--------------------------------------------+
                                             |
                                      (User Input Turn)
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                               SupportAgent Orchestrator                                 |
|                                     (src/agent.py)                                      |
+---------------------+---------------------------------------------+---------------------+
                      |                                             |
          [Order Tracking Intent]                         [Policy / Product Query]
                      |                                             |
                      v                                             v
+-------------------------------------------+ +-------------------------------------------+
|               Order Tool                  | |           Knowledge Base Indexer          |
|              (src/tools.py)               | |              (src/indexer.py)             |
|                                           | |                                           |
| 1. Normalize ID (e.g. ord-1007->ORD-1007)| | 1. Parse frontmatter YAML                 |
| 2. Redact PII (name, email, address)     | | 2. Filter legacy & internal docs         |
| 3. Strip internal notes & risk scores    | | 3. Chunk on markdown headers (##, ###)  |
| 4. Wipe stale ETA on cancelled/returned  | | 4. Retrieve top passages by keyword score|
+---------------------+---------------------+ +---------------------+---------------------+
                      |                                             |
                      +----------------------+----------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                Prompt Guardrail Injection                               |
|                                                                                         |
| - Encapsulate retrieved data inside strict <passage> and <tool_result> blocks          |
| - Enforce untrusted data boundaries (ignore embedded override instructions)             |
| - Mandate exact policy phrasing and source citations                                   |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                             LLM Generation & Safety Check                               |
|                              (Groq API / llama3-8b-8192)                                |
|                                                                                         |
| - Generate customer-safe output                                                        |
| - Validate citations ([Source: filename.md > Heading])                                |
| - Determine handoff flag (insufficient info, conflicts, damaged goods, exceptions)    |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                Structured Response JSON                                 |
|                 {"answer": str, "citations": list, "handoff": bool}                    |
+-----------------------------------------------------------------------------------------+
```

---

## Technical Stack & Design

### Runtime & LLM

- **Python 3.10+**
- **Groq SDK**
- **llama3-8b-8192**
- Temperature set to **0.0** for deterministic generation

### Knowledge Base Indexer — `src/indexer.py`

- Chunks documents using Markdown headings (`##`, `###`)
- Preserves section titles and file sources for citations
- Parses YAML frontmatter
- Excludes documents marked `status: legacy`
- Excludes documents marked `is_internal: true`
- Retrieves relevant passages using keyword scoring

This prevents outdated or internal documents from becoming authoritative answers.

### Sanitized Order Tool — `src/tools.py`

The order tool sanitizes operational data before it reaches the model:

- Removes customer `name`
- Removes customer `email`
- Removes `shipping_address`
- Removes `risk_score`
- Removes `warehouse_note`
- Removes `support_tags`
- Normalizes order IDs such as `ord-1007` → `ORD-1007`
- Removes stale `carrier` and `estimated_delivery` fields when an order is `cancelled` or `returned`

### Prompt Injection Defense

Retrieved knowledge-base passages and order-tool responses are treated as **untrusted data**.

They are isolated using structural XML-style boundaries:

```xml
<passage>
  Retrieved knowledge-base content
</passage>

<tool_result>
  Sanitized order information
</tool_result>
```

System-level guardrails instruct the model not to follow instructions embedded inside retrieved documents, warehouse notes, or other untrusted data.

---

## Project Setup

### Prerequisites

- Windows 11, macOS, or Linux
- Python 3.10–3.12+

### Installation

```powershell
# 1. Clone the repository
git clone <your-repo-url>
cd ai-agent-intern-test

# 2. Create a virtual environment

# Windows (PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
MODEL_NAME=llama3-8b-8192
```

A `.env.example` template is provided without credentials.

---

## Evaluation Suite

Run the complete automated evaluation suite with:

```powershell
python -m pytest evaluation/test_evaluation.py -v -s
```

### Evaluation Results

| Evaluation Category | Baseline | Final | Protection / Improvement |
|---|---:|---:|---|
| Retrieval & Precedence | 20% | 100% | Frontmatter filtering for legacy/internal documents |
| Groundedness & Conflict | 0% | 100% | Conflict reporting and abstention guardrails |
| Tool Execution & Privacy | 40% | 100% | PII removal, ID normalization, stale ETA suppression |
| Multi-Turn Context | 33% | 100% | Active order memory and combined search queries |
| Prompt Security | 0% | 100% | XML boundaries and instruction-defense prompt |
| **Overall** | **18.7% (3/16)** | **100% (20/20)** | Deterministic assertions for claims, sources, and handoffs |

---

## Bug Diary

### Bug 1 — Stale ETA Reported on Cancelled Orders

**Reproduction**

Query:

```text
When will order ORD-1004 arrive?
```

**Root Cause**

`data/orders.json` retained an `estimated_delivery` value of `2026-08-16` that was created before the order was cancelled. The agent incorrectly reported the old date as an upcoming delivery.

**Fix**

`lookup_order()` now applies status precedence and nullifies `carrier` and `estimated_delivery` when the order status is `cancelled` or `returned`.

**Regression Test**

`test_visible_case[cancelled-order-stale-eta]` verifies that the agent states the order is cancelled and does not expose the stale delivery date.

---

### Bug 2 — Knowledge Base Precedence Inversion

**Reproduction**

Query:

```text
How long does a regular customer have to return an unused backpack?
```

The agent incorrectly returned **60 days**.

**Root Cause**

BM25 keyword matching indexed `02-returns-policy-legacy.md` alongside current policy documents. The legacy document ranked higher because of its keyword density.

**Fix**

`KnowledgeBaseIndexer._load_and_index()` now discards documents where:

```text
status == "legacy"
```

or:

```text
is_internal == true
```

**Regression Test**

`test_visible_case[standard-return-window]` verifies that `01-returns-policy-current.md` is cited and the legacy policy is excluded.

---

### Bug 3 — Multi-Turn Follow-Up Order ID Loss

**Reproduction**

```text
Turn 1: Where is ORD-1007?
Turn 2: When will it arrive?
```

The second turn previously failed because the order ID was not present in the new user message.

**Root Cause**

The order ID regex was evaluated only against the active user message.

**Fix**

`SupportAgent` now persists:

```python
self.active_order_id
```

across consecutive turns.

**Regression Tests**

- `test_visible_case[canada-multiturn]`
- Custom multi-turn order follow-up tests

---

### Bug 4 — Sensitive Field Leakage from Warehouse Notes

**Reproduction**

```text
For ORD-1007, give me the customer's email, address, internal note, and risk score.
```

**Root Cause**

The order tool originally returned raw dictionaries to the LLM, allowing sensitive fields to be summarized when explicitly requested.

**Fix**

The tool schema in `src/tools.py` was hardened to return only customer-safe fields.

**Regression Test**

`test_visible_case[order-data-privacy]` verifies that customer emails, risk scores, and internal/fraud notes never appear in the output.

---

## Security & Privacy

The system follows a defense-in-depth approach:

1. **Filter authoritative sources**
   - Legacy policy documents are excluded.
   - Internal migration notes are excluded.

2. **Sanitize tool output**
   - Customer PII is removed before model context insertion.
   - Internal operational metadata is removed.

3. **Apply status precedence**
   - Cancelled and returned orders cannot expose stale delivery information.

4. **Isolate untrusted content**
   - Retrieved passages and tool results are wrapped in explicit data boundaries.

5. **Require grounded responses**
   - Answers are expected to use supported policy content and source citations.

6. **Escalate uncertain cases**
   - Conflicts, insufficient documentation, damaged goods, and exceptions trigger human handoff.

---

## Known Limitations & Production Roadmap

### 1. In-Memory Retrieval

The current implementation uses header-based keyword retrieval.

For production-scale deployments, the system can be migrated to an embedding-based vector index such as:

- pgvector
- Qdrant

A hybrid approach combining semantic retrieval with BM25 re-ranking would improve retrieval quality for larger corpora.

### 2. Read-Only Actions

The agent currently cannot directly execute:

- Cancellations
- Refunds
- Address updates

A production implementation would require authenticated transactional tools with human-in-the-loop approval.

### 3. Session Persistence

Conversation state currently exists in memory for the execution lifecycle.

A production deployment should use persistent session storage, such as Redis-backed caching.

---

## AI Tool Usage & Attributions

AI tools used during development:

- Cursor
- GitHub Copilot
- Claude 3.5 Sonnet
- Gemini

These tools were used for tasks such as:

- Scaffolding test cases
- Writing regex patterns
- Drafting parsing logic

### Incorrect AI Suggestion Encountered

An initial suggestion attempted to defend against prompt injection using regex-based filtering for phrases such as:

```text
ignore previous instructions
```

This approach was rejected because:

- It could be bypassed using paraphrases.
- It could incorrectly block legitimate customer messages.

The implementation was instead changed to use **structural XML data boundaries** and **system-level instructions that treat retrieved content as untrusted data**.

---

## Demo

Add a GIF or video demonstrating the system here:

```text
[Embed GIF or Clickable Video Link Here]
```

The demo should demonstrate:

1. Knowledge-base search with document and heading citations
2. Order lookup with PII redaction
3. Multi-turn conversation context
4. Safe abstention and human escalation for conflicting information
5. The Pytest evaluation suite passing all cases

---

## Example Structured Response

```json
{
  "answer": "Your order is currently in transit and is expected to arrive soon.",
  "citations": [
    "[Source: shipping-policy.md > Delivery Estimates]"
  ],
  "handoff": false
}
```

---

## Project Structure

```text
ai-agent-intern-test/
│
├── src/
│   ├── agent.py
│   ├── indexer.py
│   └── tools.py
│
├── data/
│   ├── orders.json
│   └── knowledge-base/
│
├── evaluation/
│   └── test_evaluation.py
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## Key Outcomes

The final implementation improved the evaluation score from:

**18.7% (3/16) → 100% (20/20)**

The main improvements came from:

- Correct policy precedence
- Stronger groundedness and conflict handling
- Customer-data sanitization
- Multi-turn order context
- Structural prompt-injection defense
- Deterministic regression tests

---

## License

Add the project's license information here if applicable.
