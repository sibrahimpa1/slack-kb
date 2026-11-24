"""Mocked connectors. Each source shares documents its own way; the sync maps
those principals to directory groups. Anything that can't be mapped is dropped,
so a document is never more visible in Lantern than it is at the source.
"""
from . import corpus

# Native principals per source -> directory group
MAPPING = {
    "confluence": {"confluence-users": "all_staff", "eng-space": "eng", "sales-space": "sales",
                   "hr-space": "people_ops", "contractor-access": "contractors", "finance-space": "finance",
                   "leadership-space": "leadership"},
    "drive": {"everyone@fernhill.example": "all_staff", "people@fernhill.example": "people_ops",
              "finance@fernhill.example": "finance", "leadership@fernhill.example": "leadership",
              "sales@fernhill.example": "sales", "eng@fernhill.example": "eng",
              "contractors@fernhill.example": "contractors"},
    "notion": {"workspace-members": "all_staff", "guests:contractors": "contractors", "teamspace:eng": "eng"},
}

# Sharing that exists at the source but has no group here (fails closed)
EXTRA_PRINCIPALS = {
    "D-15": ["board-observer@outside.example"],
    "D-11": ["guests:auditor-2026"],
}

LAST_SYNC = {"confluence": "2026-11-24 08:00", "drive": "2026-11-24 08:05", "notion": "2026-11-24 08:10"}


def native_acl(doc):
    rev = {v: k for k, v in MAPPING[doc["source"]].items()}
    return [rev[g] for g in doc["groups"]] + EXTRA_PRINCIPALS.get(doc["id"], [])


def sync(source):
    docs, warnings = [], []
    for d in corpus.DOCS:
        if d["source"] != source:
            continue
        groups, unmapped = [], []
        for p in native_acl(d):
            g = MAPPING[source].get(p)
            (groups.append(g) if g else unmapped.append(p))
        if unmapped:
            warnings.append({"doc": d["id"], "principals": unmapped, "effect": "ignored; only mapped groups can see it here"})
        docs.append({"doc": d["id"], "title": d["title"], "native": native_acl(d), "groups": groups})
    return {"source": source, "name": corpus.SOURCES[source]["name"], "scope": corpus.SOURCES[source]["scope"],
            "last_sync": LAST_SYNC[source], "docs": docs, "warnings": warnings}


def sync_all():
    return [sync(s) for s in corpus.SOURCES]
