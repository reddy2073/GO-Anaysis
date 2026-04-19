import sys
sys.path.insert(0, '.')
import chromadb
from config import CHROMA_PATH

print("CHROMA_PATH:", CHROMA_PATH)

TARGETS = {
    'constitution_chunks':      200,
}

try:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    print("Client created")
    counts = {}
    for name in TARGETS:
        try:
            col = client.get_or_create_collection(name)
            counts[name] = col.count()
            print(f"{name}: {counts[name]}")
        except Exception as e:
            print(f'Error for {name}: {e}')
            counts[name] = 0

    print('Counts:', counts)
    complete = all(counts[name] >= target for name, target in TARGETS.items())
    print('Complete:', complete)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()