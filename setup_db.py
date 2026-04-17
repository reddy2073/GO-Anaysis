"""Creates the 5 ChromaDB collections for LegalDebateAI."""
import chromadb
from config import CHROMA_PATH

COLLECTIONS = [
    ("constitution_chunks",      "All 395 Indian Constitution Articles + Schedules"),
    ("central_acts_chunks",      "Central Acts: IPC, CrPC, Factories, IDA, Gratuity, RTI, etc."),
    ("state_acts_chunks",        "AP and Telangana state-specific laws"),
    ("government_orders_chunks", "AP/TS Government Orders 2014-present"),
    ("court_verdicts_chunks",    "SC and HC landmark judgments"),
]

def setup():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    for name, description in COLLECTIONS:
        col = client.get_or_create_collection(
            name=name,
            metadata={"description": description, "hnsw:space": "cosine"}
        )
        print(f"  Collection '{name}': {col.count()} chunks")
    print(f"\nChromaDB ready at: {CHROMA_PATH}")

if __name__ == "__main__":
    setup()
