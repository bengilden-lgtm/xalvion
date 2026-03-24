import hashlib
from typing import Optional


# 📦 FIXED KNOWN TEST CUSTOMERS
ORDERS = {
    "John": {"status": "shipped", "value": 120, "tracking": "TRK-1001", "eta": "2-4 business days"},
    "Sarah": {"status": "delayed", "value": 80, "tracking": "TRK-1002", "eta": "Delayed in transit"},
    "Mike": {"status": "delivered", "value": 200, "tracking": "TRK-1003", "eta": "Delivered"},
    "Emma": {"status": "processing", "value": 150, "tracking": "TRK-1004", "eta": "Preparing for dispatch"},
}


def _stable_seed(name: str) -> int:
    return int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)


def _default_mock_order(customer: str):
    seed = _stable_seed((customer or "guest").strip()) % 4
    options = [
        {"status": "processing", "value": 99, "tracking": "TRK-DEV-201", "eta": "Preparing for dispatch"},
        {"status": "shipped", "value": 129, "tracking": "TRK-DEV-202", "eta": "2-4 business days"},
        {"status": "delayed", "value": 149, "tracking": "TRK-DEV-203", "eta": "Delayed in transit"},
        {"status": "delivered", "value": 89, "tracking": "TRK-DEV-204", "eta": "Delivered"},
    ]
    return options[seed]


def _scenario_mock_order(customer: str, context: str):
    text = (context or "").lower()
    seed = _stable_seed((customer or "guest").strip()) % 1000

    delivered_missing = any(p in text for p in [
        "delivered but i never got it",
        "delivered but i didnt get it",
        "delivered but i didn't get it",
        "says delivered but i never got it",
        "says delivered but i didnt get it",
        "says delivered but i didn't get it",
        "not received",
        "never got it",
        "missing package",
        "missing parcel",
        "stolen",
    ])

    late_or_delayed = any(p in text for p in [
        "late",
        "delayed",
        "where is my order",
        "where's my order",
        "wheres my order",
        "where is my package",
        "where's my package",
        "wheres my package",
        "still not here",
        "taking too long",
        "annoyed",
        "tracking not moving",
    ])

    shipped_intent = any(p in text for p in [
        "shipped",
        "in transit",
        "tracking",
        "on the way",
    ])

    processing_intent = any(p in text for p in [
        "processing",
        "hasn't shipped",
        "hasnt shipped",
        "not shipped",
        "preparing",
    ])

    # Priority order matters
    if delivered_missing:
        return {
            "status": "delivered",
            "value": 119,
            "tracking": f"TRK-DEV-{700 + (seed % 100)}",
            "eta": "Delivered",
        }

    if late_or_delayed:
        return {
            "status": "delayed",
            "value": 139,
            "tracking": f"TRK-DEV-{500 + (seed % 100)}",
            "eta": "Delayed in transit",
        }

    if processing_intent:
        return {
            "status": "processing",
            "value": 109,
            "tracking": f"TRK-DEV-{300 + (seed % 100)}",
            "eta": "Preparing for dispatch",
        }

    if shipped_intent:
        return {
            "status": "shipped",
            "value": 129,
            "tracking": f"TRK-DEV-{400 + (seed % 100)}",
            "eta": "2-4 business days",
        }

    return _default_mock_order(customer)


# 🔍 GET ORDER
def get_order(customer: str, context: Optional[str] = None):
    if customer in ORDERS:
        return ORDERS[customer]

    return _scenario_mock_order(customer, context or "")


# 💸 SAFE REFUND
def process_refund(customer, amount):
    if amount > 50:
        return {"error": "Refund exceeds safe limit"}

    return {
        "status": "success",
        "customer": customer,
        "amount": amount
    }


# 🎁 ISSUE CREDIT
def issue_credit(customer, amount):
    return {
        "status": "credit_issued",
        "customer": customer,
        "amount": amount
    }