# CityCare Intelligence Service

FastAPI service for advisory complaint similarity and spatial hotspot analysis. It runs separately from the React and Express applications and has no Supabase credentials or direct database connection.

## macOS setup

From the repository root:

```sh
cd ml-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Set `ML_SERVICE_TOKEN` in this `.env` and in `apps/api/.env` to the same private random value (for example generate with `openssl rand -hex 32`). Never place the token in `apps/web/.env`, a `VITE_` variable, or source control.

Run the service:

```sh
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Health endpoint: `GET http://127.0.0.1:8001/health`. OpenAPI/Swagger is available at `/docs`; protected analysis endpoints require `Authorization: Bearer <ML_SERVICE_TOKEN>`.

## API

- `GET /health`: service version, semantic-model availability and whether internal auth is configured.
- `GET /api/v1/model/info`: scoring methods, weights, thresholds and configuration.
- `POST /api/v1/duplicates/analyze`: one complaint plus a bounded candidate list, ranked with signal explanations.
- `POST /api/v1/duplicates/batch`: up to 10 queries against a bounded candidate list.
- `POST /api/v1/hotspots/analyze`: DBSCAN over validated coordinates with distance, category and date filters.
- `GET /api/v1/evaluation/summary`: saved demonstration benchmark metrics, when generated.

The analysis endpoints are internal. Express validates the Supabase user and role, retrieves rows with the user's JWT-scoped RLS client, minimizes the data, and forwards requests with the shared secret. Do not publish this FastAPI service directly to the internet. If it is remotely hosted, restrict network ingress to Express and use TLS.

## Model architecture

Text is normalized with Unicode NFKC, case/punctuation/whitespace normalization, repeated-character reduction, conservative spelling aliases, and a small explicit set of Romanized informal terms. Negation and meaningful status words are preserved. The word model uses TF-IDF unigrams/bigrams with English stopwords; the character model uses `char_wb` 3–5 grams; RapidFuzz WRatio provides a fuzzy baseline. Category agreement, Haversine proximity, and exponential temporal decay contribute when those fields are available. Sentence Transformers (`all-MiniLM-L6-v2`) is optional, lazy-loaded, cached, and disabled by default; API responses state when it is unavailable.

Default hybrid score is the weighted mean of available [0,1] signals, scaled to 0–100, with unavailable signals removed and the remaining weights renormalized:

| Signal | Weight |
| --- | ---: |
| Word TF-IDF | 0.24 |
| Character TF-IDF | 0.18 |
| RapidFuzz WRatio | 0.14 |
| Semantic cosine (optional) | 0.18 |
| Category match | 0.10 |
| Geographic proximity | 0.11 |
| Temporal relevance | 0.05 |

Weak lexical evidence gates down scores so proximity alone cannot imply a duplicate; differing categories also reduce a weak-text match. The method and weights are implementation choices, not trained parameters. Thresholds in `app/evaluation/calibration.json` were selected by maximizing F1 on the included labeled demonstration set; the high band additionally seeks precision at least 0.85 when the small demonstration sample permits. Override threshold and scale settings with the documented environment variables. All outputs are suggestions and require human review.

## Hotspots

DBSCAN uses radians with Haversine distance, making `epsilon_meters` independent of preselected cluster count. Centers use a spherical mean; radius is the maximum member distance to the center. Density is an approximate count per circular area based on the larger of observed radius or half epsilon. Density cutoffs are configurable. Missing coordinates and filtered records are counted and reported; synthetic coordinates are used only in clearly labeled evaluation cases, not operational data.

## Evaluation and tests

The included 24-pair dataset is a manually labeled fictional demonstration benchmark, not actual citizen records and not an independent holdout. Reproduce results and recalibrate thresholds with:

```sh
python scripts/run_evaluation.py
python -m pytest -q tests
```

Results are saved to `app/evaluation/results.json`; calibration is saved to `app/evaluation/calibration.json`. Metrics include precision, recall, F1, accuracy, false-positive/negative rates, confusion counts, and precision-recall curve points for word TF-IDF, character TF-IDF, RapidFuzz, and hybrid scoring. Resubstitution metrics illustrate code behavior only; use a representative, permissioned, independently held-out set before operational model claims. Precision matters because distinct civic problems must not be hidden by a false duplicate; recall matters because missed duplicates can cause repeated review or field work.

## Data and environment

Pydantic rejects extra fields, malformed coordinate pairs, out-of-range coordinates, oversized descriptions, invalid ranges, and oversized candidate lists. Requests above 2 MB are rejected. Routine logs include request id, path, status, duration, and error type, not payload text or credentials.

Copy `.env.example` to `.env` and configure:

- `ML_HOST`, `ML_PORT`: bind address and port; default loopback/8001.
- `ML_SERVICE_TOKEN`: required to authorize all analysis/model-info endpoints.
- `ML_ALLOWED_ORIGINS`: restricted CORS origin list (Express by default); browser requests should still use Express.
- `CITYCARE_ENABLE_SEMANTIC`, `CITYCARE_SEMANTIC_MODEL`, `CITYCARE_SEMANTIC_CACHE_SIZE`: optional semantic model settings.
- `CITYCARE_DUPLICATE_MAX_CANDIDATES`, `CITYCARE_DUPLICATE_HIGH_THRESHOLD`, `CITYCARE_DUPLICATE_POSSIBLE_THRESHOLD`.
- `CITYCARE_TEMPORAL_HALF_LIFE_DAYS`, `CITYCARE_GEO_PROXIMITY_SCALE_METERS`.
- `CITYCARE_HOTSPOT_EPSILON_METERS`, `CITYCARE_HOTSPOT_MIN_SAMPLES`.

Do not put the Supabase URL, API key, user record, or database password in the Python service. It accepts only the bounded analysis payload from authenticated Express.

## Limitations

There is no real labeled CityCare dataset in this repository. Romanized terms are only a small alias list, not multilingual NLP. Semantic embeddings are disabled by default. Current duplicate candidate selection is bounded, not exhaustive; the API signals cap reach. Hotspots exclude un-geocoded cases. Session analysis history is not persisted. Rules and scores need validation against representative labeled records and operational feedback before they should influence decisions.
