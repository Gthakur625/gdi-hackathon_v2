import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_shipment_data(num_records=1000, seed=42):
    np.random.seed(seed)

    sellers = ["Apex Retail", "Zenith Fashion", "Vortex Commerce", "Nova Wellness", "Quantum Goods"]
    skus_by_seller = {
        "Apex Retail":    ["SKU-APP-01","SKU-APP-02","SKU-APP-03","SKU-APP-04"],
        "Zenith Fashion": ["SKU-FSH-10","SKU-FSH-11","SKU-FSH-12"],
        "Vortex Commerce":["SKU-ELC-50","SKU-ELC-51","SKU-ELC-52"],
        "Nova Wellness":  ["SKU-WEL-20","SKU-WEL-21","SKU-WEL-22"],
        "Quantum Goods":  ["SKU-GEN-90","SKU-GEN-91","SKU-GEN-92"],
    }
    sku_to_product = {
        "SKU-APP-01":"Premium Cotton T-Shirt","SKU-APP-02":"Slim Fit Denim",
        "SKU-APP-03":"Oversized Hoodie","SKU-APP-04":"Cargo Joggers",
        "SKU-FSH-10":"Smart Watch V2","SKU-FSH-11":"Leather Wallet",
        "SKU-FSH-12":"Classic Sunglasses",
        "SKU-ELC-50":"Noise Cancelling Headphones","SKU-ELC-51":"Wireless Keyboard & Mouse",
        "SKU-ELC-52":"Bluetooth Speaker",
        "SKU-WEL-20":"Organic Protein Powder","SKU-WEL-21":"Multivitamin Capsules",
        "SKU-WEL-22":"Ayurvedic Massage Oil",
        "SKU-GEN-90":"Stainless Steel Water Bottle","SKU-GEN-91":"Ergonomic Office Cushion",
        "SKU-GEN-92":"Eco-friendly Yoga Mat",
    }
    sku_category = {
        "SKU-APP-01":"Apparel","SKU-APP-02":"Apparel","SKU-APP-03":"Apparel","SKU-APP-04":"Apparel",
        "SKU-FSH-10":"Electronics","SKU-FSH-11":"Fashion","SKU-FSH-12":"Fashion",
        "SKU-ELC-50":"Electronics","SKU-ELC-51":"Electronics","SKU-ELC-52":"Electronics",
        "SKU-WEL-20":"Wellness","SKU-WEL-21":"Wellness","SKU-WEL-22":"Wellness",
        "SKU-GEN-90":"General","SKU-GEN-91":"General","SKU-GEN-92":"General",
    }
    states = ["Maharashtra","Karnataka","Delhi","Tamil Nadu","Uttar Pradesh",
              "Bihar","West Bengal","Gujarat","Rajasthan","Haryana"]
    state_pincode_prefix = {
        "Maharashtra":"40","Karnataka":"56","Delhi":"11","Tamil Nadu":"60",
        "Uttar Pradesh":"20","Bihar":"80","West Bengal":"70","Gujarat":"38",
        "Rajasthan":"30","Haryana":"12",
    }
    couriers = ["ATS (Velocity)","Nimbus Express","Swift Courier","Apex Logistix"]
    ndr_reasons_by_type = {
        "absent":"Customer Not Available","address":"Wrong / Incomplete Address",
        "refused":"Customer Refused Delivery","future":"Delivery Requested for Later",
        "other":"Door Locked / Building Issue",
    }
    seller_vas = {
        "Apex Retail":     ["ATS Core Routing"],
        "Zenith Fashion":  ["ATS Core Routing","ATS Address Verification"],
        "Vortex Commerce": ["ATS Core Routing","ATS AI Calling"],
        "Nova Wellness":   ["ATS Core Routing","ATS WhatsApp NDR"],
        "Quantum Goods":   ["ATS Core Routing"],
    }

    data = []
    start_date = datetime.now() - timedelta(days=30)

    for i in range(num_records):
        seller       = np.random.choice(sellers)
        sku          = np.random.choice(skus_by_seller[seller])
        product_name = sku_to_product[sku]
        category     = sku_category[sku]

        state_probs = [0.20,0.15,0.15,0.10,0.12,0.08,0.08,0.06,0.04,0.02]
        state   = np.random.choice(states, p=state_probs)
        pincode = state_pincode_prefix[state]+"".join([str(np.random.randint(0,10)) for _ in range(4)])

        courier = np.random.choice(couriers, p=[0.45,0.25,0.18,0.12])
        cod_prob = {"Apex Retail":0.76,"Zenith Fashion":0.58}.get(seller, 0.45)
        payment_type = "COD" if np.random.rand() < cod_prob else "Prepaid"

        if "ELC" in sku:        order_value = int(np.random.normal(3200,800))
        elif "WEL" in sku:      order_value = int(np.random.normal(1200,300))
        elif "FSH" in sku or "APP" in sku: order_value = int(np.random.normal(1800,450))
        else:                   order_value = int(np.random.normal(900,250))
        order_value = max(299, min(8000, order_value))

        days_offset   = np.random.randint(0,30)
        shipment_date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")

        delivery_score = 0.85
        if courier=="ATS (Velocity)":  delivery_score += 0.10
        elif courier=="Nimbus Express": delivery_score -= 0.20
        elif courier=="Swift Courier":  delivery_score += 0.02
        elif courier=="Apex Logistix":  delivery_score -= 0.05
        if state=="Bihar":              delivery_score -= 0.22
        elif state=="Uttar Pradesh":    delivery_score -= 0.12
        if payment_type=="COD":         delivery_score -= 0.15
        else:                           delivery_score += 0.05
        delivery_score += np.random.normal(0,0.05)

        delivery_status="Delivered"; rto_status="None"; ndr_status="None"
        ndr_reason=""; attempt_count=1

        if delivery_score >= 0.72:
            delivery_status = "Delivered"
            if np.random.rand() < 0.10:
                ndr_status = "Resolved"
                ndr_reason = np.random.choice(["Customer Not Available","Delivery Requested for Later"])
        elif delivery_score >= 0.52:
            ndr_reason_key = np.random.choice(["absent","future","other"],p=[0.55,0.30,0.15])
            ndr_reason   = ndr_reasons_by_type[ndr_reason_key]
            ndr_status   = "Raised"
            attempt_count = np.random.randint(1,3)
            if np.random.rand() < 0.50:
                delivery_status="Delivered"; ndr_status="Resolved"
            else:
                delivery_status="RTO"; rto_status="Returned"
        else:
            ndr_reason_key = np.random.choice(["address","refused","absent"],p=[0.50,0.30,0.20])
            ndr_reason    = ndr_reasons_by_type[ndr_reason_key]
            delivery_status="RTO"
            rto_status     = "Returned" if np.random.rand()<0.85 else "Pending RTO"
            attempt_count  = np.random.randint(1,4)
            if np.random.rand()<0.60: ndr_status="Raised"

        if delivery_status=="RTO":
            rto_status = "Returned" if np.random.rand()<0.85 else "Pending RTO"

        ndr_age_hours     = int(np.random.randint(4,96)) if ndr_status=="Raised" else 0
        whatsapp_opt_in   = bool(np.random.rand()<0.65)
        calling_attempted = bool(delivery_status=="NDR" and np.random.rand()<0.25)

        data.append({
            "seller_name":seller,"sku":sku,"product_name":product_name,
            "sku_category":category,"state":state,"pincode":pincode,
            "courier":courier,"order_value":order_value,"payment_type":payment_type,
            "delivery_status":delivery_status,"rto_status":rto_status,
            "ndr_status":ndr_status,"ndr_reason":ndr_reason,
            "attempt_count":attempt_count,"ndr_age_hours":ndr_age_hours,
            "whatsapp_opt_in":whatsapp_opt_in,"calling_attempted":calling_attempted,
            "vas_active":", ".join(seller_vas[seller]),
            "shipment_date":shipment_date,
        })

    return pd.DataFrame(data)


def save_sample_data(filepath="shipments.csv"):
    df = generate_shipment_data()
    df.to_csv(filepath, index=False)
    print(f"Generated {len(df)} records → {filepath}")
    return df

if __name__ == "__main__":
    save_sample_data()
