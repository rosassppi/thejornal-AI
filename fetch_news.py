#!/usr/bin/env python3
"""
Radar.IA — coletor de notícias de Inteligência Artificial
Busca RSS feeds (Brasil + Mundo), extrai dados relevantes e gera news.json
Zero custo: sem chamadas a LLM, sem banco de dados, só RSS público.
"""

import feedparser
import json
import re
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from html import unescape

try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False

# ============================================================
# CONFIGURAÇÃO DE FONTES
# Cada fonte tem: nome, url do feed, região (brasil/mundo), categoria padrão
# ============================================================

FEEDS = [
    # --- Mundo: imprensa tech geral com cobertura forte de IA ---
    {"name": "TechCrunch",      "url": "https://techcrunch.com/feed/",                                    "region": "mundo", "category": "Produtos",  "generic": True},
    {"name": "VentureBeat",     "url": "https://venturebeat.com/category/ai/feed/",                       "region": "mundo", "category": "Produtos",  "generic": False},
    {"name": "The Verge",       "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml","region": "mundo", "category": "Mundo",     "generic": False},
    {"name": "Ars Technica",    "url": "https://arstechnica.com/ai/feed/",                                "region": "mundo", "category": "Mundo",     "generic": False},

    # --- Mundo: fontes especializadas / oficiais de IA ---
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "region": "mundo", "category": "Pesquisa",  "generic": False},
    {"name": "MarkTechPost",    "url": "https://www.marktechpost.com/feed/",                              "region": "mundo", "category": "Pesquisa",  "generic": False},
    {"name": "OpenAI",          "url": "https://openai.com/news/rss.xml",                                 "region": "mundo", "category": "Modelos",   "generic": False},
    {"name": "Hugging Face",    "url": "https://huggingface.co/blog/feed.xml",                            "region": "mundo", "category": "Modelos",   "generic": False},
    {"name": "Google AI Blog",  "url": "https://blog.google/technology/ai/rss/",                          "region": "mundo", "category": "Modelos",   "generic": False},

    # --- Brasil: imprensa tech geral, filtrada por palavra-chave de IA ---
    {"name": "Tecnoblog",       "url": "https://tecnoblog.net/feed/",                                     "region": "brasil", "category": "Brasil",   "generic": True},
    {"name": "Olhar Digital",   "url": "https://olhardigital.com.br/feed/",                               "region": "brasil", "category": "Brasil",   "generic": True},
    {"name": "Canaltech",       "url": "https://canaltech.com.br/rss/",                                   "region": "brasil", "category": "Brasil",   "generic": True},
]

# Palavras-chave usadas para filtrar apenas notícias relevantes de IA
# (necessário para feeds genéricos de tecnologia, como Tecnoblog e Olhar Digital)
# IMPORTANTE: o matching usa \b (fronteira de palavra) para "ia" e "ai" isoladas,
# para não confundir com substrings dentro de outras palavras comuns
# (ex: "loteria", "dia", "notícia", "história" contêm "ia" mas não são sobre IA).
AI_KEYWORDS_EXACT_WORD = ["ia", "ai", "ias", "ais"]  # exigem \b...\b (palavra isolada)

AI_KEYWORDS_SUBSTRING = [
    "inteligência artificial", "intelig", "chatgpt", "gpt-", "gpt5", "gpt-5",
    "claude", "anthropic", "openai", "gemini", "llm", "machine learning",
    "deep learning", "rede neural", "redes neurais", "modelo de linguagem",
    "artificial intelligence", "copilot", "midjourney", "deepseek",
    "chatbot", "agente de ia", "agentes de ia", "ai agent", "llms",
]

MAX_ITEMS_PER_FEED = 8
OUTPUT_FILE = "news.json"
MAX_TOTAL_ITEMS = 90

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def fetch_feed(url, timeout=12):
    """Baixa e faz o parse de um feed RSS, com header de navegador."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return feedparser.parse(data)


def strip_html(raw_html):
    """Remove tags HTML de um texto, deixando só o texto puro."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text, max_chars=180):
    """Corta o texto em um limite de caracteres, terminando em palavra cheia."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def extract_image(entry):
    """Tenta achar uma imagem de capa em vários formatos possíveis de RSS."""
    if entry.get("media_thumbnail"):
        return entry.media_thumbnail[0].get("url")

    if entry.get("media_content"):
        for m in entry.media_content:
            if m.get("url"):
                return m["url"]

    for link in entry.get("links", []):
        if "image" in str(link.get("type", "")):
            return link.get("href")

    content_html = ""
    if entry.get("content"):
        content_html = entry.content[0].get("value", "")
    if not content_html:
        content_html = entry.get("summary", "")

    match = re.search(r'<img[^>]+src="([^"]+)"', content_html)
    if match:
        return match.group(1)

    return None


def parse_date(entry):
    """Extrai a data de publicação como timestamp ISO UTC. Usa agora() se não achar."""
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            try:
                dt = datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def matches_ai_keywords(title, summary):
    """Verifica se o texto contém alguma palavra-chave de IA (case-insensitive).

    Para as siglas curtas e ambíguas ("ia", "ai"), exige fronteira de palavra
    real (\\b) para não confundir com substrings dentro de outras palavras
    comuns como "loteria", "dia", "notícia", "história", "said", "main", etc.
    """
    haystack = f"{title} {summary}".lower()

    for kw in AI_KEYWORDS_SUBSTRING:
        if kw in haystack:
            return True

    for kw in AI_KEYWORDS_EXACT_WORD:
        if re.search(rf"\b{re.escape(kw)}\b", haystack):
            return True

    return False


def make_id(link):
    """Gera um id estável a partir do link, pra evitar duplicados entre execuções."""
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]


def collect_feed(source):
    """Coleta e normaliza os itens de uma única fonte RSS."""
    items = []
    try:
        parsed = fetch_feed(source["url"])
    except Exception as exc:
        print(f"  [erro] {source['name']}: {exc}")
        return items

    entries = parsed.entries[:MAX_ITEMS_PER_FEED * 3]  # margem maior pra filtro de keywords
    needs_keyword_filter = source.get("generic", False)

    for entry in entries:
        title = strip_html(entry.get("title", "")).strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        raw_summary = entry.get("summary", "") or entry.get("description", "")
        summary = truncate(strip_html(raw_summary))

        # Para fontes genéricas (não especializadas em IA), filtra por palavra-chave
        if needs_keyword_filter and not matches_ai_keywords(title, summary):
            continue

        items.append({
            "id": make_id(link),
            "title": title,
            "summary": summary,
            "link": link,
            "image": extract_image(entry),
            "source": source["name"],
            "region": source["region"],
            "category": source["category"],
            "published_at": parse_date(entry),
        })

        if len(items) >= MAX_ITEMS_PER_FEED:
            break

    print(f"  {source['name']}: {len(items)} itens coletados")
    return items


def load_translation_cache():
    """Carrega traduções já feitas em execuções anteriores, usando o próprio
    news.json existente como cache (evita re-traduzir o que já foi traduzido,
    poupando chamadas ao serviço gratuito de tradução)."""
    cache = {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            previous = json.load(f)
        for item in previous.get("items", []):
            if item.get("id") and item.get("title"):
                cache[item["id"]] = {
                    "title": item["title"],
                    "summary": item.get("summary", ""),
                }
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cache


def translate_item(item, translator, cache):
    """Traduz título e resumo de um item 'mundo' (inglês) para português.
    Usa cache quando disponível. Em caso de falha de tradução (rede instável,
    limite do serviço gratuito), mantém o texto original em inglês —
    nunca quebra a coleta por causa de um problema de tradução."""
    if item["region"] != "mundo":
        return item

    cached = cache.get(item["id"])
    if cached:
        item["title"] = cached["title"]
        item["summary"] = cached["summary"]
        return item

    if not TRANSLATION_AVAILABLE or translator is None:
        return item

    try:
        item["title"] = translator.translate(item["title"]) or item["title"]
    except Exception as exc:
        print(f"  [aviso] falha ao traduzir título '{item['title'][:40]}...': {exc}")

    try:
        if item["summary"]:
            item["summary"] = translator.translate(item["summary"]) or item["summary"]
    except Exception as exc:
        print(f"  [aviso] falha ao traduzir resumo de '{item['title'][:40]}...': {exc}")

    return item


def main():
    print("Radar.IA — coletando feeds...\n")
    all_items = []
    seen_ids = set()

    for source in FEEDS:
        for item in collect_feed(source):
            if item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])
            all_items.append(item)

    # Ordena por data de publicação, mais recente primeiro
    all_items.sort(key=lambda x: x["published_at"], reverse=True)
    all_items = all_items[:MAX_TOTAL_ITEMS]

    # Traduz título e resumo das notícias internacionais (region "mundo") para
    # português. Usa cache do news.json anterior para não retraduzir o que já
    # foi traduzido, e nunca falha a coleta inteira se a tradução der problema.
    print("\nTraduzindo notícias internacionais...")
    translation_cache = load_translation_cache()
    translator = None
    if TRANSLATION_AVAILABLE:
        try:
            translator = GoogleTranslator(source="en", target="pt")
        except Exception as exc:
            print(f"  [aviso] não foi possível iniciar o tradutor: {exc}")
    else:
        print("  [aviso] biblioteca deep-translator não encontrada; notícias mundiais ficarão em inglês")

    translated_count = 0
    for item in all_items:
        before = item["title"]
        item = translate_item(item, translator, translation_cache)
        if item["title"] != before:
            translated_count += 1
    print(f"  {translated_count} notícias traduzidas (ou recuperadas do cache)")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(all_items),
        "items": all_items,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(all_items)} notícias salvas em {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
