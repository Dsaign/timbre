<p align="center">
  <img src="docs/images/timbre-logo.svg" width="96" height="96" alt="logo do timbre">
</p>

<h1 align="center">timbre.</h1>

<p align="center">
  Descreva a música que você quer ouvir com as suas palavras e receba as que combinam.
  <br>
  <a href="https://timbreapp.vercel.app"><strong>timbreapp.vercel.app</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Dsaign/timbre/actions/workflows/ci.yml"><img src="https://github.com/Dsaign/timbre/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/Next.js-16.4-000000?logo=nextdotjs" alt="Next.js 16.4">
  <img src="https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white" alt="FastAPI 0.162">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/PostgreSQL-18%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 18 com pgvector">
</p>

## Sobre

O timbre é um buscador de músicas por descrição. Você escreve o que está a fim de ouvir, em português ou em inglês ("emo para chorar e cantar gritando", "sad indie with female vocals"), e ele devolve as músicas que combinam, num catálogo de cerca de 38 mil faixas. Cada resultado pode ser ouvido pelo Spotify e avaliado com 👍 ou 👎, e esses votos entram no próximo treino do modelo.

Como uma busca funciona:

1. **Catálogo.** As músicas vêm de dados abertos: MusicBrainz para títulos, artistas e tags, AcousticBrainz para rótulos de humor, gênero e voz calculados a partir do áudio, e ListenBrainz para popularidade. Cada música ganha um perfil curto em texto, montado com esses rótulos e tags.
2. **Vetores.** Perfis e descrições viram vetores com o [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) (384 dimensões, ONNX na CPU), guardados no Postgres com pgvector.
3. **Ranking.** Nomes de artista e de música vêm primeiro. O resto junta dois rankings: a similaridade entre vetores, que pode passar por uma projeção treinada, e a correspondência direta entre as palavras da descrição e as tags de cada música.
4. **Avaliação.** Um benchmark de cerca de 1.270 descrições dá nota a cada versão do modelo, e uma versão nova só é promovida se a nota não for menor que a da atual.

## Stack

| Camada | Tecnologia |
|---|---|
| Front | Next.js 16.4, React 19.3, TypeScript 5.9, Tailwind CSS 4.3, Radix UI 1.8 (via shadcn), Lucide 1.62 |
| Back | Python 3.13, FastAPI 0.162, Uvicorn 0.54, psycopg 3.3, NumPy 2.5 |
| Busca | multilingual-e5-small com ONNX Runtime 1.31 e tokenizers 0.23, PostgreSQL 18 com pgvector 0.8.7 |
| Banco | migrations em SQL puro com dbmate 2.37, row-level security por papel |
| Testes | pytest, Vitest 5.0, Playwright 1.64 (Chromium, Firefox, WebKit e a tela de um iPhone 15) |
| Infra | Docker Compose, Caddy 2.11 para TLS, Vercel para o front, uma VPS na Hetzner para o back, GitHub Actions |

Gerenciadores de pacotes: pnpm 12 no `front/` e uv no `back/`.

```
front/     app Next.js
back/      serviço FastAPI, migrations SQL, jobs do worker e a stack do Compose
docs/      decisões de arquitetura (adr/), papéis dos agentes (agents/), pesquisas, operações
scripts/   checagem de drift do OpenAPI e o assistente do primeiro deploy
```

## Como rodar

Você precisa de Docker com Compose, Node 26 com pnpm 12 e [uv](https://docs.astral.sh/uv/).

### Configuração

Os segredos ficam só em `back/.env` e `front/.env.local`, os dois fora do git. Copie os nomes de cada `.env.example` e preencha os valores (`openssl rand -hex 32` para as senhas, o salt e o token; o `FRONT_TOKEN` precisa ser igual nos dois arquivos). `SEARCH_LIMIT_PER_MIN` e `VOTE_LIMIT_PER_HOUR` valem 30 e 60 por visitante se não forem definidos.

### Execução

```bash
cd back
docker compose up -d --wait   # banco, migrations, senhas dos papéis, catálogo inicial, worker e API em 127.0.0.1:8000
cd ../front
pnpm install
pnpm dev                      # mostra "[timbre] back /health → 200 ok" quando o back responde
```

Abra http://localhost:3000. Com `APP_ENV=development` no `back/.env`, a documentação da API fica em http://localhost:8000/docs. Para parar, use `docker compose down` (com `-v`, o banco é apagado).

O primeiro build baixa o modelo e5 (cerca de 470 MB) para dentro da imagem. Depois de subir, o worker leva alguns segundos para montar os vetores das músicas, e até lá as buscas não encontram nada. Uma stack nova começa com um catálogo inicial de cerca de 200 músicas conhecidas; o [docs/operations.md](docs/operations.md#catalog-import) explica como importar o catálogo completo.

### Hooks de pre-commit

Os hooks bloqueiam commits com segredos (gitleaks) ou que falham nas checagens rápidas da CI (ruff no `back/`, ESLint e Prettier no `front/`). Instale o pre-commit e o gitleaks no seu usuário:

```bash
uv tool install pre-commit
# gitleaks: baixe o tarball linux_x64 e o checksums.txt de
# https://github.com/gitleaks/gitleaks/releases, e então:
sha256sum --check --ignore-missing gitleaks_*_checksums.txt
tar -xzf gitleaks_*_linux_x64.tar.gz gitleaks && install -m 755 gitleaks ~/.local/bin/
pre-commit install            # na raiz do repositório
pre-commit run --all-files    # opcional: roda agora
```

## Checagens

```bash
cd back
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run pyright
# A stack de testes (limites de requisição maiores, banco inicial e volume de modelos próprios;
# o catálogo de dev não é tocado). Use-a para o pytest e para o `pnpm test:e2e`.
# `docker compose up -d` volta para o banco de dev.
docker compose -f compose.yaml -f compose.test.yaml up -d --wait --build
docker compose -f compose.yaml -f compose.test.yaml run --rm --build tests   # pytest dentro da rede do Compose (a porta do banco não é publicada)

cd ../front
pnpm lint
pnpm exec tsc --noEmit   # precisa dos tipos das rotas: rode `pnpm build` ou `pnpm dev` uma vez antes
pnpm exec prettier --check .
pnpm build
pnpm test                # Vitest
pnpm test:e2e            # faz o build e roda o Playwright contra `pnpm start`; precisa da stack de testes do back no ar (acima)
pnpm format              # Prettier, reescreve os arquivos

cd ..
scripts/check-openapi-drift.sh   # falha se o back/openapi.json ou os tipos TS estiverem desatualizados
```

O Playwright roda no Chromium, no Firefox, no WebKit e na tela de um iPhone 15 (`--project=<nome>` escolhe um). Instale os navegadores uma vez com `pnpm exec playwright install chromium firefox webkit`; o WebKit também precisa de `sudo pnpm exec playwright install-deps webkit`.

## Operações

O [docs/operations.md](docs/operations.md) cobre os jobs que montam e mantêm a busca, todos rodados pelo worker a partir de `back/`:

- o [catálogo inicial](docs/operations.md#seed-catalog) e a [importação do catálogo](docs/operations.md#catalog-import) pelas APIs da MetaBrainz;
- o [retag](docs/operations.md#retag), que completa as tags do MusicBrainz que faltam;
- o [benchmark](docs/operations.md#benchmark): o job de avaliação, seus arquivos e métricas;
- o [modelo próprio](docs/operations.md#own-model): treino, promoção e como voltar a uma versão anterior.

Depois de uma importação, rode nesta ordem, cada um depois que o anterior terminar: `retag` → `build-vectors` → `evaluate` → `train`.

## Deploy

O front roda na Vercel (diretório raiz `front`) e o back numa VPS. O `back/compose.prod.yaml` coloca o Caddy na frente da API (TLS para o `API_DOMAIN`, redirecionamento HTTP→HTTPS, HSTS), publica só as portas 80 e 443 e força `APP_ENV=production`, o que desliga a documentação da API. O `scripts/deploy-wizard.sh` guia a primeira configuração: VPS, DNS, `back/.env`, Vercel, segredos do GitHub e checagem dos headers.

Para atualizar o back, na VPS (o `back/.env` dela define o `COMPOSE_FILE`):

```bash
cd /root/timbre && git pull && cd back && docker compose up -d --wait --build
```

## Mudanças na API

Depois de mudar modelos de requisição ou resposta, gere de novo e faça commit dos dois arquivos:

```bash
(cd back && uv run python -m timbre_back.openapi > openapi.json)
(cd front && pnpm api:types)
```

Migrations novas vão em `back/migrations/` como `YYYYMMDDHHMMSS_descricao.sql`, com as seções `-- migrate:up` e `-- migrate:down`.

## Como o projeto é tocado

- Toda mudança chega na `main` por pull request. A regra da `main` exige as checagens `front`, `back`, `stack` e `secrets` verdes e bloqueia force-push e exclusão. Não há aprovação obrigatória, porque o repositório tem um só mantenedor.
- O trabalho é planejado em tickets no `.scratch/`, e as decisões ficam registradas como ADRs em [docs/adr/](docs/adr/). Os termos do domínio (Song, Match, Fit, Benchmark) estão definidos no [CONTEXT.md](CONTEXT.md).
- Agentes de código fazem a implementação: o Bob ([docs/agents/bob.md](docs/agents/bob.md)) constrói cada ticket, e o Carl ([docs/agents/carl.md](docs/agents/carl.md)) revisa contra os padrões do repositório e o ticket antes de o mantenedor fazer o commit. O template de PR pede o ticket, os testes e a revisão do Carl.

## Dados e créditos

- Metadados das músicas, rótulos de áudio e contagens de audição vêm do [MusicBrainz](https://musicbrainz.org), do [AcousticBrainz](https://acousticbrainz.org) e do [ListenBrainz](https://listenbrainz.org), mantidos pela MetaBrainz Foundation. O catálogo inicial no git usa só os campos CC0 deles.
- As tags do MusicBrainz são CC BY-NC-SA 3.0. Elas ficam no banco e nunca entram no git ([ADR 0002](docs/adr/0002-catalog-via-apis-not-dumps.md)).
- O Spotify serve só para ouvir as músicas. Ele nunca decide quais músicas combinam com a busca ([ADR 0001](docs/adr/0001-spotify-only-for-preview.md)).
- Fontes: Bricolage Grotesque e Inter, ambas sob a SIL Open Font License.

<p align="center">made in Brasil 🇧🇷</p>
