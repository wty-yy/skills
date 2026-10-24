import json
from commandcode_usage import auth_headers, call_api

h = auth_headers()
data = call_api("/internal/models", None, h)
if isinstance(data, list):
    models = data
else:
    for k in ("models", "data"):
        if isinstance(data, dict) and isinstance(data.get(k), list):
            models = data[k]
            break
    else:
        models = data
print(json.dumps(models[:2], ensure_ascii=False, indent=1)[:1200])
print("count:", len(models))
cats = {}
for m in models:
    cats.setdefault(str(m.get("plan") or m.get("category") or m.get("tier")), []).append(m.get("id"))
for c, ids in sorted(cats.items()):
    print(c, len(ids), sorted(str(i) for i in ids))
