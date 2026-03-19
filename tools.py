import random


# 📦 MOCK ORDER DB
ORDERS = {
    "John": {"status": "shipped", "value": 120},
    "Sarah": {"status": "delayed", "value": 80},
    "Mike": {"status": "delivered", "value": 200},
    "Emma": {"status": "processing", "value": 150}
}


# 🔍 GET ORDER
def get_order(customer):
    return ORDERS.get(customer, {"status": "unknown", "value": 0})


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