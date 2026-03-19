import json
import os

FILE = "external_knowledge.json"


def ingest_data(new_data):
    if not os.path.exists(FILE):
        data = []
    else:
        with open(FILE, "r") as f:
            data = json.load(f)

    data.append(new_data)

    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


def retrieve_knowledge(query):
    if not os.path.exists(FILE):
        return ""

    with open(FILE, "r") as f:
        data = json.load(f)

    results = []

    for item in data:
        if query.lower() in str(item).lower():
            results.append(str(item))

    return "\n".join(results[:3])