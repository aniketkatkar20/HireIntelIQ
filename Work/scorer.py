from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

def get_similarity_scores(transcript_path):
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        qas = []
        question = ""
        for line in lines:
            if line.startswith("Q: "):
                question = line[3:].strip()
            elif line.startswith("A: "):
                answer = line[3:].strip()
                if question:
                    qas.append((question, answer))
                    question = ""

        if not qas:
            raise ValueError("No valid Q&A pairs found in transcript.")

        # Limit to 10 chunks (10% progress steps)
        total_pairs = len(qas)
        chunk_size = max(1, total_pairs // 10)
        chunks = [qas[i:i + chunk_size] for i in range(0, total_pairs, chunk_size)]
        if len(chunks) > 10:
            chunks = chunks[:10]  # Trim any extra to stay within 100%

        results = []
        all_scores = []

        for i, chunk in enumerate(chunks):
            sim_scores = []
            for question, answer in chunk:
                embeddings = model.encode([question, answer])
                score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                sim_scores.append(score)
                all_scores.append(score)

            avg_score = np.mean(sim_scores) if sim_scores else 0.0
            results.append({
                "progress": f"{(i + 1) * 10}%",
                "score": round(avg_score * 100, 2)
            })

        overall = round(np.mean(all_scores) * 100, 2) if all_scores else 0.0

        return {
            "scores": results,
            "overall": overall
        }

    except Exception as e:
        return {
            "error": str(e),
            "scores": [],
            "overall": None
        }
