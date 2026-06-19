# Velocity Growth & Delivery Intelligence Engine (GDI)
### AI-Powered Seller Operations Copilot

Velocity GDI is a state-of-the-art MVP dashboard designed to help sellers, Key Account Managers (KAMs), and operations teams optimize shipping outcomes. It identifies delivery issues, computes regional/courier inefficiencies, and recommends actions to improve Delivery %, lower RTO %, and optimize overall courier allocations.

---

## 📁 Folder Structure

```
Shipping Ops AI/
├── .venv/                  # Python virtual environment (recommended)
├── data_generator.py       # Python script generating 1,000 shipment records with operational biases
├── app.py                  # Main Streamlit dashboard application
├── requirements.txt        # Project package dependencies
├── shipments.csv           # Generated synthetic shipment dataset (created automatically)
└── README.md               # Setup and execution instructions (this file)
```

---

## ⚡ Setup & Run Instructions

To run the application locally on macOS or any compatible system, follow these steps:

### 1. Create and Activate Virtual Environment
Open your terminal in the project folder and run:
```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate
```

### 2. Install Dependencies
Install the required packages using pip:
```bash
pip install -r requirements.txt
```

### 3. Generate Sample Data
Run the data generator to create the synthetic dataset:
```bash
python3 data_generator.py
```

### 4. Run the Streamlit Dashboard
Launch the dashboard app using Streamlit:
```bash
streamlit run app.py
```

Streamlit will automatically open the dashboard in your default web browser (usually at `http://localhost:8501`).

---

## 🛠 Features

- **Executive Summary Dashboard**: Dynamic health score and operations risk meter (Low / Medium / High).
- **Interactive Filters**: Dynamic filtering by Seller, Shipment Date Range, SKU, and Courier Partner.
- **Top KPIs**: Real-time tracking of Delivery %, RTO %, NDR %, Total Shipments, and Successful Deliveries.
- **Geography Performance**: Top performing states and worst performing states side-by-side with Plotly charts.
- **Courier Intelligence**: Detailed delivery and RTO rates by carrier, including recommended route routing.
- **AI Recommendation Engine**: Automatic checkouts suggesting action playbooks (AI Calling, ATS verification, etc.) with projected impacts.
- **AI Chatbot**: Instant answers to operations questions using rule-based metrics search.
- **Impact Simulator**: Simulate shifting courier loads and payment profiles to see projected delivery improvements and revenue gains.
