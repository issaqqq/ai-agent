import json
import re
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
ORDERS_FILE = BASE_DIR / "data" / "orders.json"

def normalize_order_id(order_id: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9-]', '', order_id)
    return cleaned.upper()

def lookup_order(raw_order_id: str) -> Dict[str, Any]:
    order_id = normalize_order_id(raw_order_id)
    
    if not ORDERS_FILE.exists():
        return {"error": "Orders database not found", "handoff": True}
        
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for order in data.get("orders", []):
        if order.get("order_id") == order_id:
            status = order.get("status")
            
            # Strip PII and internal data fields
            result = {
                "order_id": order.get("order_id"),
                "membership_tier": order.get("membership_tier"),
                "items": [
                    {
                        "name": item.get("name"),
                        "quantity": item.get("quantity"),
                        "final_sale": item.get("final_sale")
                    } for item in order.get("items", [])
                ],
                "placed_at": order.get("placed_at"),
                "status": status,
                "customer_safe_message": order.get("customer_safe_message"),
                "handoff": False
            }
            
            # Enforce status precedence and stale data rules
            if status in ["cancelled", "returned"]:
                result["carrier"] = None
                result["estimated_delivery"] = None
            elif status == "shipped":
                result["carrier"] = order.get("carrier")
                result["estimated_delivery"] = order.get("estimated_delivery") or "Unavailable"
            elif status == "exception":
                result["handoff"] = True
                
            return result
            
    return {"error": f"Order {order_id} was not found. Please check your order ID or contact support.", "handoff": True}