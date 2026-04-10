
# app.py - ViralGenix PRO v2.3.1
import os, io, re, sqlite3, requests
from pathlib import Path
from datetime import datetime
from typing import Optional
from textwrap import dedent

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import bcrypt

BASE = Path(__file__).parent
DB_PATH = BASE / "viralgenix.db"
LOGOS_DIR = BASE / "logos"
IMAGES_DIR = BASE / "images"
for d in (LOGOS_DIR, IMAGES_DIR):
    d.mkdir(exist_ok=True)

PRODUCT_NAME = "Sol Lima · Content Studio"
BRAND_COLOR = "#C9A84C"
GRAPHITE = "#0A0A0A"
WHITE = "#F5F0E8"
FOREST = "#1B3A2D"

OPENAI_KEY = os.environ.get("VIRAL_API_KEY", "").strip()
USE_LLM = bool(OPENAI_KEY)

def call_llm(sys_prompt: str, user_prompt: str) -> str:
    if not USE_LLM:
        raise RuntimeError("No API key found")
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=1200,
    )
    return resp.choices[0].message.content.strip()

def dalle_image_url(prompt: str, size="1024x1024") -> str:
    if not USE_LLM:
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        res = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
        return res.data[0].url
    except Exception:
        return ""

def create_canvas(size: str) -> Image.Image:
    sizes = {"IG_Q": (1080,1080), "VERT": (1080,1920), "FB": (1200,630), "YT": (1280,720)}
    w, h = sizes.get(size, (1080,1080))
    return Image.new("RGB", (w, h), (13, 26, 74))

def draw_text_on_image(base_img: Image.Image, title: str, subtitle: str = "") -> Image.Image:
    img = base_img.convert("RGBA").copy()
    draw = ImageDraw.Draw(img)
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    ov = ImageDraw.Draw(overlay)
    ov.rectangle([(0,0),(W,int(H*0.25))], fill=(0,0,0,140))
    ov.rectangle([(0,int(H*0.75)),(W,H)], fill=(0,0,0,140))
    ov.rectangle([(1,1),(W-2,H-2)], outline=(30,80,200,180), width=2)
    img = Image.alpha_composite(img, overlay)
    margin = 30
    draw = ImageDraw.Draw(img)
    draw.text((margin, margin), title[:120], fill=(255,255,255,255))
    if subtitle:
        draw.text((margin, H - 60), subtitle[:160], fill=(255,255,255,255))
    return img.convert("RGB")

def generate_image_dalle(prompt: str, size: str = "1024x1024") -> Path:
    url = dalle_image_url(prompt, size=size)
    if url:
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            p = IMAGES_DIR / f"gen_{int(datetime.utcnow().timestamp())}.png"
            img.save(p)
            return p
        except Exception:
            pass
    bg = create_canvas("IG_Q")
    card = draw_text_on_image(bg, title=prompt[:120], subtitle="(imagem gerada localmente)")
    p = IMAGES_DIR / f"fallback_{int(datetime.utcnow().timestamp())}.png"
    card.save(p, optimize=True)
    return p

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS contents(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, body TEXT, format TEXT, tone TEXT, length TEXT, created_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id))")
    for col in ["format", "tone", "length"]:
        try:
            c.execute(f"ALTER TABLE contents ADD COLUMN {col} TEXT")
        except Exception:
            pass
    conn.commit(); conn.close()

def hash_password(p: str) -> bytes:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt())
def check_password(p: str, h: bytes) -> bool:
    return bcrypt.checkpw(p.encode("utf-8"), h)

def register_user(u, p):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)", (u, hash_password(p), datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def login_user(u, p) -> Optional[dict]:
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (u,))
    row = c.fetchone(); conn.close()
    if row and check_password(p, row["password_hash"]):
        return dict(row)
    return None

def save_content(user_id: int, title: str, body: str, fmt: str, tone: str, length: str):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO contents(user_id,title,body,format,tone,length,created_at) VALUES(?,?,?,?,?,?,?)",
              (user_id, title, body, fmt, tone, length, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def list_contents(user_id: int, fmt_filter: Optional[str] = None):
    conn = get_conn(); c = conn.cursor()
    if fmt_filter and fmt_filter != "Todos":
        c.execute("SELECT * FROM contents WHERE user_id=? AND format=? ORDER BY created_at DESC", (user_id, fmt_filter))
    else:
        c.execute("SELECT * FROM contents WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall(); conn.close(); return rows

def slugify(text: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower()).strip()
    t = re.sub(r"\s+", "-", t)
    return re.sub(r"-+", "-", t)[:80]

FORMATS = ["Instagram Carrossel","TikTok Script","Facebook Post","YouTube Shorts","X/Twitter Thread","Artigo SEO (Monetizavel)"]
TONES   = ["impactante","emocional","educativo","divertido","provocativo"]
LENGTHS = ["curto","medio","longo"]

def platform_prompt(fmt, idea, tone, length):
    if fmt == "Instagram Carrossel":
        return ("Carrossel IG sobre: {idea}\nTom: {tone}. Tamanho: {length}.\n"
                "- 7 slides numerados (1/7..7/7).\n- 1: gancho forte; 2-6: valor pratico; 7: CTA.\n- Hashtags ao final.").format(idea=idea,tone=tone,length=length)
    if fmt == "TikTok Script":
        return ("Roteiro TikTok sobre: {idea}\nTom: {tone}. Tamanho: {length}.\n"
                "- 3 atos (gancho, desenvolvimento, CTA).\n- Fala natural + descricao visual curta.").format(idea=idea,tone=tone,length=length)
    if fmt == "Facebook Post":
        return ("Post FB sobre: {idea}\nTom: {tone}. Tamanho: {length}.\n"
                "- Abertura c/ historia/pergunta; 2-3 paragrafos de valor; CTA emocional.\n- 3 titulos chamativos.").format(idea=idea,tone=tone,length=length)
    if fmt == "YouTube Shorts":
        return ("Roteiro Shorts sobre: {idea}\nTom: {tone}. Tamanho: {length}.\n"
                "- Gancho (<=3s), desenvolvimento (40s), CTA final.\n- Legenda curta + 5 hashtags.").format(idea=idea,tone=tone,length=length)
    if fmt == "X/Twitter Thread":
        return ("Thread X/Twitter sobre: {idea}\nTom: {tone}. Tamanho: {length}.\n"
                "- 6 a 10 tweets numerados (<=260 chars).\n- Feche com CTA.").format(idea=idea,tone=tone,length=length)
    return "{fmt} sobre: {idea} — tom {tone}, tamanho {length}.".format(fmt=fmt,idea=idea,tone=tone,length=length)

def local_generate(fmt, idea, tone, length):
    base = platform_prompt(fmt, idea, tone, length)
    if fmt == "Instagram Carrossel":
        slides = ["1/7 — GANCHO poderoso.","2/7 — Insight pratico #1.","3/7 — Micro-historia + aprendizado.",
                  "4/7 — 3 bullets acionaveis.","5/7 — Erro comum + correcao.","6/7 — Micro-desafio hoje.","7/7 — CTA: comente; siga; salve."]
        return base + "\n\n" + "\n".join(slides) + "\n\n#hashtags: #conteudo #viralgenix"
    if fmt == "TikTok Script":
        return base + "\n\nGANCHO (0-3s) — pergunta direta.\nDESENV (40s) — 3 passos curtos.\nCTA (5-7s) — seguir + comentar."
    if fmt == "Facebook Post":
        return base + "\n\nTITULOS:\n- Hoje voce precisa ler isso\n- O erro silencioso\n- O segredo simples\n\nPOST: Abertura forte, 3 aprendizados, CTA final."
    if fmt == "YouTube Shorts":
        return base + "\n\nGANCHO: frase curta.\nROTEIRO: 5-6 falas com [visual].\nCTA: seguir + comentario.\n#shorts"
    if fmt == "X/Twitter Thread":
        tweets = ["{}/10 — insight curto.".format(i) for i in range(1,7)]
        return base + "\n\n" + "\n".join(tweets) + "\nCTA final: siga e salve."
    return base + "\nConteudo base (local)."

def generate_for_format(fmt, idea, tone, length):
    sys = "Voce e estrategista senior de conteudo. Entrega pratica, humana, ganchos fortes."
    user = platform_prompt(fmt, idea, tone, length)
    try:
        return call_llm(sys, user)
    except Exception:
        return local_generate(fmt, idea, tone, length)

def generate_card(style: str, title: str, subtitle: str, size_code: str, user_img: Optional[Image.Image]=None) -> Path:
    base = user_img.convert("RGB") if user_img else create_canvas(size_code)
    final = draw_text_on_image(base, title or "Titulo", subtitle)
    p = IMAGES_DIR / "card_{}_{}_{}.png".format(slugify(title or "titulo"), size_code, int(datetime.utcnow().timestamp()))
    final.save(p, optimize=True)
    return p

def generate_blog_article(kw: str, audience: str, country_lang: str, intent: str, length_words: int, n_images: int, brand: str) -> dict:
    sys = "Editor SEO: gere H1 unico, H2/H3 coerentes, meta/OG/Twitter, FAQPage, alt-text, paragrafos curtos, voz ativa, acessibilidade."
    user = "Palavra-chave foco: {kw}\nPublico: {aud}\nPais/idioma: {cl}\nIntencao: {it}\nTamanho: ~{lw} palavras\nMarca: {br}\nEstrutura: H1, meta, 4-6 H2, image_hint, 4-6 FAQs, conclusao com CTA.".format(
        kw=kw, aud=audience, cl=country_lang, it=intent, lw=length_words, br=brand
    )
    try:
        txt = call_llm(sys, user)
        if len(txt.strip()) < 300:
            raise RuntimeError("LLM short")
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else "{}: guia completo".format(kw.title())
        meta_title = title if len(title) <= 60 else title[:57] + "..."
        meta_desc = "Guia pratico e atualizado sobre {} para {}.".format(kw, audience)
        blocks, cur = [], {"h2": None, "paragraphs": [], "bullets": [], "image_hint": None}
        for l in lines[1:]:
            if l.startswith("## "):
                if cur["h2"] or cur["paragraphs"] or cur["bullets"]:
                    blocks.append(cur)
                cur = {"h2": l[3:].strip(), "paragraphs": [], "bullets": [], "image_hint": None}
            elif l.startswith("- "):
                cur["bullets"].append(l[2:].strip())
            elif l.lower().startswith("image_hint:"):
                cur["image_hint"] = l.split(":",1)[1].strip()
            else:
                cur["paragraphs"].append(l)
        if cur["h2"] or cur["paragraphs"] or cur["bullets"]:
            blocks.append(cur)
        if not blocks:
            blocks = [{"h2": "O que e {}".format(kw), "paragraphs":["Entenda {} de forma simples.".format(kw)], "bullets":["Exemplo pratico","Erro comum"], "image_hint":"pessoa usando smartphone"}]
        faq = [{"q": "{} funciona para iniciantes?".format(kw), "a": "Sim. Com passos simples, voce comeca hoje."},
               {"q": "Quanto tempo para ver resultados com {}?".format(kw), "a": "Depende da pratica, mas consistencia acelera."}]
        return {"title": title, "meta_title": meta_title, "meta_desc": meta_desc, "h2_blocks": blocks[:6], "faq": faq[:6], "n_images": n_images}
    except Exception:
        title = "{}: guia pratico para {}".format(kw.title(), audience)
        meta_title = title[:60]
        meta_desc = "Guia direto sobre {}, pensado para {}.".format(kw, audience)
        h2_blocks = [
            {"h2": "O que e {}".format(kw), "paragraphs":["Definicao simples de {} e por que importa.".format(kw)], "bullets":["Exemplo 1","Exemplo 2"], "image_hint":"close de celular/notebook"},
            {"h2": "Como aplicar {} no dia a dia".format(kw), "paragraphs":["Passo 1, 2, 3."], "bullets":["Dica rapida","Erro comum"], "image_hint":"maos em acao"},
            {"h2": "Checklist rapido", "paragraphs":["Use esta lista antes de publicar."], "bullets":["Titulo claro","Paragrafos curtos","CTA"], "image_hint":"ilustracao minimalista"},
        ]
        faq = [{"q": "{} serve para mim?".format(kw), "a": "Sim, se voce quer resultado sem enrolacao."}]
        return {"title": title, "meta_title": meta_title, "meta_desc": meta_desc, "h2_blocks": h2_blocks, "faq": faq, "n_images": n_images}

def build_article_html(struct: dict, kw: str, brand: str, want_images: bool):
    slug = slugify(kw)
    image_paths = []
    if want_images and struct.get("n_images", 0) > 0:
        hero_hint = struct["h2_blocks"][0].get("image_hint") or "foto realista sobre {}".format(kw)
        hero = generate_image_dalle(hero_hint + ", alta qualidade, realista, contraste bom")
        hero_name = "{}-hero.png".format(slug); (IMAGES_DIR/hero_name).write_bytes(hero.read_bytes())
        image_paths.append(IMAGES_DIR/hero_name)
        count = max(0, struct["n_images"] - 1)
        for i in range(count):
            hint = (struct["h2_blocks"][i % len(struct["h2_blocks"])].get("image_hint") or "conceito de {} #{}".format(kw, i+1))
            p = generate_image_dalle(hint + ", alta qualidade, realista, contraste bom")
            name = "{}-img-{}.png".format(slug, i+1)
            (IMAGES_DIR/name).write_bytes(p.read_bytes())
            image_paths.append(IMAGES_DIR/name)

    faq_items = "".join(['{{"@type":"Question","name":"{}","acceptedAnswer":{{"@type":"Answer","text":"{}"}}}}'.format(q["q"], q["a"]) for q in struct["faq"]])
    jsonld = """
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Article","headline":"{title}","about":"{kw}","author":{{"@type":"Person","name":"{brand}"}}, "datePublished":"{date}","image":[{imgs}]}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{faq}]}}
</script>
""".format(title=struct['title'], kw=kw, brand=brand, date=str(datetime.utcnow().date()), imgs=", ".join(['"{}"'.format(p.name) for p in image_paths]), faq=faq_items)

    og_img = image_paths[0].name if image_paths else ""
    head = """
<meta charset="utf-8"/>
<title>{mt}</title>
<meta name="description" content="{md}"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta property="og:title" content="{mt}"/>
<meta property="og:description" content="{md}"/>
{ogimg}
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{mt}"/>
<meta name="twitter:description" content="{md}"/>
{twimg}
""".format(mt=struct['meta_title'], md=struct['meta_desc'], ogimg=("<meta property='og:image' content='{}'/>".format(og_img) if og_img else ""), twimg=("<meta name='twitter:image' content='{}'/>".format(og_img) if og_img else ""))

    styles = """
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Open Sans,Helvetica Neue,sans-serif;margin:0;padding:0 16px;line-height:1.6;background:#fff;color:#111}
 header{max-width:900px;margin:24px auto}
 main{max-width:900px;margin:16px auto}
 h1{font-size:2.0rem;margin:16px 0 8px}
 h2{font-size:1.4rem;margin:20px 0 8px}
 h3{font-size:1.1rem;margin:16px 0 8px}
 p{margin:8px 0}
 ul{margin:8px 0 16px 20px}
 figure{margin:16px 0}
 figcaption{font-size:.9rem;color:#555}
 .meta{color:#444;font-size:.95rem}
</style>
"""

    hero_tag = '<img src="{src}" alt="{alt}" width="1200" height="630" loading="lazy" style="max-width:100%;height:auto;"/>'.format(src=og_img, alt=kw+" — imagem destaque") if og_img else ""
    sections = []
    for i, b in enumerate(struct["h2_blocks"], start=1):
        pars = "".join(["<p>{}</p>".format(p) for p in b["paragraphs"]])
        bulls = "<ul>{}</ul>".format("".join(["<li>{}</li>".format(x) for x in b["bullets"]])) if b["bullets"] else ""
        img_inline = ""
        if i < len(image_paths):
            ip = image_paths[i].name
            img_inline = '<figure><img src="{ip}" alt="{alt}" width="1200" height="800" loading="lazy" style="max-width:100%;height:auto;"/><figcaption>{cap}</figcaption></figure>'.format(ip=ip, alt="{} — {}".format(kw, b["h2"]), cap=b["h2"])
        sections.append("<section><h2>{h2}</h2>{pars}{bulls}{img}</section>".format(h2=b["h2"], pars=pars, bulls=bulls, img=img_inline))

    faq_html = "<section><h2>Perguntas Frequentes</h2>" + "".join(["<h3>{}</h3><p>{}</p>".format(x["q"], x["a"]) for x in struct["faq"]]) + "</section>"

    html = "<!doctype html><html lang='pt-BR'><head>{head}{styles}{jsonld}</head><body><header><h1>{h1}</h1><p class='meta'>Por {brand} • Atualizado em {date}</p>{hero}</header><main>{sections}{faq}</main></body></html>".format(
        head=head, styles=styles, jsonld=jsonld, h1=struct['title'], brand=brand, date=str(datetime.utcnow().date()), hero=hero_tag, sections="".join(sections), faq=faq_html
    )

    md = "# {title}\n\n".format(title=struct['title']) + "\n\n".join(["## {h}\n\n{p}".format(h=b["h2"], p="\n".join(b["paragraphs"])) for b in struct["h2_blocks"]]) + "\n\n## Perguntas Frequentes\n" + "\n".join(["**{q}**\n\n{a}".format(q=x["q"], a=x["a"]) for x in struct["faq"]])
    return html, image_paths, md

def publish_instagram(caption: str, image_path: Optional[Path], page_id: str, access_token: str, dry_run=True):
    payload = {"caption": caption, "image_path": str(image_path) if image_path else None, "page_id": page_id, "access_token": access_token}
    if dry_run:
        return {"ok": True, "dry_run": True, "platform": "instagram", "payload": payload}
    return {"ok": False, "error": "Not implemented in demo"}

def publish_tiktok(caption: str, video_path: Optional[Path], access_token: str, dry_run=True):
    payload = {"caption": caption, "video_path": str(video_path) if video_path else None, "access_token": access_token}
    if dry_run:
        return {"ok": True, "dry_run": True, "platform": "tiktok", "payload": payload}
    return {"ok": False, "error": "Not implemented in demo"}

def publish_youtube(title: str, description: str, video_path: Optional[Path], api_key: str, dry_run=True):
    payload = {"title": title, "description": description, "video_path": str(video_path) if video_path else None, "api_key": api_key}
    if dry_run:
        return {"ok": True, "dry_run": True, "platform": "youtube", "payload": payload}
    return {"ok": False, "error": "Not implemented in demo"}

def pro_css():
    st.markdown(f"""
    <style>
      .stApp {{
        background: linear-gradient(180deg, {GRAPHITE} 0%, {FOREST} 100%);
        color: {WHITE};
      }}
      h1, h2, h3, h4, h5, h6 {{ color: {WHITE}; }}
      .stButton>button {{
        background: {BRAND_COLOR};
        color: {WHITE};
        border: 0;
        border-radius: 10px;
        font-weight: 800;
        padding: 10px 16px;
        box-shadow: 0 6px 14px rgba(201,168,76,0.25);
        transition: transform .06s ease, box-shadow .2s ease, opacity .2s ease;
      }}
      .stButton>button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 10px 20px rgba(201,168,76,0.35);
        opacity: .95;
      }}
      .stTextInput>div>div>input,
      .stTextArea textarea,
      .stSelectbox div[data-baseweb="select"] {{
        background: rgba(27, 58, 45, 0.55) !important;
        color: {WHITE} !important;
        border: 1px solid #2D5A3D !important;
        border-radius: 10px !important;
      }}
      .stTextInput>div>div>input::placeholder,
      .stTextArea textarea::placeholder {{
        color: rgba(255,255,255,0.55) !important;
      }}
      .hero, .stTabs [data-baseweb="tab-list"] + div, .stFileUploader, .stDataFrame, .stAlert {{
        background: rgba(27, 58, 45, 0.35) !important;
        border: 1px solid #2D5A3D !important;
        border-radius: 12px !important;
      }}
      .stTabs [data-baseweb="tab"] {{
        color: {WHITE} !important;
      }}
      .badge {{
        background: {BRAND_COLOR};
        color: {WHITE};
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 800;
        margin-left: 8px;
        box-shadow: 0 4px 12px rgba(201,168,76,0.35);
      }}
      pre, code {{
        background: #0F2A1A !important;
        color: #F5F0E8 !important;
        border-radius: 10px !important;
        border: 1px solid #2D5A3D !important;
      }}
      a {{ color: {BRAND_COLOR} !important; text-decoration: none !important; }}
      a:hover {{ text-decoration: underline !important; }}
    </style>
    """, unsafe_allow_html=True)

def pro_header():
    st.title(f"{PRODUCT_NAME} <span class='badge'>PRO</span>", anchor=False)
    st.markdown("Crie conteúdo com sua voz, seu método e sua marca. Roteiros, carrosseis e artigos SEO com 1 clique.", unsafe_allow_html=True)
    if not USE_LLM:
        st.info("IA local ativa (sem chave). Para resultados melhores, defina VIRAL_API_KEY.")

def main():
    ensure_schema()
    st.set_page_config(page_title="Sol Lima · Content Studio", page_icon="🌿", layout="wide")
    pro_css(); pro_header()

    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "last_title" not in st.session_state:
        st.session_state.last_title = None
    if "last_slides" not in st.session_state:
        st.session_state.last_slides = []

    if "menu_override" not in st.session_state:
        st.session_state.menu_override = None

    menu_opts = ["Entrar","Registrar","Dashboard","Meus Conteudos","Publicar","Sobre"]
    default_idx = 2 if st.session_state.get("user") else 0
    if st.session_state.menu_override == "Dashboard":
        default_idx = menu_opts.index("Dashboard")
        st.session_state.menu_override = None

    menu = st.sidebar.selectbox("Menu", menu_opts, index=default_idx)

    if menu == "Registrar":
        with st.form("register"):
            u = st.text_input("E-mail (sera seu usuario)")
            p = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Criar conta")
        if ok:
            try:
                register_user(u, p)
                st.success("Conta criada! Va em Entrar.")
            except Exception as e:
                st.error(f"Erro ao registrar: {e}")
        return

    if menu == "Entrar":
        with st.form("login"):
            u = st.text_input("Usuario (email)")
            p = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Entrar")
        if ok:
            user = login_user(u, p)
            if user:
                st.session_state.user = user
                st.success(f"Logada como {u}")
                st.session_state.menu_override = "Dashboard"
                st.rerun()
            else:
                st.error("Usuario/senha invalidos.")
        return

    if menu == "Dashboard":
        if "user" not in st.session_state:
            st.warning("Faca login primeiro."); return
        user = st.session_state.user

        colA, colB = st.columns([2,1])
        with colA:
            st.subheader(f"Bem-vinda, {user['username']}")
            st.markdown("<div class='hero'><b>Crie conteudo pronto para publicar</b>: formatos, imagens e artigos SEO.</div>", unsafe_allow_html=True)

            idea = st.text_area("De o insight, topico ou frase", height=120, placeholder="Ex.: Meu pug quer brincar na cama (rotina + humor)")
            fmt = st.selectbox("Formato", FORMATS, index=0)
            tone = st.selectbox("Tom", TONES, index=0)
            length = st.selectbox("Tamanho", LENGTHS, index=1)
            auto_save = st.toggle("Salvar automaticamente apos gerar", value=True)

            if fmt != "Artigo SEO (Monetizavel)":
                if st.button("Gerar Conteudo 🚀", use_container_width=True):
                    if not idea.strip():
                        st.error("Escreva uma ideia primeiro.")
                    else:
                        result = generate_for_format(fmt, idea.strip(), tone, length)
                        st.session_state.last_result = result
                        st.session_state.last_title = "{}: {}".format(fmt, idea.strip()[:50])
                        slides = []
                        for line in result.splitlines():
                            ln = line.strip()
                            if "/" in ln and ln.split()[0].count("/") == 1 and any(ln.startswith("{}/".format(i)) for i in range(1,11)):
                                slides.append(ln)
                        st.session_state.last_slides = slides

                        st.markdown("#### Resultado")
                        st.code(result, language="markdown")

                        if auto_save:
                            save_content(user["id"], st.session_state.last_title, result, fmt, tone, length)
                            st.success("Conteudo salvo automaticamente ✅")

                if st.session_state.last_result:
                    st.markdown("#### Resultado (persistente)")
                    st.code(st.session_state.last_result, language="markdown")

                st.markdown("---")
                st.markdown("### Geracao de Imagem (PRO) — sem sair do seu conteudo")

                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    style = st.selectbox("Estilo", ["Meme", "Quote", "Foto+Texto"], index=0)
                    title_img = st.text_input("Titulo curto p/ imagem", value=(idea[:60] if idea else ""))
                    subtitle_img = st.text_input("Subtitulo (opcional)", value="")
                with col_img2:
                    size_code = st.selectbox("Tamanho/Plataforma", ["IG_Q","VERT","FB","YT"], index=0, help="IG_Q=1080x1080 • VERT=1080x1920 • FB=1200x630 • YT=1280x720")
                    user_img_up = st.file_uploader("Ou envie sua imagem base", type=["png","jpg","jpeg","webp"])
                    user_img = Image.open(user_img_up).convert("RGB") if user_img_up else None

                gcol1, gcol2, gcol3 = st.columns(3)
                with gcol1:
                    if st.button("Gerar Card Local 🖼️"):
                        p = generate_card(style, title_img or "Titulo", subtitle_img, size_code, user_img=user_img)
                        st.image(str(p), caption=p.name, use_column_width=True)
                        st.success("Imagem pronta (pasta images/).")
                with gcol2:
                    if st.button("Imagem IA (DALL·E)"):
                        prompt_img = st.text_input("Prompt de imagem (detalhado)", value=idea or "conceito criativo minimalista, realista")
                        if prompt_img:
                            p = generate_image_dalle(prompt_img)
                            st.image(str(p), caption=p.name, use_column_width=True)
                            st.info("Se sua organizacao nao estiver verificada, gerei um card local. Para liberar IA, verifique a org na OpenAI.")
                with gcol3:
                    if st.button("Gerar Carrossel IG (cards)"):
                        if not st.session_state.last_slides:
                            st.warning("Gere o conteudo do carrossel primeiro (para eu extrair 1/7, 2/7...).")
                        else:
                            paths = []
                            for i, slide in enumerate(st.session_state.last_slides, start=1):
                                p = generate_card("Meme", slide, "", "IG_Q", user_img=user_img)
                                paths.append(p)
                            st.success("Gerei {} slides do carrossel (pasta images/).".format(len(paths)))
                            for p in paths:
                                st.image(str(p), caption=p.name, use_column_width=True)

            if fmt == "Artigo SEO (Monetizavel)":
                st.markdown("### Gerar Artigo SEO (Monetizavel)")
                kw = st.text_input("Palavra-chave foco", placeholder="ex.: relacionamento saudavel com filhos")
                audience = st.text_input("Publico", value="Maes e pais iniciantes")
                country_lang = st.text_input("Pais/Idioma", value="Brasil/pt-BR")
                intent = st.selectbox("Intencao de busca", ["Informacional","Transacional","Navegacional"], index=0)
                length_words = st.slider("Tamanho (palavras)", 1000, 3000, 1600, step=100)
                n_images = st.slider("Imagens (inclui Hero)", 1, 5, 3)
                brand = st.text_input("Assinatura/Marca (E-E-A-T)", value="Sol Lima")
                want_images = st.toggle("Gerar imagens automaticamente", value=True)

                if st.button("Gerar Artigo SEO ✅", use_container_width=True):
                    if not kw.strip():
                        st.error("Informe a palavra-chave foco.")
                    else:
                        struct = generate_blog_article(kw.strip(), audience.strip(), country_lang.strip(), intent, length_words, n_images, brand.strip())
                        html, imgs, md = build_article_html(struct, kw.strip(), brand.strip(), want_images)
                        st.success("Artigo gerado com sucesso — pronto para publicar.")
                        st.download_button("Baixar .html (SEO pronto)", data=html, file_name="{}.html".format(slugify(kw)), mime="text/html")
                        st.download_button("Baixar .md (opcional)", data=md, file_name="{}.md".format(slugify(kw)), mime="text/markdown")
                        if imgs:
                            st.caption("Imagens geradas:")
                            for p in imgs:
                                st.image(str(p), caption=p.name, use_column_width=True)

        with colB:
            st.subheader("Logotipo (opcional)")
            logo_file = st.file_uploader("Enviar logo", type=["png","jpg","jpeg","webp"])
            if logo_file:
                name = "{}_{}.png".format(user['username'], int(datetime.utcnow().timestamp()))
                path = LOGOS_DIR / name
                Image.open(logo_file).convert("RGBA").save(path)
                st.success("Logo salva.")
            st.markdown("---")
            st.markdown("### Plano Pro 🔥")
            st.caption("Modelos por nicho + publicacao 1-clique (OAuth). Em breve.")
        return

    if menu == "Meus Conteudos":
        if "user" not in st.session_state: st.warning("Faca login primeiro."); return
        user = st.session_state.user
        st.subheader("Seu acervo")
        fmt_filter = st.selectbox("Filtrar por formato", ["Todos"] + FORMATS, index=0)
        rows = list_contents(user["id"], fmt_filter)
        if not rows:
            st.info("Nenhum conteudo ainda. Gere algo no Dashboard 😉"); return
        for r in rows:
            st.markdown("**{}** · {} · {}/{} · {}".format(r['title'], r['format'], r['tone'], r['length'], r['created_at']))
            st.write(r["body"])
            st.download_button("Baixar .txt", data=r["body"], file_name="{}.txt".format(r['title'].replace(" ","_")), mime="text/plain")
            st.markdown("---")
        return

    if menu == "Publicar":
        if "user" not in st.session_state: st.warning("Faca login primeiro."); return
        st.subheader("Publicar (scaffolding)")
        st.caption("Para publicar direto, o cliente autoriza a rede (OAuth). Aqui mostramos o payload (dry-run).")

        tab1, tab2, tab3 = st.tabs(["Instagram","TikTok","YouTube"])
        with tab1:
            ig_caption = st.text_area("Legenda / texto", height=120)
            ig_page_id = st.text_input("Instagram Business Page ID (Graph API)")
            ig_token = st.text_input("Access Token", type="password")
            img_up = st.file_uploader("Imagem para publicar (opcional)", type=["png","jpg","jpeg","webp"])
            img_path = None
            if img_up:
                img_obj = Image.open(img_up).convert("RGBA")
                img_path = IMAGES_DIR / "ig_{}.png".format(int(datetime.utcnow().timestamp()))
                img_obj.save(img_path)
                st.image(str(img_path), caption="Previa IG", use_column_width=True)
            if st.button("Dry-run Instagram"):
                res = publish_instagram(ig_caption, img_path, ig_page_id, ig_token, dry_run=True)
                st.json(res)

        with tab2:
            tk_caption = st.text_input("Legenda (TikTok)")
            tk_token = st.text_input("TikTok Access Token", type="password")
            st.caption("Selecione um video (quando disponivel). Nesta demo, exibimos so o payload.")
            if st.button("Dry-run TikTok"):
                res = publish_tiktok(tk_caption, None, tk_token, dry_run=True)
                st.json(res)

        with tab3:
            yt_title = st.text_input("Titulo (YouTube)")
            yt_desc = st.text_area("Descricao (YouTube)")
            yt_key = st.text_input("YouTube API Key", type="password")
            if st.button("Dry-run YouTube"):
                res = publish_youtube(yt_title, yt_desc, None, yt_key, dry_run=True)
                st.json(res)
        return

    st.header("Sobre")
    st.write("ViralGenix PRO v2.3.1 — azul profundo, artigos SEO 100% prontos, cards e carrosseis profissionais, e publicacao preparada.")
    if not USE_LLM:
        st.caption("Dica: configure VIRAL_API_KEY para geracao ainda mais poderosa.")
    return

if __name__ == "__main__":
    main()
