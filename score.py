import json, sys

SENSITIVE = {"PII", "SOC2 Auditable", "GDPR"}

def is_sensitive(n):
    return bool(SENSITIVE & set(t for t in (n.get("glossary") or []) if t))

def evaluate(audit):
    root = audit["root"]
    ups = audit["upstream"]
    findings = []
    score = 100

    # CHECK 1 - unowned sensitive upstreams (max -40)
    bad = [n for n in ups if is_sensitive(n) and n.get("owner_count", 0) == 0]
    if bad:
        pen = min(40, 4 * len(bad))
        score -= pen
        findings.append({
            "check": "Unowned sensitive data upstream",
            "severity": "CRITICAL" if len(bad) >= 5 else "HIGH",
            "penalty": pen,
            "detail": str(len(bad)) + " upstream nodes carry sensitive classifications with no assigned owner",
            "evidence": [{"node": n.get("name"), "urn": n.get("urn"), "fact": "owner_count=0, glossary=" + ",".join([t for t in n.get("glossary") or [] if t])} for n in bad],
        })

    # CHECK 2 - ownership coverage (max -20)
    unowned = [n for n in ups if n.get("owner_count", 0) == 0]
    if ups:
        cov = 1 - len(unowned) / len(ups)
        if cov < 1:
            pen = min(20, int((1 - cov) * 20))
            score -= pen
            findings.append({
                "check": "Ownership coverage",
                "severity": "HIGH" if cov < 0.5 else "MEDIUM",
                "penalty": pen,
                "detail": str(round(cov * 100)) + "% of upstream nodes have an assigned owner",
                "evidence": [{"node": n.get("name"), "urn": n.get("urn"), "fact": "owner_count=0"} for n in unowned[:8]],
            })

    # CHECK 3 - documentation coverage (max -15)
    undoc = [n for n in ups if not n.get("has_description")]
    if ups and undoc:
        pen = min(15, int(len(undoc) / len(ups) * 15))
        score -= pen
        findings.append({
            "check": "Documentation coverage",
            "severity": "MEDIUM",
            "penalty": pen,
            "detail": str(len(undoc)) + " of " + str(len(ups)) + " upstream nodes are undocumented",
            "evidence": [{"node": n.get("name"), "urn": n.get("urn"), "fact": "has_description=false"} for n in undoc[:8]],
        })

    # CHECK 4 - incident health (max -25)
    failing = []
    for n in [root] + ups:
        for h in n.get("health") or []:
            if str(h.get("status")).upper() != "PASS":
                failing.append((n, h))
    if failing:
        pen = min(25, 8 * len(failing))
        score -= pen
        findings.append({
            "check": "Upstream incident health",
            "severity": "CRITICAL",
            "penalty": pen,
            "detail": str(len(failing)) + " nodes report non-passing health",
            "evidence": [{"node": n.get("name"), "urn": n.get("urn"), "fact": str(h.get("type")) + "=" + str(h.get("status"))} for n, h in failing[:8]],
        })

    # CHECK 4b - no upstream lineage to verify (max -20)
    if not ups:
        score -= 20
        findings.append({
            "check": "No upstream lineage recorded",
            "severity": "HIGH",
            "penalty": 20,
            "detail": "This asset has no upstream lineage in DataHub - its provenance cannot be verified",
            "evidence": [{"node": root.get("name"), "urn": root.get("urn"), "fact": "upstream_count=0"}],
        })

    # CHECK 5 - steward on sensitive root (max -10)
    if is_sensitive(root):
        roles = [str(o.get("role") or "") for o in root.get("owners") or []]
        if not any("Steward" in r for r in roles):
            score -= 10
            findings.append({
                "check": "Data steward on sensitive asset",
                "severity": "HIGH",
                "penalty": 10,
                "detail": "Root asset carries sensitive classifications but has no Data Steward",
                "evidence": [{"node": root.get("name"), "urn": root.get("urn"), "fact": "roles=" + (",".join(roles) or "none")}],
            })

    return max(0, score), findings

def grade(s):
    if s >= 90: return "A", "TRUSTED"
    if s >= 75: return "B", "ACCEPTABLE"
    if s >= 60: return "C", "NEEDS REVIEW"
    if s >= 40: return "D", "AT RISK"
    return "F", "NOT TRUSTWORTHY"

def render(audit, score, findings):
    root = audit["root"]
    g, label = grade(score)
    L = []
    L.append("=" * 72)
    L.append("  PROVENANCE TRUST REPORT")
    L.append("=" * 72)
    L.append("  Asset    : " + str(root.get("name")) + "  (" + str(root.get("platform")) + ")")
    L.append("  Domain   : " + str(root.get("domain")))
    L.append("  Upstream : " + str(len(audit["upstream"])) + " nodes traversed")
    L.append("")
    L.append("  TRUST SCORE : " + str(score) + "/100   GRADE " + g + "   [" + label + "]")
    L.append("=" * 72)
    L.append("")
    if not findings:
        L.append("  No governance issues detected across the upstream chain.")
    for f in findings:
        L.append("  [" + f["severity"] + "]  " + f["check"] + "   (-" + str(f["penalty"]) + ")")
        L.append("     " + f["detail"])
        L.append("     Evidence:")
        for e in f["evidence"]:
            L.append("       - " + str(e["node"]) + "  ::  " + e["fact"])
        L.append("")
    L.append("=" * 72)
    L.append("  Every deduction above is bound to a verifiable DataHub metadata fact.")
    L.append("=" * 72)
    return "\n".join(L)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/root/audit.json"
    audit = json.load(open(path))
    score, findings = evaluate(audit)
    report = render(audit, score, findings)
    print(report)
    json.dump({"score": score, "grade": grade(score)[0], "findings": findings},
              open("/root/report.json", "w"), indent=2)
    open("/root/report.txt", "w").write(report)
