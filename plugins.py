import os


def get_customer_data(source="mock"):
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise NotImplementedError("plugins.py is a development stub. Wire a real customer data source.")
    return {"id": "123", "name": "John", "value": 600, "orders": ["#1001"], "status": "delayed"}