-- Etats courants de l'AFD par service source
CREATE TABLE IF NOT EXISTS afd_states (
  source_id           VARCHAR(100) PRIMARY KEY,
  current_state       VARCHAR(20)  NOT NULL DEFAULT 'NOMINAL',
  previous_state      VARCHAR(20),
  last_event_time     TIMESTAMP    DEFAULT NOW(),
  cascade_start_time  TIMESTAMP,
  ack_time            TIMESTAMP,
  updated_at          TIMESTAMP    DEFAULT NOW()
);

-- Historique de tous les logs traités
CREATE TABLE IF NOT EXISTS logs (
  id              SERIAL       PRIMARY KEY,
  source_id       VARCHAR(100),
  timestamp       TIMESTAMP,
  level           VARCHAR(10),
  category        VARCHAR(20),
  message         TEXT,
  raw             TEXT,
  afd_state       VARCHAR(20),
  afd_symbol      VARCHAR(50),
  afd_prev_state  VARCHAR(20),
  classified_at   TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_source_id    ON logs(source_id);
CREATE INDEX IF NOT EXISTS idx_logs_afd_state    ON logs(afd_state);
CREATE INDEX IF NOT EXISTS idx_logs_classified_at ON logs(classified_at);

-- Corrections humaines (feedback WhatsApp, WF2)
CREATE TABLE IF NOT EXISTS feedback_corrections (
  id               SERIAL    PRIMARY KEY,
  log_id           INTEGER   REFERENCES logs(id) ON DELETE SET NULL,
  original_state   VARCHAR(20),
  corrected_state  VARCHAR(20),
  corrected_by     VARCHAR(50) DEFAULT 'whatsapp_admin',
  corrected_at     TIMESTAMP   DEFAULT NOW()
);

-- Cache des réponses LLM
CREATE TABLE IF NOT EXISTS llm_cache (
  message_hash  VARCHAR(64) PRIMARY KEY,
  category      VARCHAR(20),
  response      JSONB,
  source        VARCHAR(10) DEFAULT 'ollama',
  hit_count     INTEGER     DEFAULT 1,
  created_at    TIMESTAMP   DEFAULT NOW()
);

-- Erreurs systeme n8n (Error Trigger workflow)
CREATE TABLE IF NOT EXISTS system_errors (
  id            SERIAL      PRIMARY KEY,
  workflow_id   VARCHAR(100),
  workflow_name VARCHAR(200),
  node_name     VARCHAR(200),
  error_message TEXT,
  error_stack   TEXT,
  occurred_at   TIMESTAMP   DEFAULT NOW()
);

-- Métriques journalieres agregees (WF3 daily report)
CREATE TABLE IF NOT EXISTS daily_metrics (
  id                   SERIAL    PRIMARY KEY,
  report_date          DATE      UNIQUE,
  nb_nominal           INTEGER   DEFAULT 0,
  nb_degraded          INTEGER   DEFAULT 0,
  nb_error             INTEGER   DEFAULT 0,
  nb_error_cascade     INTEGER   DEFAULT 0,
  nb_critical          INTEGER   DEFAULT 0,
  nb_recovery          INTEGER   DEFAULT 0,
  mttr_avg_seconds     INTEGER,
  false_positive_count INTEGER   DEFAULT 0,
  llm_cache_hits       INTEGER   DEFAULT 0,
  created_at           TIMESTAMP DEFAULT NOW()
);
