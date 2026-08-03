import asyncio, json, re, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ENV = {"DATAHUB_GMS_URL": "http://localhost:8080", "DATAHUB_GMS_TOKEN": ""}
URN_RE = re.compile(r'"urn":"(urn:li:dataset:[^"]+)"')

def text_of(res):
    return "".join(getattr(c, "text", "") for c in res.content)

def facts(node):
    owners = []
    for o in (node.get("ownership") or {}).get("owners", []) or []:
        props = (o.get("owner") or {}).get("properties") or {}
        otype = (o.get("ownershipType") or {}).get("info", {}).get("name")
        owners.append({"name": props.get("displayName") or props.get("name"), "role": otype})
    return {
        "urn": node.get("urn"),
        "name": node.get("name"),
        "platform": ((node.get("platform") or {}).get("name")),
        "owners": owners,
        "owner_count": len(owners),
        "tags": ["".join(ch for ch in ((t.get("tag") or {}).get("properties", {}).get("name") or "") if ord(ch) < 0x2000).strip() for t in (node.get("tags") or {}).get("tags", []) or []],
        "glossary": [(g.get("term") or {}).get("properties", {}).get("name") for g in (node.get("glossaryTerms") or {}).get("terms", []) or []],
        "health": node.get("health") or [],
        "has_description": bool(((node.get("properties") or {}).get("description")) or ((node.get("editableProperties") or {}).get("description"))),
        "domain": (((node.get("domain") or {}).get("domain") or {}).get("properties") or {}).get("name"),
    }

async def run(query, hops=2):
    p = StdioServerParameters(command="mcp-server-datahub", args=[], env=ENV)
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("search", {"query": query})
            cands = [u for u in URN_RE.findall(text_of(res)) if "replica" not in u.lower()]
            if not cands:
                print("No dataset found for:", query); return
            root = cands[0]
            seen, frontier, chain = {root}, [root], []
            for hop in range(1, hops + 1):
                nxt = []
                for u in frontier:
                    lr = await s.call_tool("get_lineage", {"urn": u, "upstream": True, "max_hops": 1})
                    for up in URN_RE.findall(text_of(lr)):
                        if up not in seen:
                            seen.add(up); nxt.append(up)
                            chain.append({"hop": hop, "urn": up, "from": u})
                frontier = nxt
                if not frontier: break
            all_urns = [root] + [c["urn"] for c in chain]
            er = await s.call_tool("get_entities", {"urns": all_urns})
            nodes = json.loads(text_of(er))
            if isinstance(nodes, dict): nodes = [nodes]
            by_urn = {n.get("urn"): facts(n) for n in nodes}
            audit = {
                "root": by_urn.get(root, {"urn": root}),
                "upstream": [dict(hop=c["hop"], **by_urn.get(c["urn"], {"urn": c["urn"]})) for c in chain],
            }
            with open("/root/audit.json", "w") as f:
                json.dump(audit, f, indent=2)
            print("ROOT:", audit["root"].get("name"), "(", audit["root"].get("platform"), ")")
            print("UPSTREAM NODES:", len(audit["upstream"]))
            print()
            for n in audit["upstream"][:15]:
                h = ",".join(str(x.get("type")) + ":" + str(x.get("status")) for x in (n.get("health") or [])) or "-"
                terms = ",".join([t for t in n.get("glossary", []) if t]) or "-"
                doc = "Y" if n.get("has_description") else "N"
                print(" hop" + str(n["hop"]), "own=" + str(n.get("owner_count", 0)), "health=" + h, "doc=" + doc, "terms=" + terms, (n.get("name") or n["urn"])[:40])
            print()
            print("Saved -> /root/audit.json")

asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "order_details"))
