# The Jornal AI

Agregador automático e gratuito de notícias sobre Inteligência Artificial — Brasil e mundo. Layout de jornal de verdade, inspirado no The New York Times: masthead blackletter, colunas, hairlines, tipografia serifada.

Site estático que lê `news.json`, gerado automaticamente todo dia a partir de feeds RSS públicos. Sem servidor, sem banco de dados, sem custo de API.

## Como funciona

1. `fetch_news.py` busca os feeds RSS configurados, filtra o que é relevante para IA, extrai título/resumo/imagem/link e gera `news.json`.
2. O GitHub Actions (`.github/workflows/update-news.yml`) roda esse script automaticamente a cada 6 horas e commita o `news.json` atualizado.
3. O `index.html` lê o `news.json` e monta a "capa" do jornal na hora, no navegador: manchete principal + colunas secundárias + lista terciária.
4. O GitHub Pages serve o site direto do repositório — de graça.

## Layout

- **Masthead** em "Manufacturing Consent" (fonte blackletter de código aberto, inspirada no logotipo do NYT) + linha de data/edição acima e barra de seções abaixo.
- **Capa em 3 colunas**: manchete principal (maior, com imagem), coluna de notícias secundárias (com imagem menor), coluna terciária densa em lista (sem imagem, estilo "últimas").
- **Modo leitura "jornal"**: clicar em qualquer notícia abre em tela cheia com efeito de virar página (como um jornal/livro físico). Navegação por setas laterais, teclado (← →) ou arrastando no celular.

## Como publicar (passo a passo)

1. Crie um repositório novo no GitHub (pode ser público, ex: `the-jornal-ai`).
2. Suba todos os arquivos desta pasta para o repositório (`git init`, `git add .`, `git commit`, `git push`, ou arraste pela interface web do GitHub).
3. No repositório, vá em **Settings → Pages** → em "Source" escolha **Deploy from a branch** → branch `main`, pasta `/ (root)` → Save.
4. Vá em **Settings → Actions → General** → em "Workflow permissions" marque **Read and write permissions** (necessário para o robô poder commitar o `news.json` atualizado).
5. Vá na aba **Actions** do repositório → clique no workflow "Atualizar notícias" → **Run workflow** (botão manual) para gerar o primeiro `news.json` de verdade, com notícias reais.
6. Espere 1-2 minutos, recarregue a aba Pages — o site estará no ar em algo como `https://seu-usuario.github.io/the-jornal-ai/`.

A partir daí, o robô atualiza solo, a cada 6 horas, para sempre.

## Fontes incluídas

**Mundo:** TechCrunch, VentureBeat, The Verge (seção IA), Ars Technica, MIT Technology Review, MarkTechPost, OpenAI News, Hugging Face Blog, Google AI Blog.

**Brasil:** Tecnoblog, Olhar Digital, Canaltech (filtrados por palavra-chave de IA, já que cobrem tecnologia em geral).

Todas verificadas como fontes ativas e confiáveis em junho de 2026. Vale revisitar a lista de tempos em tempos — sites mudam estrutura de feed ou descontinuam RSS.

## Personalizar fontes

Edite a lista `FEEDS` no topo de `fetch_news.py` para adicionar, remover ou trocar fontes RSS. Cada fonte precisa de: nome, URL do feed, região (`brasil` ou `mundo`), categoria padrão, e `generic` (`True` se o site cobre tecnologia em geral e precisa do filtro de palavra-chave de IA, `False` se é especializado em IA).

## Mudar a frequência de atualização

No arquivo `.github/workflows/update-news.yml`, ajuste a linha `cron`. Exemplos:
- `"0 */6 * * *"` → a cada 6 horas (atual)
- `"0 */3 * * *"` → a cada 3 horas
- `"0 8,20 * * *"` → duas vezes por dia, 8h e 20h (horário UTC)
