from __future__ import annotations

from copy import deepcopy


class ReciprocalRankFusion:
    """Merge ranked retrieval lists using Reciprocal Rank Fusion."""

    def __init__(self, k: int = 60) -> None:
        self.k = k

    def fuse(self, ranked_sources: list[tuple[str, list[dict]]], limit: int) -> list[dict]:
        if limit <= 0:
            return []

        fused: dict[str, dict] = {}
        for source_name, hits in ranked_sources:
            for rank, hit in enumerate(hits, start=1):
                chunk_id = str(hit["chunk_id"])
                contribution = 1.0 / (self.k + rank)
                if chunk_id not in fused:
                    merged = deepcopy(hit)
                    merged["fusion_score"] = 0.0
                    merged["sources"] = []
                    merged["scores"] = {}
                    fused[chunk_id] = merged

                fused_hit = fused[chunk_id]
                fused_hit["fusion_score"] += contribution
                if source_name not in fused_hit["sources"]:
                    fused_hit["sources"].append(source_name)
                fused_hit["scores"][source_name] = hit.get("score")

        return sorted(
            fused.values(),
            key=lambda h: (h["fusion_score"], len(h["sources"])),
            reverse=True,
        )[:limit]
