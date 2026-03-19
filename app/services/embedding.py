from typing import List
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            print("🧠 Carregando modelo de Embeddings (SentenceTransformer)...")
            # Modelo leve e rápido, ideal para rodar localmente
            cls._model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print("✅ Modelo de Embeddings carregado com sucesso!")
        return cls._instance

    def generate_embedding(self, text: str) -> List[float]:
        """
        Gera o vetor de embedding para o texto fornecido.
        O modelo all-MiniLM-L6-v2 gera vetores de 384 dimensões.
        """
        if not text:
            return []
        
        # O modelo retorna um numpy array, convertemos para lista float
        embedding = self._model.encode(text)
        return embedding.tolist()

# Instância Singleton global
embedding_service = EmbeddingService()
