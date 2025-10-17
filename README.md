# ViralGenix PRO v2.3.1
- Tema azul profundo (autoridade)
- Auto-redirect pro Dashboard apos login
- Artigo SEO (Monetizavel) — HTML pronto com meta/OG/Twitter + JSON-LD (Article/FAQ) + imagens (com fallback local)
- Geracao de imagem PRO (meme/quote/foto+texto) com upload
- Carrossel IG multi-imagem a partir dos slides do texto (1/7...)
- Fallback quando gpt-image-1 estiver bloqueado (403)

## Rodar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export VIRAL_API_KEY='sua_chave_ou_vazio'
streamlit run app.py
