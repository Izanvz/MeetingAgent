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
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        results = self.collection.query(query_texts=[query], n_results=top_k)
        output = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            output.append({"text": doc, **meta})
        return output
