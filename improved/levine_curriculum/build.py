"""build -- orchestrace osnovy: chunk -> MAP(cache) -> merge -> order -> critic -> zápis. + CLI."""
import json
import hashlib
from pathlib import Path
from .chunk import chunk_corpus
from .extract import extract_concepts
from .graph import merge_concepts, order_concepts
from .critic import critique
from .output import write_curriculum


def build_curriculum(corpus_dir, out_dir, client, work_dir,
                     max_chars=4000, overlap=400, run_critic=True):
    """Celá pipeline. MAP výstupy se cachují per okno (resumable). -> Path(out_dir)."""
    cache = Path(work_dir) / "map_cache"
    cache.mkdir(parents=True, exist_ok=True)
    chunks = chunk_corpus(corpus_dir, max_chars, overlap)
    per_chunk = []
    for idx, ch in enumerate(chunks):
        key = hashlib.sha1(ch.text.encode("utf-8")).hexdigest()[:16]
        cf = cache / f"chunk-{idx:04d}-{key}.json"
        if cf.exists():
            per_chunk.append(json.loads(cf.read_text()))
        else:
            concepts = []
            for attempt in (1, 2):                 # §9: 1 retry, pak skip s logem
                try:
                    concepts = extract_concepts(ch, client)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  [skip] okno {idx} ({ch.chapter} {ch.pages}): {type(e).__name__}: {e}")
            cf.write_text(json.dumps(concepts, ensure_ascii=False))
            per_chunk.append(concepts)
    merged = order_concepts(merge_concepts(per_chunk))
    report = critique(merged, client) if run_critic else None
    return write_curriculum(merged, out_dir, report)


def main():
    import argparse
    from .ollama_client import OllamaClient
    ap = argparse.ArgumentParser(description="Levine korpus -> výuková osnova (lokální Ollama)")
    ap.add_argument("corpus_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--work", required=True)
    ap.add_argument("--model", default="qwen3.6:27b-mlx")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--overlap", type=int, default=400)
    ap.add_argument("--no-critic", action="store_true")
    a = ap.parse_args()
    client = OllamaClient(a.model, num_ctx=a.num_ctx)
    if not client.available():
        raise SystemExit(f"Ollama model '{a.model}' není dostupný (běží server? `ollama list`?)")
    out = build_curriculum(a.corpus_dir, a.out_dir, client, a.work,
                           max_chars=a.max_chars, overlap=a.overlap, run_critic=not a.no_critic)
    print(f"hotovo -> {out}")


if __name__ == "__main__":
    main()
