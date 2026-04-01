import chromadb


class VectorStore:
    def __init__(self, host: str = "localhost", port: int = 8001, ephemeral: bool = False,
                 collection_name: str = "meeting_segments"):
        if ephemeral:
            self.client = chromadb.EphemeralClient()
        else:
            self.client = chromadb.HttpClient(host=host, port=port)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_segments(self, meeting_id: str, meeting_title: str, date: str, segments: list[dict]):
        ids, documents, metadatas = [], [], []
        for i, seg in enumerate(segments):
            ids.append(f"{meeting_id}-seg-{i}")
            documents.append(seg["text"])
            metadatas.append({
                "meeting_id": meeting_id,
                "meeting_title": meeting_title,
                "speaker": seg.get("speaker", ""),
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "date": date,
            })
        if not ids:
            return
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        # Ask Chroma for extra headroom so we can remove near-identical hits safely.
        n_results = max(top_k * 3, top_k)
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        output = []
        seen = set()
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, distance in zip(documents, metadatas, distances):
            if not doc or not meta:
                continue
            dedupe_key = (
                meta.get("meeting_id"),
                meta.get("speaker", ""),
                round(float(meta.get("start", 0.0)), 1),
                round(float(meta.get("end", 0.0)), 1),
                " ".join(str(doc).split()).strip().lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            output.append({"text": doc, "score": distance, **meta})
            if len(output) >= top_k:
                break
        return output
