"""Generate a high-quality PDF version of the presentation using reportlab."""
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import (Color, HexColor, white, black)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "JAGGU_AI_Hackathon_Presentation.pdf")

W, H = 13.33*inch, 7.5*inch
PAGE = (W, H)

# Brand colours
DARK   = HexColor("#0B0F19")
PURPLE = HexColor("#4F46E5")
BRIGHT = HexColor("#7C3AED")
LIGHT  = HexColor("#C084FC")
GREEN  = HexColor("#34D399")
AMBER  = HexColor("#FBBF24")
RED    = HexColor("#F87171")
LGREY  = HexColor("#D1D5DB")
MGREY  = HexColor("#9CA3AF")
CARD   = HexColor("#111827")
LINE   = HexColor("#1F2937")
WHITE  = white

def rect(c, x, y, w, h, fill, stroke=None, sw=0.5):
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke); c.setLineWidth(sw)
    else:
        c.setStrokeColor(fill)
    c.roundRect(x*inch, y*inch, w*inch, h*inch, 6, fill=1, stroke=1 if stroke else 0)

def txt(c, text, x, y, size=12, color=WHITE, bold=False, align="L"):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    px = x*inch
    if align == "C":
        c.drawCentredString(px, y*inch, text)
    elif align == "R":
        c.drawRightString(px, y*inch, text)
    else:
        c.drawString(px, y*inch, text)

def bg(c):
    c.setFillColor(DARK); c.rect(0, 0, W, H, fill=1, stroke=0)

def bar(c, y, h=0.06, col=PURPLE):
    c.setFillColor(col); c.rect(0, y*inch, W, h*inch, fill=1, stroke=0)

def slide_num(c, n):
    txt(c, f"0{n} / 05", 12.7, 7.15, 9, MGREY, align="R")

def watermark(c):
    txt(c, "VELOCITY GDI", 0.35, 0.2, 8, MGREY)
    txt(c, "Confidential · Hackathon Demo 2026", 12.9, 0.2, 8, MGREY, align="R")

def card_rect(c, x, y, w, h, border=PURPLE):
    c.setFillColor(CARD); c.setStrokeColor(border); c.setLineWidth(0.8)
    c.roundRect(x*inch, y*inch, w*inch, h*inch, 6, fill=1, stroke=1)

def pill_box(c, text, x, y, w=4.8, h=0.36, fill=PURPLE, size=12):
    c.setFillColor(fill); c.setStrokeColor(fill)
    c.roundRect(x*inch, y*inch, w*inch, h*inch, 10, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", size)
    c.drawCentredString((x+w/2)*inch, (y+0.1)*inch, text)


c = canvas.Canvas(OUT, pagesize=PAGE)
c.setTitle("JAGGU AI — Hackathon Presentation")
c.setAuthor("Velocity Shipping · GDI Team")
c.setSubject("AI KAM & Operations Expert")


# ── SLIDE 1 ───────────────────────────────────────────────────────────────────
bg(c); bar(c, 7.44, col=PURPLE); bar(c, 0, col=BRIGHT); slide_num(c, 1)
txt(c, "The Problem", 0.5, 6.55, 36, WHITE, bold=True)
txt(c, "D2C Brands Lose Revenue Due to Failed Deliveries", 0.5, 6.1, 15, LIGHT)

# Left card
card_rect(c, 0.4, 1.3, 3.8, 4.55, border=PURPLE)
txt(c, "Key Challenges", 0.6, 5.52, 12, AMBER, bold=True)
chs = ["High RTO (Return to Origin)","High NDR (Non-Delivery)",
       "Customer Unreachable","Courier Underperformance",
       "Poor Courier Allocation","Lack of Operational Visibility","Manual Analysis"]
for i,ch in enumerate(chs):
    txt(c, f"  ✗  {ch}", 0.6, 5.12-i*0.33, 11, LGREY)

# Middle card
card_rect(c, 4.4, 1.3, 4.2, 4.55, border=RED)
txt(c, "Business Impact", 4.6, 5.52, 12, RED, bold=True)
txt(c, "Example Seller", 4.6, 5.18, 10, MGREY, bold=True)
txt(c, "10,000 Orders / Month", 4.6, 4.82, 13, WHITE, bold=True)
txt(c, "Delivery Rate:", 4.6, 4.45, 10, MGREY)
txt(c, "65%", 4.6, 3.85, 36, AMBER, bold=True)
txt(c, "Orders Failed:", 4.6, 3.5, 10, MGREY)
txt(c, "3,500", 4.6, 2.9, 36, RED, bold=True)

# Right card — failure chain
card_rect(c, 8.8, 1.3, 4.1, 4.55, border=BRIGHT)
txt(c, "The Failure Chain", 9.0, 5.52, 12, LIGHT, bold=True)
flow = [("📦 Order Placed", WHITE), ("🚚 Dispatched", LGREY),
        ("⚠️  NDR", AMBER),         ("🔄 Reattempt", LGREY),
        ("❌ RTO", RED),             ("💸 Revenue Loss", RED)]
fy = 5.05
for label, col in flow:
    txt(c, label, 9.1, fy, 11, col, bold=True)
    if label != "💸 Revenue Loss":
        txt(c, "↓", 10.4, fy-0.18, 10, MGREY, align="C")
    fy -= 0.62

watermark(c); c.showPage()


# ── SLIDE 2 ───────────────────────────────────────────────────────────────────
bg(c); bar(c, 7.44, col=PURPLE); bar(c, 0, col=BRIGHT); slide_num(c, 2)
# Hero area
c.setFillColor(HexColor("#0F0A1E")); c.rect(0, H-1.6*inch, W, 1.6*inch, fill=1, stroke=0)
txt(c, "🤖  JAGGU AI", 0.4, 6.5, 42, WHITE, bold=True)
txt(c, "Powered by Velocity GDI — Growth & Delivery Intelligence", 0.4, 5.92, 14, LIGHT)
pill_box(c, "Your AI KAM & Operations Expert", 0.4, 5.5, 5.2, 0.36, PURPLE, 12)

# Not a dashboard card
card_rect(c, 0.4, 3.85, 5.2, 1.48, border=BRIGHT)
txt(c, "Not a Dashboard.  Not a Chatbot.", 0.6, 5.0, 15, AMBER, bold=True)
txt(c, "An AI Growth & Delivery Consultant.", 0.6, 4.6, 13, WHITE)
txt(c, "JAGGU gives proactive, personalised insights — not reports.", 0.6, 4.2, 10, LGREY)

# 6 capability cards
caps = [("📊","Delivery Intel",PURPLE),("🚚","Courier Intel",BRIGHT),
        ("📦","Product Intel",GREEN), ("📍","Pincode Intel",RED),
        ("⚙️","VAS Engine",  LIGHT), ("💡","Ops Intel",   AMBER)]
cx = 0.4
for i,(icon,lbl,col) in enumerate(caps):
    bx = cx + i*(2.05+0.07)
    card_rect(c, bx, 2.55, 2.05, 1.15, border=col)
    txt(c, icon, bx+1.025, 3.35, 18, col, align="C")
    txt(c, lbl, bx+1.025, 2.8, 10, WHITE, bold=True, align="C")

# Arrow flow bottom
txt(c, "HOW JAGGU WORKS", 6.665, 2.1, 9, MGREY, bold=True, align="C")
flow2 = ["Diagnose","Recommend","Optimize","Deliver"]
fx = 1.5; fw = 2.3
for i, step in enumerate(flow2):
    card_rect(c, fx, 1.28, fw, 0.62, border=BRIGHT)
    txt(c, step, fx+fw/2, 1.52, 13, WHITE, bold=True, align="C")
    if i < 3:
        txt(c, "→", fx+fw+0.07, 1.52, 16, LIGHT, align="C")
    fx += fw + 0.35

watermark(c); c.showPage()


# ── SLIDE 3 ───────────────────────────────────────────────────────────────────
bg(c); bar(c, 7.44, col=BRIGHT); bar(c, 0, col=PURPLE); slide_num(c, 3)
txt(c, "How JAGGU Works", 0.5, 6.6, 34, WHITE, bold=True)
txt(c, "From raw shipment data to actionable intelligence in seconds", 0.5, 6.18, 13, LIGHT)

# Pipeline
card_rect(c, 0.4, 1.2, 2.8, 4.85, border=PURPLE)
txt(c, "DATA PIPELINE", 0.65, 5.75, 9, MGREY, bold=True)
pipe = [("📂","Seller Data",WHITE),("⚡","Velocity GDI",LIGHT),
        ("🤖","JAGGU AI",GREEN),    ("🔍","Root Cause",AMBER),
        ("✅","Recommendations",GREEN),("📈","Improved Delivery %",WHITE)]
py = 5.3
for icon, lbl, col in pipe:
    txt(c, f"{icon}  {lbl}", 0.6, py, 11, col, bold=True)
    if lbl != "Improved Delivery %":
        txt(c, "↓", 1.9, py-0.2, 9, MGREY, align="C")
    py -= 0.65

# Modules
modules = [
    ("❤️  Seller Health Score","Health Score 0–100 · Benchmark comparison · Risk flags",GREEN),
    ("🚚  Courier Intelligence","Delivery rate by courier · Allocation recs · Concentration risk",BRIGHT),
    ("📦  Product Intelligence","Top selling · Highest RTO · Revenue at risk by SKU",AMBER),
    ("📍  Pincode Intelligence","Opportunity · Risk pincodes · NDR clusters · Courier mismatch",RED),
    ("⚙️  VAS Recommendations","AI Calling · WhatsApp NDR · Courier Optimization · NDD",LIGHT),
]
my = 5.53
mw, mh = 4.6, 0.88
for title, desc, col in modules:
    card_rect(c, 3.45, my-mh, mw, mh, border=col)
    txt(c, title, 3.6, my-0.3, 11, WHITE, bold=True)
    txt(c, desc,  3.6, my-0.62, 9, LGREY)
    my -= mh + 0.15

# Response format
card_rect(c, 8.25, 1.2, 4.7, 4.85, border=PURPLE)
txt(c, "JAGGU RESPONSE FORMAT", 8.45, 5.75, 9, MGREY, bold=True)
fmt = [("📊 Observation","What the data shows — with real numbers",LIGHT),
       ("🔍 Root Cause","Why it's happening — courier, state, product",AMBER),
       ("✅ Recommendation","Specific Velocity action — not generic advice",GREEN),
       ("📈 Expected Impact","Recoverable shipments or delivery gain",WHITE)]
fy = 5.3
for lbl, desc, col in fmt:
    c.setFillColor(HexColor("#151C2E")); c.setStrokeColor(LINE); c.setLineWidth(0.3)
    c.roundRect(8.4*inch, (fy-0.72)*inch, 4.35*inch, 0.82*inch, 4, fill=1, stroke=1)
    txt(c, lbl, 8.55, fy-0.12, 11, col, bold=True)
    txt(c, desc, 8.55, fy-0.45, 9.5, LGREY)
    fy -= 1.0

watermark(c); c.showPage()


# ── SLIDE 4 ───────────────────────────────────────────────────────────────────
bg(c); bar(c, 7.44, col=PURPLE); bar(c, 0, col=GREEN); slide_num(c, 4)
txt(c, "Business Impact", 0.5, 6.6, 34, WHITE, bold=True)
txt(c, "What changes when JAGGU is activated", 0.5, 6.18, 13, GREEN)

# BEFORE
card_rect(c, 0.4, 1.2, 3.7, 4.85, border=RED)
txt(c, "❌  BEFORE JAGGU", 0.6, 5.75, 12, RED, bold=True)
txt(c, "10,000 Orders / Month", 0.6, 5.38, 10, MGREY)
txt(c, "65%  Delivery Rate", 0.6, 4.82, 20, RED, bold=True)
txt(c, "3,500  Orders Failed", 0.6, 4.28, 16, RED, bold=True)
befores = ["No courier intelligence","Manual NDR handling",
           "No pincode restrictions","Reactive operations","Slow decision making"]
for i, b in enumerate(befores):
    txt(c, f"✗  {b}", 0.6, 3.7-i*0.32, 10, LGREY)

# Arrow
txt(c, "→", 4.22, 3.55, 26, LIGHT, bold=True, align="C")
txt(c, "JAGGU AI", 4.22, 3.15, 9, LIGHT, bold=True, align="C")

# AFTER
card_rect(c, 5.0, 1.2, 3.7, 4.85, border=GREEN)
txt(c, "✅  AFTER JAGGU", 5.2, 5.75, 12, GREEN, bold=True)
txt(c, "10,000 Orders / Month", 5.2, 5.38, 10, MGREY)
txt(c, "82%+  Delivery Rate", 5.2, 4.82, 20, GREEN, bold=True)
txt(c, "+1,700  Extra Deliveries", 5.2, 4.28, 16, GREEN, bold=True)
afters = ["AI Calling → 38% NDR recovery","WhatsApp NDR → 8% COD RTO",
          "Courier optimization per state","Pincode COD restrictions","Order Confirmation pre-dispatch"]
for i, a in enumerate(afters):
    txt(c, f"✓  {a}", 5.2, 3.7-i*0.32, 10, LGREY)

# VAS panel
card_rect(c, 8.9, 1.2, 4.05, 4.85, border=BRIGHT)
txt(c, "JAGGU ACTIVATES", 9.1, 5.75, 9, MGREY, bold=True)
vas = [("📞 AI Calling","38% NDR recovery rate",BRIGHT),
       ("💬 WhatsApp NDR","8% COD RTO reduction",GREEN),
       ("🔍 Order Confirm","12% pre-dispatch block",AMBER),
       ("🚚 Courier Optimize","State-level rebalancing",LIGHT),
       ("📍 Pincode Block","Zero-cost COD restriction",RED),
       ("🚀 NDD Activation","Zone A/B next-day delivery",GREEN)]
vy = 5.3
for lbl, desc, col in vas:
    c.setFillColor(HexColor("#0D1322")); c.setStrokeColor(col); c.setLineWidth(0.4)
    c.roundRect(9.05*inch, (vy-0.52)*inch, 3.75*inch, 0.6*inch, 4, fill=1, stroke=1)
    txt(c, lbl, 9.2, vy-0.1, 11, col, bold=True)
    txt(c, desc, 9.2, vy-0.38, 9, LGREY)
    vy -= 0.72

watermark(c); c.showPage()


# ── SLIDE 5 ───────────────────────────────────────────────────────────────────
bg(c); bar(c, 7.44, col=PURPLE); bar(c, 0, col=BRIGHT)
c.setFillColor(HexColor("#0F0A1E")); c.rect(0, H-2.1*inch, W, 2.1*inch, fill=1, stroke=0)
slide_num(c, 5)
txt(c, "Why JAGGU Wins", 0.5, 6.6, 36, WHITE, bold=True)
txt(c, "From reactive dashboards to proactive AI consulting", 0.5, 6.18, 13, LIGHT)
txt(c, "Hackathon Demo Ready  ·  Production Architecture  ·  Velocity Integrated",
    0.5, 5.8, 10, MGREY)

# Without
card_rect(c, 0.4, 2.1, 4.15, 3.52, border=RED)
txt(c, "❌  Without JAGGU", 0.6, 5.36, 12, RED, bold=True)
without = ["Manual analysis in Excel/Sheets","Multiple disconnected dashboards",
           "Reactive — act after damage done","Slow decisions (days, not seconds)",
           "No courier intelligence","No VAS adoption guidance","Generic, not seller-specific"]
for i,w in enumerate(without):
    txt(c, f"✗  {w}", 0.6, 4.96-i*0.33, 10, LGREY)

# With
card_rect(c, 4.7, 2.1, 4.15, 3.52, border=GREEN)
txt(c, "✅  With JAGGU AI", 4.9, 5.36, 12, GREEN, bold=True)
with_ = ["AI KAM — instant consultant","One unified intelligence engine",
         "Proactive — act before damage","Instant decisions (seconds)",
         "Courier optimization per state","VAS recommendations by impact","Personalised per seller/SKU"]
for i,w in enumerate(with_):
    txt(c, f"✓  {w}", 4.9, 4.96-i*0.33, 10, LGREY)

# Closing card
card_rect(c, 9.05, 2.1, 3.9, 3.52, border=BRIGHT)
txt(c, "One AI Consultant", 10.0, 5.2, 16, WHITE, bold=True, align="C")
txt(c, "Thousands of Sellers", 10.0, 4.72, 20, LIGHT, bold=True, align="C")
txt(c, "Millions of", 10.0, 4.22, 18, GREEN, bold=True, align="C")
txt(c, "Deliveries Optimized", 10.0, 3.82, 16, GREEN, bold=True, align="C")

# Final tagline
c.setFillColor(HexColor("#0F0A2E")); c.setStrokeColor(BRIGHT); c.setLineWidth(1)
c.roundRect(0.4*inch, 0.5*inch, 12.5*inch, 1.45*inch, 8, fill=1, stroke=1)
txt(c, "JAGGU AI", 6.665, 1.55, 32, WHITE, bold=True, align="C")
txt(c, "Turning Delivery Data into Growth Decisions", 6.665, 1.05, 15, LIGHT, align="C")
txt(c, "Powered by Velocity Shipping  ·  Built with Claude AI", 6.665, 0.68, 9, MGREY, align="C")

watermark(c); c.showPage()

c.save()
import os
print(f"✅ PDF saved: {OUT}")
print(f"   Pages: 5")
print(f"   Size:  {os.path.getsize(OUT):,} bytes")
