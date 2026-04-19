import traceback
import chromadb
from config import CHROMA_PATH

try:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    cols = client.list_collections()
    print('collections', [c.name for c in cols])
    for c in cols:
        try:
            print(c.name, c.count())
        except Exception as nested_e:
            print('count_error', c.name, type(nested_e).__name__, nested_e)
except Exception as e:
    traceback.print_exc()
