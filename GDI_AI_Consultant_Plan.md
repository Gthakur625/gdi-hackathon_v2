# GDI — AI-Powered Growth & Delivery Consultant
## Hackathon Enhancement Blueprint

> **Objective:** Transform the existing WIP GDI dashboard into an AI consultant that proactively diagnoses delivery problems, recommends actions, and drives VAS adoption — so sellers spend zero time on manual analysis.

---

## 1. What the WIP Already Has (Don't Rebuild)

| Module | Current State |
|---|---|
| KPI Cards | Delivery %, RTO %, NDR %, Shipment count, Opportunity score |
| AI Root Cause Analysis | 3 hardcoded anomaly cards (State, Courier, COD) |
| Geographic Intelligence | Top/Worst state bar charts + dataframes |
| Courier Intelligence | Performance table + best courier badge |
| Recommendation Engine | 4 rule-based playbooks (Courier, Address, Calling, WhatsApp) |
| Chat Assistant | Rule-based keyword matching on 4 questions |
| Impact Simulator | Sliders for ATS %, COD conversion, AI Calling toggle |
| Data Layer | `data_generator.py` (1000 synthetic records, 5 sellers, 4 couriers) |
| UI Theme | Dark SaaS (Outfit font, indigo/purple gradient, #0B0F19 background) |

---

## 2. Updated Product Architecture

### 2.1 From Monolith → Modular Multi-Page Streamlit

```
gdi/
├── app.py                          # Main router + sidebar nav
├── data_generator.py               # ENHANCE: add VAS fields, SKU returns, caller data
├── utils/
│   ├── styles.py                   # Extract CSS from app.py (no logic change)
│   ├── metrics.py                  # Shared KPI computation functions
│   └── ai_engine.py               # Rule engine + LLM prompt wrapper (if API key present)
└── modules/
    ├── seller_health.py            # NEW: Seller Health Score
    ├── root_cause.py               # ENHANCE: deeper pattern detection
    ├── sku_intelligence.py         # NEW: SKU-level delivery + RTO analysis
    ├── ats_engine.py               # ENHANCE: VAS product mapping + adoption score
    ├── ai_calling.py               # NEW: NDR shipment prioritization for calling
    ├── whatsapp_ndr.py             # NEW: WhatsApp NDR engagement queue
    ├── chat_assistant.py           # ENHANCE: context-aware, data-grounded answers
    └── impact_simulator.py         # ENHANCE: VAS-linked sliders, revenue model
```

### 2.2 Navigation Design (Sidebar)

```
⚡ GDI Consultant
──────────────────
🏠  Executive Summary        ← existing header + KPIs (keep as landing page)
❤️  Seller Health Score       ← NEW
🔍  Root Cause Analysis       ← ENHANCE
📦  SKU Intelligence          ← NEW
🚀  ATS Recommendation        ← ENHANCE
📞  AI Calling Engine         ← NEW
💬  WhatsApp NDR Engine       ← NEW
🤖  AI Chat Assistant         ← ENHANCE (full page)
📊  Delivery Impact Simulator ← ENHANCE
```

### 2.3 Data Layer Additions (`data_generator.py`)

Add the following columns to the synthetic dataset:

| New Column | Purpose |
|---|---|
| `attempt_count` | 1–3 delivery attempts (drives AI Calling priority) |
| `buyer_phone_verified` | Bool — for AI Calling engine |
| `ndr_reason` | "Not Available", "Wrong Address", "Refused", "Future Request" |
| `vas_active` | List of VAS products active for this seller |
| `sku_return_rate` | Pre-computed per-SKU return rate |
| `sku_category` | "Electronics", "Apparel", "Wellness", "General" |
| `whatsapp_opt_in` | Bool — buyer WhatsApp consent |
| `calling_attempted` | Bool — AI calling already triggered |

---

## 3. Module Specifications & Screen Designs

---

### MODULE 1: Seller Health Score

**Purpose:** Give the seller a single, actionable number they can act on immediately — not a collection of charts they need to interpret.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ❤️ Your Seller Health Score                           │
│                                                         │
│  ┌──────────────┐  ┌─────────────────────────────────┐ │
│  │  GAUGE CHART │  │  "Your score dropped 8 points   │ │
│  │              │  │   this week. Bihar RTO and       │ │
│  │    67/100    │  │   Nimbus underperformance are    │ │
│  │  ⚠️ MED RISK │  │   the key drivers."             │ │
│  └──────────────┘  └─────────────────────────────────┘ │
│                                                         │
│  Score Breakdown (5 Dimensions):                        │
│  ┌─────────────┬──────────────┬──────────────┬───────┐ │
│  │ Dimension   │ Your Score   │ Benchmark    │ Delta │ │
│  ├─────────────┼──────────────┼──────────────┼───────┤ │
│  │ Delivery %  │ 63% → 26/40  │ 85% → 34/40  │ -8   │ │
│  │ RTO Rate    │ 28% → 12/25  │ 12% → 22/25  │ -10  │ │
│  │ NDR Rate    │ 18% → 7/20   │ 8% → 16/20   │ -9   │ │
│  │ COD Ratio   │ 71% → 7/10   │ 50% → 10/10  │ -3   │ │
│  │ VAS Adoption│ 1/4 VAS → 5/5│ 3/4 → 4/5    │ -4   │ │
│  └─────────────┴──────────────┴──────────────┴───────┘ │
│                                                         │
│  Weekly Trend (Sparkline: last 4 weeks)                 │
│  75 → 71 → 69 → 67  ▼ Declining                        │
└─────────────────────────────────────────────────────────┘
```

**Scoring Formula:**
```python
health_score = (
    delivery_pct * 0.40 +          # 40 pts max
    (100 - rto_pct) * 0.25 +       # 25 pts max
    (100 - ndr_pct) * 0.20 +       # 20 pts max
    (100 - cod_pct) * 0.10 +       # 10 pts max
    vas_adoption_score * 0.05       # 5 pts max
)
```

**Key UX Shift:** The page opens with a plain-language verdict: _"Your delivery health is declining. 3 specific fixes can recover 8 points this week."_ — not a dashboard the seller has to interpret.

---

### MODULE 2: AI Root Cause Analysis

**Purpose:** Automatically surface *why* delivery is failing — not just *that* it is failing.

**Enhancement over WIP:** Current WIP has 3 static cards. Enhance to dynamic pattern detection with drill-down and remediation steps.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  🔍 AI Diagnosis — 4 Anomalies Detected                │
│  "GDI scanned 1,000 shipments. Here's what's wrong."   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🔴 CRITICAL  Geographic RTO Cluster              │  │
│  │ Bihar accounts for 31% of RTOs (189 shipments).  │  │
│  │ Root Cause: Address quality + COD non-acceptance  │  │
│  │ Fix: Enable ATS Address Verification for Bihar    │  │
│  │ [See Bihar Shipments ▶]                           │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🟡 WARNING   Courier Allocation Mismatch         │  │
│  │ 25% volume on Nimbus but it delivers only 61%.   │  │
│  │ Root Cause: No smart routing rules in place       │  │
│  │ Fix: Shift Nimbus share to ATS for these pincodes │  │
│  │ [See Affected Shipments ▶]                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🟡 WARNING   COD Concentration Risk              │  │
│  │ 71% COD share with 29% COD RTO rate.             │  │
│  │ Root Cause: No prepaid nudge at checkout          │  │
│  │ Fix: Add 5% prepaid discount using Velocity tools │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🔵 INFO      NDR Unresolved Queue Growing        │  │
│  │ 142 NDRs unresolved > 48 hours. Escalation risk. │  │
│  │ Fix: Activate AI Calling for these shipments now  │  │
│  │ [Launch AI Calling ▶]                             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**New Detection Patterns:**
- NDR age > 48 hours (unresolved queue alert)
- SKU category with RTO > 2x average (Electronics spike)
- Single state contributing > 25% of RTOs (geographic cluster)
- Courier with < 70% delivery and > 15% allocation (misallocation)
- COD > 70% AND COD-RTO > 25% (COD concentration)

---

### MODULE 3: SKU Intelligence

**Purpose:** Answer "Which SKU is underperforming?" — the #1 seller question that currently requires manual analysis.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  📦 SKU Intelligence — Product-Level Delivery Analysis  │
│                                                         │
│  Summary Chips:                                         │
│  [16 SKUs analyzed] [3 Critical] [2 Improving] [11 OK] │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ CRITICAL SKUs  (RTO > 30%)                       │   │
│  │                                                   │   │
│  │ SKU-ELC-51  Wireless Keyboard  RTO 38% ⚠         │   │
│  │  → Reason: Electronics + Bihar concentration     │   │
│  │  → Action: Restrict Bihar COD for this SKU       │   │
│  │                                                   │   │
│  │ SKU-FSH-10  Smart Watch V2     RTO 33% ⚠         │   │
│  │  → Reason: High value + Nimbus courier            │   │
│  │  → Action: Force ATS routing for this SKU        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Full SKU Performance Table (sortable):                 │
│  SKU | Product | Shipments | Delivery% | RTO% | Revenue │
│  + Scatter Plot: Delivery% vs Order Value               │
└─────────────────────────────────────────────────────────┘
```

**Metrics per SKU:**
- Delivery %, RTO %, NDR %
- Revenue at risk (RTO shipments × avg order value)
- Category-level benchmark comparison
- Recommended action per SKU (rule-based)

---

### MODULE 4: ATS Recommendation Engine

**Purpose:** Map seller's specific pain points to Velocity VAS products. Drive adoption with data-backed ROI.

**VAS Product Catalog (for recommendation logic):**

| VAS Product | Trigger Condition | Impact Claim |
|---|---|---|
| ATS Address Verification | RTO > 20% OR Bihar/UP share > 30% | Reduces RTO by 4–6% |
| ATS AI Calling Suite | NDR > 15% OR unresolved NDR > 48h | Recovers 35–40% of NDRs |
| ATS WhatsApp NDR | COD > 60% AND NDR > 10% | Reduces COD RTO by 8% |
| ATS Secure (Prepaid Push) | COD > 70% | Converts 15–20% COD to Prepaid |
| ATS Smart Routing | Courier score variance > 20% | Improves delivery by 3–5% |

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  🚀 Your Personalized VAS Adoption Plan                 │
│  "Based on your data, 3 VAS products will solve 80%    │
│   of your delivery problems."                           │
│                                                         │
│  ┌─────────────────────────────────────────┐           │
│  │ #1 HIGHEST IMPACT                        │           │
│  │ 🎯 ATS AI Calling Suite                  │           │
│  │ Your NDR rate: 18% (benchmark: 8%)       │           │
│  │ 142 shipments at risk right now          │           │
│  │ Estimated recovery: +47 deliveries/week  │           │
│  │ Revenue unlock: ₹84,600                  │           │
│  │ [Activate Now] [See Demo]                │           │
│  └─────────────────────────────────────────┘           │
│                                                         │
│  ┌─────────────────────────────────────────┐           │
│  │ #2 ATS Address Verification              │           │
│  │ Bihar causing 31% of RTOs → Fix at source│           │
│  │ [Activate Now]                           │           │
│  └─────────────────────────────────────────┘           │
│                                                         │
│  ┌─────────────────────────────────────────┐           │
│  │ ✅ ALREADY ACTIVE  ATS Core Routing      │           │
│  │ Saving you ~12% vs Nimbus baseline       │           │
│  └─────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

---

### MODULE 5: AI Calling Recommendation Engine

**Purpose:** Tell the seller exactly *which* shipments to call, in what priority order, and with what script.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  📞 AI Calling Engine — NDR Recovery Queue              │
│                                                         │
│  Queue Summary:                                         │
│  [142 NDR Shipments] [47 High Priority] [₹2.4L at risk]│
│                                                         │
│  Priority Queue (Auto-ranked by recovery probability):  │
│  ┌───────┬─────────────┬─────────┬───────┬──────────┐  │
│  │ AWB   │ Buyer State │ NDR Age │ Reason│ Recovery%│  │
│  ├───────┼─────────────┼─────────┼───────┼──────────┤  │
│  │ AWB01 │ Maharashtra │ 24h     │ Absent│ 89%      │  │
│  │ AWB02 │ Karnataka   │ 18h     │ Absent│ 84%      │  │
│  │ AWB03 │ Delhi       │ 36h     │ Future│ 78%      │  │
│  │ AWB04 │ Bihar       │ 12h     │ Wrong │ 41%      │  │
│  └───────┴─────────────┴─────────┴───────┴──────────┘  │
│                                                         │
│  💬 Suggested Calling Script (context-aware):           │
│  "Hello, this is regarding your order AWB01.            │
│   We attempted delivery but you were unavailable.       │
│   Can we schedule for tomorrow between 2–5 PM?"         │
│                                                         │
│  [Export Priority List as CSV]  [Mark as Called]        │
└─────────────────────────────────────────────────────────┘
```

**Recovery Probability Algorithm:**
```python
# High recovery (>70%): Metro state + Absent/Future reason + <48h age
# Medium recovery (40-70%): Tier-2 state + any reason + <72h age
# Low recovery (<40%): Bihar/UP + Wrong Address reason + >72h age
recovery_score = (
    state_recovery_weight[state] * 0.4 +
    ndr_reason_weight[ndr_reason] * 0.35 +
    age_decay_factor(attempt_count, ndr_age_hours) * 0.25
)
```

---

### MODULE 6: WhatsApp NDR Recommendation Engine

**Purpose:** Identify COD shipments best suited for WhatsApp engagement to prevent RTO.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  💬 WhatsApp NDR Engine                                 │
│                                                         │
│  Engagement Funnel:                                     │
│  Sent: 89 → Delivered: 76 → Read: 61 → Replied: 38    │
│  Deliveries Saved: 29  |  Revenue Recovered: ₹52,100   │
│                                                         │
│  WhatsApp Queue (COD NDR shipments, opt-in buyers):     │
│  ┌───────┬──────────┬────────┬───────┬──────────────┐  │
│  │ AWB   │ State    │ Value  │Status │ Template     │  │
│  ├───────┼──────────┼────────┼───────┼──────────────┤  │
│  │ AWB05 │ Gujarat  │ ₹1,499 │Pending│ "Redelivery" │  │
│  │ AWB06 │ Haryana  │ ₹2,999 │Sent   │ "Confirm"    │  │
│  └───────┴──────────┴────────┴───────┴──────────────┘  │
│                                                         │
│  Template Preview:                                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 📦 Velocity Express                              │  │
│  │ Hi! Your order (₹1,499) couldn't be delivered.   │  │
│  │ Reply:                                            │  │
│  │ 1️⃣ Reschedule  2️⃣ Change Address  3️⃣ Cancel   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Eligibility Filters:**
- `delivery_status == "NDR"`
- `payment_type == "COD"`
- `whatsapp_opt_in == True`
- `attempt_count < 3`
- Exclude Wrong Address NDRs (send to calling instead)

---

### MODULE 7: AI Chat Assistant (Full Page Enhancement)

**Purpose:** Replace the rule-based keyword matching with a data-grounded conversational interface. Every answer cites actual numbers from the loaded dataset.

**Enhancement over WIP:** WIP matches 4 keywords. Enhanced version handles 15+ question patterns with dynamic data injection and suggested follow-ups.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  🤖 GDI AI Consultant                                   │
│  "Ask me anything about your delivery operations"       │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Quick Questions:                                  │  │
│  │ [Why is delivery dropping?] [Which courier?]      │  │
│  │ [Which SKU is failing?] [Which state has RTO?]    │  │
│  │ [Which VAS should I adopt?] [How much can I save?]│  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  🤖 GDI: Good morning! I've analyzed your 1,000       │
│     shipments. Your biggest issue right now is Bihar    │
│     — 31% of your RTOs come from there. Want me to     │
│     show you exactly which shipments and what to do?   │
│                                                         │
│  👤 Which SKU is underperforming?                       │
│                                                         │
│  🤖 GDI: SKU-ELC-51 (Wireless Keyboard) has the worst │
│     RTO rate at 38% — that's 2.3x your average.        │
│     Primary driver: 67% of these are COD + Bihar.      │
│     Recommendation: Restrict Bihar COD for this SKU.   │
│     This alone could save 23 shipments/week.           │
│                                                         │
│  [Follow-up: How do I fix SKU-ELC-51?]                 │
│  [Follow-up: Show me Bihar analysis]                    │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Type your question...                    [Send]   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Enhanced Q&A Coverage:**
| Question Pattern | Data Used | Answer Type |
|---|---|---|
| Why is delivery dropping? | delivery_pct, state RTO, courier gap | Multi-factor diagnosis |
| Which courier should I use? | courier_perf table | Ranked recommendation |
| Which SKU is underperforming? | sku_perf table | Named SKU + reason |
| Which state is causing RTO? | state RTO counts | Top 3 states + % |
| Which VAS should I adopt? | rec_list + health score | Ranked VAS plan |
| How much can I save? | impact_simulator values | Revenue calculation |
| What's my health score? | health_score breakdown | Score + 3 fixes |
| Show me NDR shipments | ndr_df filtered | Count + priority |
| What's my COD risk? | cod_rto_pct | COD analysis |
| How do I reduce RTO? | rto patterns | Step-by-step plan |

---

### MODULE 8: Delivery Impact Simulator (Enhanced)

**Enhancement over WIP:** Add VAS-specific sliders, revenue model per VAS, and a "What if I adopt all recommended VAS?" one-click scenario.

**New Sliders:**
```
Current WIP:
  [ATS Allocation %]
  [COD to Prepaid %]
  [AI Calling Toggle]

Enhanced:
  [ATS Allocation %]              ← keep
  [COD to Prepaid %]              ← keep
  [ATS Address Verification ON]   ← NEW (reduces Bihar/UP RTO by 5%)
  [AI Calling — NDR Recovery %]   ← change from toggle to slider (0-40%)
  [WhatsApp NDR ON]               ← NEW (reduces COD RTO by 8%)
  [ATS Smart Routing ON]          ← NEW (improves low-performer pincodes by 3%)

  [⚡ Apply All Recommendations]  ← NEW one-click button
```

**Revenue Model:**
```
Revenue Saved = Additional Deliveries × Avg Order Value
Revenue at Risk (Current) = RTO Shipments × Avg Order Value × 0.15 (logistics cost)
Net Impact = Revenue Saved + Logistics Cost Avoided
```

---

## 4. Component-Level Changes from Current WIP

### KEEP (zero changes needed)
- All CSS styling in `st.markdown()` blocks — perfect as-is
- `data_generator.py` structure — add columns, don't rewrite
- `.streamlit/config.toml` — keep dark theme
- KPI Cards section — already good
- Sidebar file upload + MIS parsing (`parse_uploaded_mis`)
- Sidebar filters (seller, date, product, SKU, courier)

### ENHANCE (modify existing code)

**`app.py` → `modules/root_cause.py`**
- Add 2 new anomaly patterns: NDR age > 48h, SKU category spike
- Add expandable drill-down per anomaly (`st.expander`)
- Add "Take Action" button that deep-links to relevant module

**Chat Assistant block in `app.py` → `modules/chat_assistant.py`**
- Expand `generate_bot_reply()` from 4 patterns → 10+ patterns
- Add dynamic follow-up suggestion chips after each answer
- Add proactive opening message based on current data state
- Add SKU-specific and VAS-specific Q&A branches

**Impact Simulator block → `modules/impact_simulator.py`**
- Add 3 new sliders (Address Verification, WhatsApp NDR, Smart Routing)
- Add "Apply All Recommended" one-click preset
- Add per-VAS revenue breakdown table
- Add net revenue impact (not just delivery count)

**Recommendation Engine block → `modules/ats_engine.py`**
- Add VAS product catalog with activation CTAs
- Add "Already Active" state for adopted VAS
- Add ROI calculation per VAS recommendation
- Rank recommendations by estimated impact

### ADD (new code)

**`modules/seller_health.py`** (~80 lines)
- Gauge chart using Plotly `go.Indicator`
- 5-dimension score breakdown table
- Weekly trend sparkline (computed from date-partitioned data)
- Plain-language verdict string

**`modules/sku_intelligence.py`** (~100 lines)
- Group `df_filtered` by `sku` + `product_name`
- Compute delivery%, RTO%, revenue at risk per SKU
- Flag Critical/Warning/OK using thresholds
- Scatter plot: delivery% vs order value (Plotly)
- Sortable dataframe with conditional formatting

**`modules/ai_calling.py`** (~90 lines)
- Filter `df_filtered` for NDR shipments
- Compute recovery probability per shipment
- Sort by recovery probability descending
- Display priority queue as styled dataframe
- Export as CSV button
- Context-aware calling script generator

**`modules/whatsapp_ndr.py`** (~80 lines)
- Filter for COD + NDR + whatsapp_opt_in
- Funnel chart: Sent → Delivered → Read → Replied → Saved
- Display engagement queue
- Template preview renderer (HTML card)

**`utils/metrics.py`** (~60 lines)
- Extract shared metric functions: `calc_health_score()`, `calc_sku_perf()`, `calc_courier_perf()`, `calc_state_perf()`
- Used by multiple modules to avoid re-computation

---

## 5. Hackathon MVP Scope (2–3 Day Build)

### Day 1 — Foundation + Core Intelligence (8 hours)

**Goal:** The app tells sellers what's wrong without them asking.

| Task | File | Time |
|---|---|---|
| Refactor `app.py` to multi-page with `st.navigation()` or tabs | `app.py` | 1h |
| Extract CSS to `utils/styles.py`, metrics to `utils/metrics.py` | `utils/` | 1h |
| Enhance `data_generator.py` — add `attempt_count`, `ndr_reason`, `whatsapp_opt_in`, `sku_category` | `data_generator.py` | 1h |
| Build `modules/seller_health.py` — gauge + 5-dimension table + verdict | `seller_health.py` | 2h |
| Enhance root cause analysis — add 2 patterns + drill-down expanders | `root_cause.py` | 1.5h |
| Integration test: all existing modules still render correctly | — | 1.5h |

**Demo-able by end of Day 1:** Health Score page + enhanced root cause

---

### Day 2 — SKU + VAS Recommendation Stack (8 hours)

**Goal:** Sellers can identify their worst products and get told exactly which VAS to buy.

| Task | File | Time |
|---|---|---|
| Build `modules/sku_intelligence.py` — performance table + scatter + critical flags | `sku_intelligence.py` | 2h |
| Enhance `modules/ats_engine.py` — VAS catalog + ROI + ranked plan + activation CTAs | `ats_engine.py` | 2h |
| Build `modules/ai_calling.py` — priority queue + recovery score + script | `ai_calling.py` | 2h |
| Build `modules/whatsapp_ndr.py` — funnel + queue + template preview | `whatsapp_ndr.py` | 2h |

**Demo-able by end of Day 2:** Full VAS adoption flow — from diagnosis to specific product recommendation to calling queue

---

### Day 3 — Chat + Simulator Polish + Demo Prep (6 hours)

**Goal:** The app feels like talking to a consultant, not reading a dashboard.

| Task | File | Time |
|---|---|---|
| Expand chat to 10+ Q&A patterns + follow-up chips + proactive opening | `chat_assistant.py` | 2h |
| Add 3 new sliders + "Apply All" button + revenue breakdown to simulator | `impact_simulator.py` | 1.5h |
| UI polish: consistent section headers, loading spinners, empty state messages | all modules | 1h |
| Prepare hackathon demo data: curated `shipments.csv` that shows all anomalies clearly | `data_generator.py` | 0.5h |
| End-to-end demo run + bug fixes | — | 1h |

**Demo-able by end of Day 3:** Full AI consultant flow from health score → diagnosis → SKU → VAS → calling queue → chat

---

## 6. Hackathon Demo Script (3-Minute Flow)

```
1. [0:00] Open app → Health Score: 67/100, Medium Risk
   "GDI scanned 1,000 shipments and gave you a score. Let's see why."

2. [0:30] Root Cause Analysis → Bihar RTO cluster + Nimbus underperformance
   "GDI found 4 anomalies automatically. No manual analysis."

3. [1:00] SKU Intelligence → SKU-ELC-51 flagged at 38% RTO
   "Which product is hurting you most? GDI tells you in one click."

4. [1:30] ATS Recommendation → 3 VAS ranked by impact
   "GDI maps your exact problem to the exact Velocity product that fixes it."

5. [2:00] AI Calling Engine → 47 shipments queued with recovery scores
   "Not just 'use AI calling' — GDI tells you which 47 shipments, in order."

6. [2:30] Chat: "Which VAS should I adopt?"
   "GDI: Based on your data, activate ATS Calling first. It recovers 47 shipments worth ₹84,600."

7. [2:50] Impact Simulator → Apply All Recommended → +11% delivery, ₹1.8L revenue unlock
   "This is what 3 VAS products do to your numbers."
```

---

## 7. Technical Notes

### No LLM Dependency for MVP
All intelligence is rule-based using computed metrics. The chat assistant uses pattern matching + data injection. This ensures the demo works 100% reliably without API keys or latency.

### Optional LLM Enhancement (if time permits)
```python
# utils/ai_engine.py
import anthropic

def get_llm_insight(question, context_data):
    client = anthropic.Anthropic()
    prompt = f"""
    You are a shipping operations consultant for Indian e-commerce sellers.
    
    Seller data:
    - Delivery rate: {context_data['delivery_pct']:.1f}%
    - RTO rate: {context_data['rto_pct']:.1f}%
    - Worst state: {context_data['worst_state']}
    - Best courier: {context_data['best_courier']}
    
    Question: {question}
    
    Answer in 2-3 sentences. Be specific with numbers. End with one clear action.
    """
    # Wrap in try/except — fall back to rule-based if API fails
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except:
        return generate_rule_based_reply(question, context_data)
```

### Streamlit Multi-Page Setup
```python
# app.py
import streamlit as st

pg = st.navigation([
    st.Page("modules/seller_health.py", title="Seller Health Score", icon="❤️"),
    st.Page("modules/root_cause.py", title="Root Cause Analysis", icon="🔍"),
    st.Page("modules/sku_intelligence.py", title="SKU Intelligence", icon="📦"),
    st.Page("modules/ats_engine.py", title="ATS Recommendations", icon="🚀"),
    st.Page("modules/ai_calling.py", title="AI Calling Engine", icon="📞"),
    st.Page("modules/whatsapp_ndr.py", title="WhatsApp NDR", icon="💬"),
    st.Page("modules/chat_assistant.py", title="AI Chat Assistant", icon="🤖"),
    st.Page("modules/impact_simulator.py", title="Impact Simulator", icon="📊"),
])
pg.run()
```

---

## 8. Success Criteria for Hackathon

| Criterion | Target |
|---|---|
| Time to first insight | < 30 seconds after data upload |
| Questions answerable by chat | 10+ |
| VAS products mapped to seller pain | 3–5 specific recommendations |
| Revenue impact visible | ₹ number on simulator page |
| Manual analysis eliminated | 100% — GDI surfaces all issues proactively |
| Demo flow | < 3 minutes, zero dead ends |

---

*Built on existing GDI WIP — Velocity Hackathon 2025*
