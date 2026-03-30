# MeetingAgent

Un agente de IA que analiza grabaciones de reuniones y extrae lo importante de forma automática: resumen ejecutivo, decisiones tomadas, y action items con responsable y fecha límite. Búsqueda semántica sobre el historial de todas tus reuniones incluida.

Todo corre en local. Sin APIs de pago, sin que tus grabaciones salgan de tu máquina.

---

## Stack

| Componente | Herramienta |
|---|---|
| Transcripción | [Whisper](https://github.com/openai/whisper) (local, CPU o CUDA) |
| LLM local | [Ollama](https://ollama.com/) — `mistral:7b` por defecto |
| LLM externo (opcional) | OpenAI / Anthropic |
| Pipeline de agente | [LangGraph](https://langchain-ai.github.io/langgraph/) |
| API | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| Base de datos | SQLite (estructurado) + [ChromaDB](https://www.trychroma.com/) (vectores) |
| Dashboard | Alpine.js — sin build step, sin bundler |
| Contenedores | Docker + Docker Compose |

---

## Qué hace

Subes un audio → el agente lo transcribe con Whisper → lo analiza con un LLM → guarda todo en SQLite + ChromaDB → puedes consultarlo desde un dashboard web o desde la API.

```
audio.mp3  →  [Whisper]  →  [LLM: resumir]  →  [LLM: action items]  →  [LLM: informe]  →  SQLite + ChromaDB
```

El pipeline usa LangGraph. Cada paso es un nodo independiente con estado compartido. Si algo falla, sabes exactamente dónde y por qué.

---

## Requisitos

- **Docker + Docker Compose**: la forma más fácil, levanta todo con un comando (API, ChromaDB y Ollama incluidos)

Si no quieres Docker, también puedes levantarlo a mano con Python 3.12+.

---

## Empezar (con Docker)

**1. Clona y configura**

```bash
git clone https://github.com/Izanvz/MeetingAgent
cd MeetingAgent
cp .env.example .env
# Edita .env si quieres cambiar algo (por defecto va con Ollama + mistral:7b)
```

**2. Levanta**

```bash
docker compose up --build
```

Eso es todo. Docker levanta la API, ChromaDB y Ollama automáticamente. La primera vez descarga el modelo `mistral:7b` (~4 GB), puedes ver el progreso con `docker logs -f meetingagent-ollama-1`. Las siguientes veces arranca en segundos.

La API y el dashboard estarán en `http://localhost:8000`.

> **GPU**: Si tienes NVIDIA y el [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) instalado, descomenta la sección `deploy` del servicio `ollama` en `docker-compose.yml` para usar la GPU.

---

## Empezar (sin Docker)

Necesitas Python 3.12 y levantar ChromaDB tú mismo.

```bash
# Crea el entorno
python3.12 -m venv venvMA
source venvMA/bin/activate          # Linux/Mac
# venvMA\Scripts\activate           # Windows

pip install -e .

# Terminal 1: ChromaDB
chroma run --host localhost --port 8001 --path ./chroma

# Terminal 2: Ollama (si no está ya corriendo)
ollama serve

# Terminal 3: la API
uvicorn src.api.main:app --reload --port 8000
```

---

## Configuración

Copia `.env.example` a `.env` y ajusta lo que necesites:

| Variable | Por defecto | Descripción |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | LLM a usar: `ollama`, `openai`, `anthropic` |
| `OLLAMA_MODEL` | `mistral:7b` | Modelo Ollama. `llama3:8b` también funciona bien |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL de Ollama |
| `OPENAI_API_KEY` | - | Solo si `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | - | Solo si `LLM_PROVIDER=anthropic` |
| `WHISPER_DEVICE` | `cpu` | `cuda` si tienes GPU NVIDIA |
| `WHISPER_COMPUTE_TYPE` | `int8` | `float16` para mejor calidad en GPU |
| `CHROMA_HOST` | `localhost` | Host de ChromaDB (automático con Docker) |
| `CHROMA_PORT` | `8001` | Puerto de ChromaDB (automático con Docker) |

> Con Docker Compose, `CHROMA_HOST` y `CHROMA_PORT` se sobreescriben automáticamente para que la API encuentre ChromaDB dentro de la red de contenedores. No hace falta tocarlos.

---

## Dashboard web

Abre `http://localhost:8000` en el navegador.

Tres pestañas:

- **Subir audio**: arrastra un mp3/wav/m4a, ponle título y fecha, y dale a analizar. Verás el pipeline en tiempo real mientras procesa.
- **Reuniones**: lista de todas las reuniones analizadas. Expandible. Puedes marcar action items como completados y exportar a ICS, Google Calendar, Jira o CSV.
- **Búsqueda semántica**: busca por contenido en todas las reuniones. "¿En qué reunión se habló del presupuesto de Q2?" y te devuelve el fragmento exacto con timestamp.

---

## API

La documentación interactiva está en `http://localhost:8000/docs` (Swagger UI).

Endpoints principales:

```
POST /meetings/audio          Sube un audio y lanza el análisis
GET  /jobs/{job_id}           Estado del análisis (polling)
GET  /meetings                Lista todas las reuniones
GET  /meetings/{id}           Detalle de una reunión
PATCH /tasks/{id}             Actualiza estado de un action item
POST /search                  Búsqueda semántica
```

---

## Estructura del proyecto

```
src/
├── agent/
│   ├── graph.py      ← Pipeline LangGraph (4 nodos)
│   ├── nodes.py      ← Lógica de cada nodo
│   ├── state.py      ← Estado compartido entre nodos
│   └── tools.py      ← Tools del LLM
├── api/
│   ├── main.py       ← FastAPI app
│   ├── routes/       ← /meetings, /tasks, /search, /jobs
│   └── static/       ← Dashboard web (Alpine.js, sin build step)
├── db/
│   ├── sqlite.py     ← Persistencia estructurada
│   └── vector_store.py ← ChromaDB wrapper
└── providers/
    └── llm.py        ← Factory de LLM por provider
```

---

## Notas sobre el LLM

El agente usa un **pipeline prescriptivo**, no ReAct. Esto significa que el LLM ejecuta instrucciones fijas en cada nodo, no decide qué hacer ni en qué orden.

Esto fue una decisión deliberada: `mistral:7b` con lógica ReAct (el LLM razona y decide qué tool llamar) producía JSON malformado, loops que no terminaban y tools llamadas en orden incorrecto. Con GPT-4 o Claude probablemente funciona, con un 7B local necesitas ser tú quien orqueste.

Si cambias a `openai` o `anthropic` en `LLM_PROVIDER`, el pipeline ReAct dinámico debería funcionar bien, pero el prescriptivo también es válido y más predecible.

---

## Tests

```bash
pytest
# Los tests usan ChromaDB efímero (sin servidor), corren sin dependencias externas
```

---

## Demo web

Hay una demo estática (sin API real) en: https://github.com/Izanvz/meeting-agent-demo

---

## Créditos

El diseño y desarrollo del dashboard web (`src/api/static/index.html`) fue realizado por [Claude](https://claude.ai) (Anthropic): interfaz, exportaciones a ICS/Google Calendar/Jira/CSV, e integración con la API.

---

## Autor

**Izan Villarejo Adames** — Backend Developer & AI Engineer

- Portfolio: [portfolio-izanv.vercel.app](https://portfolio-izanv.vercel.app/)
- LinkedIn: [linkedin.com/in/izan-villarejo-ai](https://www.linkedin.com/in/izan-villarejo-ai/)
- GitHub: [github.com/Izanvz](https://github.com/Izanvz)

---

> *"La IA no es el producto. El sistema que la integra correctamente, sí."*
