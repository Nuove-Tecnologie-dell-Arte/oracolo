from collections import Counter

from backend import db_local


def build_tag_detail(tag_name: str, category: str | None = None) -> dict | None:
    """Dettaglio di un tag (entry correlate + tag imparentati), o None se non esiste.

    Condivisa tra il server locale (backend/server.py) e l'export statico
    (backend/export_static.py) cosi' producono esattamente la stessa risposta.
    """
    entries = db_local.get_entries_with_tags(category)
    matching = [e for e in entries if tag_name in e["tags"]]
    if not matching:
        return None

    related_counts: Counter = Counter()
    # Per ogni tag imparentato, le entry che contengono entrambi i tag:
    # sono il motivo per cui i due sono collegati.
    shared: dict[str, list[dict]] = {}
    for entry in matching:
        for tag in entry["tags"]:
            if tag != tag_name:
                related_counts[tag] += 1
                shared.setdefault(tag, []).append(entry)

    return {
        "name": tag_name,
        "count": len(matching),
        # `source` (titolo e autore) accompagna le citazioni tratte dai testi;
        # `group` il gruppo di chi ha scritto un pensiero del diario
        "entries": [
            {"id": e["id"], "text": e["text"], "likes": e["likes"], "source": e["source"], "group": e.get("group")}
            for e in matching[:20]
        ],
        "related": [
            {
                "name": n,
                "weight": w,
                "entries": [
                    {"id": e["id"], "text": e["text"], "source": e["source"], "group": e.get("group")}
                    for e in shared[n][:3]
                ],
            }
            for n, w in related_counts.most_common(12)
        ],
    }
