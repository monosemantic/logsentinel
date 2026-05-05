-- Etat courant de l AFD par service
-- Une seule ligne par service (source_id)
-- Mise a jour a chaque log traite
CREATE TABLE IF NOT EXISTS afd_states (
    source_id           VARCHAR(100) PRIMARY KEY,
    current_state       VARCHAR(20)  NOT NULL DEFAULT 'NOMINAL',
    previous_state      VARCHAR(20),
    last_symbol         VARCHAR(30),        -- dernier symbole applique
    last_event_time     TIMESTAMP    NOT NULL DEFAULT NOW(),
    cascade_start_time  TIMESTAMP,          -- debut de la fenetre ERROR_CASCADE
    cascade_count       INTEGER      NOT NULL DEFAULT 0,  -- nombre d erreurs dans la fenetre
    ack_time            TIMESTAMP,          -- heure du ACK admin (utile pour MTTR)
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Historique des logs traites
CREATE TABLE IF NOT EXISTS logs (
    id              SERIAL       PRIMARY KEY,
    source_id       VARCHAR(100) NOT NULL,
    log_timestamp   TIMESTAMP,        -- timestamp extrait du log
    level           VARCHAR(10),      -- info | warning | error | critical
    category        VARCHAR(20),      -- SECURITY | PERFORMANCE | AVAILABILITY | DATA | NETWORK | SYSTEM | MALFORMED
    message         TEXT,
    raw_log         TEXT,             -- log original avant normalisation
    format_type     VARCHAR(20),      -- json | plaintext | syslog | apache | unknown
    afd_state       VARCHAR(20),      -- etat AFD assigne
    afd_symbol      VARCHAR(30),      -- symbole qui a declenche la transition
    previous_state  VARCHAR(20),
    llm_cache_hit   BOOLEAN      DEFAULT FALSE,  -- true si reponse depuis le cache
    classified_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_source_id     ON logs(source_id);
CREATE INDEX IF NOT EXISTS idx_logs_afd_state     ON logs(afd_state);
CREATE INDEX IF NOT EXISTS idx_logs_classified_at ON logs(classified_at DESC);

-- Corrections faites par un humain (via WhatsApp)
-- Permet de suivre les faux positifs et ameliorer le systeme
CREATE TABLE IF NOT EXISTS feedback_corrections (
    id               SERIAL       PRIMARY KEY,
    log_id           INTEGER      REFERENCES logs(id) ON DELETE SET NULL,
    source_id        VARCHAR(100),
    original_state   VARCHAR(20),
    corrected_state  VARCHAR(20),
    command_used     VARCHAR(30),   -- ACK | FALSE_POSITIVE | CORRIGER_WARNING | etc
    mttr_seconds     INTEGER,       -- calcule si RESOLVED (NOW() - ack_time)
    corrected_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Cache des reponses LLM
-- Evite de reinterroger le modele pour des messages identiques
CREATE TABLE IF NOT EXISTS llm_cache (
    message_hash    VARCHAR(64)  PRIMARY KEY,  -- hash SHA-256 du message normalise
    category        VARCHAR(20),
    afd_state       VARCHAR(20),
    response_text   TEXT         NOT NULL,
    llm_source      VARCHAR(20),  -- groq | anthropic | static
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_hit_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
    hit_count       INTEGER      NOT NULL DEFAULT 1
);

-- Erreurs internes du systeme (capturees par n8n)
CREATE TABLE IF NOT EXISTS system_errors (
    id              SERIAL       PRIMARY KEY,
    workflow_name   VARCHAR(100),
    node_name       VARCHAR(100),
    error_message   TEXT,
    error_stack     TEXT,
    occurred_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);
