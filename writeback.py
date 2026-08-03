import json, sys
from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
from datahub.emitter.mcp import MetadataChangeProposalWrapper
import datahub.metadata.schema_classes as sc

GMS = "http://localhost:8080"

def tag_urn(name):
    return "urn:li:tag:" + name

def ensure_tag(emitter, name, desc):
    mcp = MetadataChangeProposalWrapper(
        entityUrn=tag_urn(name),
        aspect=sc.TagPropertiesClass(name=name, description=desc),
    )
    emitter.emit(mcp)

def stamp(audit_path="/root/audit.json", report_path="/root/report.json"):
    audit = json.load(open(audit_path))
    report = json.load(open(report_path))
    urn = audit["root"]["urn"]
    grade = report["grade"]
    score = report["score"]

    name = "Provenance-Grade-" + grade
    desc = ("Provenance trust grade " + grade + " (score " + str(score) + "/100). "
            "Assigned by the Provenance agent from an evidence-bound audit of the upstream lineage chain.")

    emitter = DataHubGraph(DatahubClientConfig(server=GMS))
    ensure_tag(emitter, name, desc)

    emitter.emit(MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=sc.GlobalTagsClass(tags=[sc.TagAssociationClass(tag=tag_urn(name))]),
    ))

    lines = ["## Provenance Trust Audit", "",
             "**Score: " + str(score) + "/100 (Grade " + grade + ")**", "",
             str(len(audit["upstream"])) + " upstream nodes traversed.", ""]
    for f in report["findings"]:
        lines.append("- **[" + f["severity"] + "] " + f["check"] + "** (-" + str(f["penalty"]) + "): " + f["detail"])
    lines.append("")
    lines.append("_Every deduction is bound to a verifiable DataHub metadata fact._")

    import time; time.sleep(1)
    check = emitter.get_aspect(entity_urn=urn, aspect_type=sc.GlobalTagsClass)
    print("VERIFIED IN GRAPH:", bool(check and check.tags))

    print("Tagged:", urn)
    print("  ->", name)
    print("\n".join(lines))

if __name__ == "__main__":
    stamp()
