# Stockfish — Architektur & Betrieb

> **Stand:** 2026-09-12  
> **Fork von:** NousResearch/hermes-agent  
> **Fork owner:** Stockfish18 (Rason 'Bro' Leis)  
> **Plattform:** DrexOSS (drexoss.com)  
> **LLM Backend:** DeepSeek V4 Flash (OpenRouter) + Llama 3.1 8b (lokal/Ollama)

---

## 1. WAS IST STOCKFISH?

Stockfish ist ein **Hard Fork** von Hermes Agent mit Eigenentwicklungen.  
Kein reiner Hermes-Agent mehr — sondern Rasons persönlicher Jarvis, der unter `DrexOSS` als Plattform läuft.

### Fork-Struktur

| Komponente | Ort |
|---|---|
| Fork-Repo | `Stockfish18/hermes-agent` (GitHub) |
| Lokal | `C:\Users\rason\hermes-agent\` |
| Live-Installation | `C:\Users\rason\AppData\Local\hermes\hermes-agent\` |
| Origin | Stockfish18/hermes-agent |
| Upstream | NousResearch/hermes-agent |
| Eigenentwicklungen | `stockfish-skills/` (3 Skills, s.u.) |

---

## 2. SYSTEMKOMPONENTEN

```
┌─────────────────────────────────────────────────────────────────┐
│                        DREXOSS PLATTFORM                         │
│                                                                   │
|  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│  │  Hermes CLI   │    │  Stockfish Bridge│   │  Cloudflare         │  │
│  │  (Terminal)   │    │  v5.1-CLI :8002  │   │  Pages              │  │
│  │  aktuell aktiv│    │  → hermes chat -q │   │  drexoss.com        │  │
│  └──────┬───────┘    └────────┬─────────┘   │  Cloudflare Tunnel   │  │
│         │                     │              │  (hermes-chat)       │  │
│         │                     │              │  chat.drexoss.com    │  │
│         │                     │              │  /chat/* → :8002     │  │
│         │                     │              │  /*      → :9119     │  │
│         │                     │              │  Page Rule: Security │  │
│         │                     │              │  Off für Chat-Sub    │  │
│         ▼                     ▼              └──────────┬───────────┘  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │             SUPABASE (Single Source of Truth)             │     │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐    │     │
│  │  │  Schema: public      │  │  Schema: memory          │    │     │
│  │  │  ├─ projects         │  │  ├─ sessions             │    │     │
│  │  │  ├─ tasks            │  │  ├─ messages             │    │     │
│  │  │  ├─ routines         │  │  ├─ consolidations       │    │     │
│  │  │  ├─ user_profiles    │  │  ├─ representations      │    │     │
│  │  │  ├─ app_config       │  │  ├─ embeddings(pgvector) │    │     │
│  │  │  └─ ideas            │  │  └─ embeddings(pgvector) │    │     │
│  │  └─────────────────────┘  └─────────────────────────┘    │     │
│  │                                                           │     │
│  │  Edge Functions:                                         │     │
│  │  ├─ dreaming  (v16 — tägl. 3:00 via pg_cron)             │     │
│  │  ├─ leela     (v4  — Projekt-Assistentin)                 │     │
│  │  └─ scout     (v1  — Mo 6:00 via pg_cron)                 │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Hermes Core

| Aspekt | Wert |
|---|---|
|| Main Model | deepseek/deepseek-v4-flash (OpenRouter) |
|| Sub-Agent Model | llama3.1:8b (lokal, Ollama, kostenlos) |
|| Reasoning | medium (DeepSeek), false (Ollama) |
|| Plattform | CLI (Terminal), Dashboard (9119) |
|| Hermes Core | v2026.9.11 (upstream, gemerged 12.09.) |
|| Chat Bridge | Stockfish Bridge **v9** (NDJSON-Streaming) → Port 8002 |
|| Chat Endpoint | `chat.drexoss.com` → Tunnel → :8002 (Bridge) → hermes chat -q |
|| Dashboard | `chat.drexoss.com` → Tunnel → :9119 |

### 2.2 Memory System (Ab 05.09.2026)

| Aspekt | Status |
|---|---|
| Provider | **supabase** (umgestellt von honcho) |
| Honcho | Zugriffsschlüssel entfernt, Daten noch auf Honcho-Servern |
| Speicherort | Supabase, Schema `memory` |
| Semantische Suche | pgvector (text-embedding-3-small, 1536d) via `match_consolidations` RPC |
| Backup | Lokal in `~/Dokumente/honcho_backup_20260905.json` |
| Benchmark | `metrics`-Tabelle, 5 IQ-Metriken, wöchentliche Messung (Mo 5:00) |

**Migrierte Daten (Stand 05.09.):**

| Datentyp | Menge | Status |
|---|---|---|
| Sessions (mit Messages) | 17 (9 migriert + 8 gesynct) | Konsolidiert (via Dreaming v2 + stockfish-sync) |
| Messages | 2.500+ | Vollständig migriert + sync |
| Peer Cards | 2 (Rason-Leis, Telegram) | 28 Card-Items importiert |
| Consolidations (Dreaming) | 71+ | Cloud Edge Function (v20), täglich 3:00 UTC |
| Representations | 28 | Automatisch extrahiert |
| Embeddings | 72 | pgvector, 1536d |

**Semantische Suche (pgvector):**
- `match_consolidations` RPC-Funktion erstellt (vektorielle Ähnlichkeitssuche)
- Threshold 0.4, bis zu 3 relevante Consolidations pro Query
- Embedder speichert Insight-Text in `metadata.content_text` für direkte Darstellung

### 2.3 Memory-Provider (Eigenentwicklung)

**Ort:** `plugins/memory/supabase/__init__.py` (469 Zeilen, neu geschrieben 12.09.)

**Status:** **AKTIV** — supabase provider active, `hermes doctor` zeigt grün. Sync_turn schreibt user+assistant messages direkt in Supabase. Env Vars in `~/.hermes/.env` (SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY).

Tools via MemoryProvider-Interface (nur in hybrid/tools-mode):
- `supabase_profile` — Peer-Card lesen
- `supabase_search` — Keyword-Suche auf Consolidations

### 2.4 Supabase Edge Functions

#### dreaming (v16)

| Aspekt | Wert |
|---|---|
| Status | ACTIVE |
| Trigger | pg_cron, täglich 3:00 UTC |
| API-Key | sf-dream-60_QDmG4cU0zqc87tXCNDI-CTQ5kgMDEIyVQ6TAPJBY (generiert) |
| verify_jwt | false |
| Import Map | true |
| Version | 16 |

**Ablauf (1 Session pro Aufruf):**
1. Nächste unkonsolidierte Session holen (kleinste zuerst)
2. Messages ladeb (max 200 × 3000 Zeichen)
3. 4-Pass Dialectic via DeepSeek (kalt → warm → Synthese → Final)
4. 5. Pass: Cross-Session-Merge mit letzten 10 Consolidations
5. Consolidations speichern
6. Representations updaten (Key/Value in `memory.representations`)
7. Summary schreiben
8. Embedding via OpenRouter (text-embedding-3-small) — **separates Script**

**Prompts für die Dialectic:**
- PASS0_COLD: Fakten extrahieren, keine Interpretation
- PASS0_WARM: Unausgesprochene Muster erkennen
- PASS1_SYNTHESIS: Kohärentes Profil + Widersprüche auflösen
- PASS2_FINAL: 3-5 Bullet Points | Confidence | Type
- CROSS_SESSION: Merge mit historischen Conslidations

**Bekannte Einschränkung:** Embeddings müssen separat laufen — die Edge Function hat CPU-Limits im Free-Tier (150s Zeitlimit + Worker-Resource-Limit).

**Update 05.09.:** Embedder-Cron auf `no_agent`-Modus umgestellt. Embedder speichert jetzt `content_text` in `metadata` für die semantische Suche.

#### leela (v4)

Agent Leela — Projekt-Assistentin für Kunden/Tean. Ohne Admin-Wisen, keine persönlichen Erinrungen. Zugrff nur auf `public`-Schemata.

---

## 3. SKILLS (Eigenentwicklungen)

Verzeichnis unter `stockfish-skills/`:

| Skill | Beschreibung | Status |
|---|---|---|
| stockfish-lsp | LSP-Analzeator (pyright + jedi) für Code-Inspektion | Aktiv |
| stockfish-coordinator | Parallele Sub-Agents mit koordiniertem Merge | Aktiv (aber limtiert auf 2 parallel) |
| stockfish-teams| 5 Rollen (explore, plan, coder, reiewer, verifier) | Aktiv |

**Weitere Skills (aus AppLoca/hermes/skills/):**
- `sopabase-auth-mnagement`— Supabase Auth via API
- Github-Skills (PRs, Issues, Code- Review)
- Ocradn- Dokumente — PDF/DOCX
- yotbe- Content — Transkripte
- Tleegram- Bridge — Bot-Chat
- Archtecture-Diagram — SVG-Diagramme
- viele weietere...

---

## 4. CONFIG

| Key | Wert | Quelle |
|---|---|---|
| `memory.provider` | **supabase** | config.yaml |
| `memory.memory_enabled` | true | config.yaml |
| `memory.user_profile_enabled` | true | config.yaml |
| `provider` | openrouter | config.yaml |
| `model` | deepseek/deepseek-v4-flash | config.yaml |
| `SUPABASE_URL` | rmveqbegqfthwdopzykh.supabase.co | .env |
| `SUPABASE_SERVICE_KEY` | gesetzt | .env |
| `SUPABASE_ANON_KEY` | gesetzt | .env |
| `OPENROUTER_API_KEY`| gesetzt | .env |

---

## 5. CRON-JOBS (Lokal, benötigen PC am Gateway)

|| Job | Zeitplan | Status| Skript| Typ |
|---|---|---|---|---|
|| Stockfish Sync| alle 30min (no_agent) | AKTIV | `stockfish-sync.py` | no_agent (direkt)|
|| Stockfish Embedder| tägl. 3:15 | AKTIV | `stockfish-embedder.py` | no_agent (direkt)|
|| Stockfish Scout | Mo 6:00 | AKTIV | Supabase Edge Function + pg_cron | Cloud |
|| Stockfish Compressor| tägl. 2:15 | AKTIV | `stockfish-compressor.py` (auch via Sync getriggert) | no_agent|
|| OpenRouter Kosten| alle 360min | AKTIV | `openrouter_cost_watch.py` | no_agent|
|| Rechnungen| Mo/Do 9:00 | AKTIV | `invoice_cron.py` | no_agent|
|| Ollama Autostart| alle 5min | AKTIV | (intern)| Prompt-Job|
|| Discord DM Poller| alle 1min| AKTIV| `discord_dm_poller.sh`| no_agent|
|| Termin Dr. Reuss| 08.09. 07:00 | AKTIV | —| One-Shot|

**Pipeline (09.09.):**
1. `stockfish-sync.py` lokal (alle 30 Min) — pushed state.db Sessions in memory.schema
2. Bei >20 Messages: trigger `stockfish-compressor.py` lokal (Ollama, 23-60x Kompression)
3. `dreaming` Edge Function (3:00 UTC Cloud) — konsolidiert neue Sessions
4. `stockfish-embedder.py` (3:15 UTC lokal) — Embeddings für neue Consolidations

**Wichtig:** Lokale Crons laufen nur wenn `hermes gateway` läuft (PC an).  
Dagegen: pg_cron auf Supabase läuft **immer** (Cloud).

---

##6. PROJEKTE IN SUPABASE

| Code |Name |Status | Fortschritt|Tasks|
|---|---|---|---|---|---|
| STKF| Stockfish Capability Absoption| active| 1%|11 Tasks (T-066 bis T-076) — 6 done, 2 review, 1 idle, 2 offen|
| DREX |Drexoss Web Companion|active| 10% |~25 Tasks (DREX — enthält Admin-Panel)|
| LERN| Programmieren lernen |active| 15%|3 Tasks offen|
| SRVR|Mi-PC Server| planning|5%|—|

**Neue Tasks (05.09.):**

| Task | Status | Beschreibung |
|---|---|---|
| T-074 | Done | LightThinker auf RTX 3090 getestet — Repo geklont, Model läuft |
| T-075 | Idle | Dreaming Session-Kompression via Embeddings (wartet auf LightThinker++) |
| T-076 | Done | Embedding-optimierte Context-Injektion im Supabase-Provider (Semantic Search) |

**Offene (ungeplante) Prokekte:**
- Melissa´s Kindemode-Shop + Mi-ERP
- Hailing + Gü als Benutzer (Role- bsed Acces)

---

##7. DATENFLUSS (Eine Sitzung)

```
User-Nachricht → Hermes CLI
  → MemoryManager ruft prefetch() auf (Supabase-Provider)
    → Lädt Representations (user_id=rason)
    → Lädt letzte 3 Session-Summaries
    → Lädt Top-5 Consolidations
    → Semantische Suche (pgvector): Embedding der Query → match_consolidations
  → Inject in System-Prompt
  → LLM generiert Antwort (DeepSeek via OpenRouter)
  → sync_turn() schreibt User+Assistant-Message in lokale state.db
```

**Nächtliche Cloud-Pipeline (PC-unabhängig):**
```
1. stockfish-sync.py (alle 30 Min, lokal) → pushed state.db Sessions in memory.schema
2. stockfish-compressor.py (lokal) → komprimiert Sessions >20 Messages (Ollama, 23-60x)
3. dreaming Edge Function (3:00 UTC, Cloud) → konsolidiert Sessions mit summary
4. stockfish-embedder.py (3:15, lokal) → Embeddings für neue Consolidations
```

---

##8. STATUS-CHECK (via Script)

```bash
python C:/Users/rason/AppData/Local/hermes/scripts/stockfish-status.py
```

Prüft 17 Komponenten live. Output:
```
    OK | memory.provider — =supabase
    OK | table sessions — 17 total, 0 unprocessed
    OK | embeddings — 72 stored
    OK | dreaming function — v20, ACTIVE
    ...
  17 passed, 0 warnings, 0 failed
```

---

## 9. SICHERHEIT

| Maßnahme | Status |
|---|---|
| Service-Key | Nicht im Browser-Code (nur Backend/Edge Function) |
| DREAMING_API_KEY | Generierter Token (nicht vorhersagbar) |
| Honcho-API-Key | Gelöscht (aus honcho.json) |
| RLS Policies | memory.* Tabellen auf user_id + admin-Rolle |
| Leela-Daten | Kein Zugriff auf memory.*, nur public.* |
| Config | Secret-Werte via Env/Secrets-API, nicht hartcodiert |
| Embedder | Liest OPENROUTER_API_KEY aus der Gateway-Umgebung (kein .env-File-Parsing mehr) |

**Noch offen:**
- [ ] Chat.drexoss.com Auth verstärken (Basic Auth reicht nicht für Produktion)
- [ ] T-080 Screenshots STRG+V im Dashboard-Chat
- [ ] T-072c Agent Leela Konzept (Dashboard vs separates Hermes-Profil)

---

## 10. ROADMAP (Nächste Schritte)

| Priorität | Task | Beschreibung |
|---|---|---|
| 1 | LightThinker++ | Training auf eigenem Dataset — Stockfish-spezifisches Reasoning |
| 2 | DREX-023/24 | Admin-Panel Configs in DB statt LocalStorage |
| 3 | T-073 | Bridge-Sync zwischen Instanzen |

**Bereits erledigt (09.09.):**
- T-080: stockfish-sync.py — state.db -> Supabase memory. Cron alle 30 Min, half-sync detection, auto-compress. QA: 8 Sessions, Dreaming getestet ✓
- T-072: Scout Edge Function + pg_cron + Dashboard-Tab (PC-unabhängig) ✓
- T-074: LightThinker auf RTX 3090 getestet ✓
- T-075: Dreaming-Kompression (stockfish-compressor.py, jetzt 23-60x, Ollama lokal) ✓
- T-076: Embedding-optimierte Context-Injektion (Semantic Search) ✓
- Deploy: Dashboard mit System-Tab + Benchmark-Tab + Scout-Tab live auf drexoss.com ✓
- Embedder-Cron auf no_agent umgestellt ✓
- Benchmark: metrics-Tabelle + stockfish-benchmark.py + wöchentlicher Cron ✓

---

## 11. DATENVERZEICHNIS (Wichtige Dateien)

**Eigene Skripte (`scripts/`):**

| Datei | Zweck |
|---|---|
| `stockfish-sync.py` | Sync state.db → Supabase memory (alle 30 Min, no_agent) |
| `stockfish-bridge.py` | Stockfish Bridge v5.1 → CLI-basiertes Chat-Streaming (Port 8002) |
| `stockfish-dreaming.py` | (pausiert) Lokales Dreaming — Edge Function macht das jetzt |
| `stockfish-compressor.py` | Session-Kompression vor Dreaming (Ollama lokal, 23-60x, Cron 2:15 + via Sync getriggert) |
| `stockfish-embedder.py` | Batch-Embeddings für Consolidations (Cron 3:15, no_agent) |
| `stockfish-status.py` | Live-Health-Check (17 Checks) |
| `stockfish-benchmark.py` | IQ-Messung: 5 Metriken, wöchentlich (Mo 5:00) |

**Research:**

| Datei | Inhalt |
|---|---|
| `stockfish-skills/research/latent-reasoning.md` | Vollständige Analyse: Coconut, LatentPress, CODI, LightThinker, LCLM, J-Space |

**Externe Repos (geklont):**

| Repo | Ort | Zweck |
|---|---|---|
| `zjunlp/LightThinker` | `C:\Users\rason\LightThinker\` | Reasoning-Kompression (T-074) |
| `zjunlp/LightThinker-Qwen` | `...\models\LightThinker-Qwen` | Lokales Model (RTX 3090) |

**Konfigurationen:**

| Datei | Inhalt |
|----|---|
| `~/AppData/Local/hermes/config.yaml` | Hauptkonfig |
| `~/AppData/Local/hermes/honcho.json` | Honcho-Config (Key gelöscht) |
| `~/AppData/Local/hermes/.env` | Umgebungsvariablen |
| `~/.cloudflared/config.yml` | Cloudflare Tunnel-Routing (chat.drexoss.com Path-Routing) |
| `~/AppData/Local/hermes/gateway-service/stockfish_bridge.py` | Stockfish Bridge v5.1-CLI |

**Backup:**

| Datei | Größe | Inhalt |
|---|---|---|
| `~/Dokumente/honcho_backup_20260905.json` | 1,1 MB | Vollständiger Honcho-Export |

---

*Dieses Dokument wird bei größeren Änderungen aktualisiert.  
Letzte Aktualisierung: 2026-09-05*