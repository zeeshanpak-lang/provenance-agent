import asyncio, json, subprocess, sys, os, time

TARGETS = ["order_details", "customer_analytics", "measures", "looker",
           "orders", "customers", "products", "warehouses"]

results = []
for t in TARGETS:
    print("=" * 60)
    print("AUDITING:", t)
    r = subprocess.run([sys.executable, "/root/walker.py", t],
                       capture_output=True, text=True, env=os.environ.copy())
    time.sleep(4)
    if "UPSTREAM NODES" not in r.stdout:
        print("  skipped (not found)")
        continue
    subprocess.run(["python", "/root/score.py"], capture_output=True, text=True)
    subprocess.run(["python", "/root/writeback.py"], capture_output=True, text=True)
    rep = json.load(open("/root/report.json"))
    aud = json.load(open("/root/audit.json"))
    name = aud["root"].get("name")
    results.append((name, rep["score"], rep["grade"], len(aud["upstream"]), len(rep["findings"])))
    print("  " + str(name) + ": " + str(rep["score"]) + "/100 grade " + rep["grade"])

print()
print("=" * 60)
print("  CATALOG TRUST SUMMARY")
print("=" * 60)
for n, s, g, u, f in sorted(results, key=lambda x: x[1]):
    print("  " + str(g) + "  " + str(s).rjust(3) + "/100   " + str(u).rjust(2) + " upstream  " +
          str(f) + " findings   " + str(n))
json.dump([{"asset": n, "score": s, "grade": g, "upstream": u, "findings": f}
           for n, s, g, u, f in results], open("/root/catalog_summary.json", "w"), indent=2)
print()
print("Saved -> /root/catalog_summary.json")
