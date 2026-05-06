-- Exchange rates captured by the light pipeline
CREATE TABLE IF NOT EXISTS exchange_rates (
    id              SERIAL PRIMARY KEY,
    currency_from   VARCHAR(3) NOT NULL,
    currency_to     VARCHAR(3) NOT NULL,
    rate            NUMERIC(12, 4) NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL,
    window_start    TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_exchange_rate_window
        UNIQUE (currency_from, currency_to, window_start)
);

CREATE INDEX IF NOT EXISTS idx_exchange_rates_window
    ON exchange_rates(window_start DESC);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_currencies
    ON exchange_rates(currency_from, currency_to);

-- Course catalog (seeded)
CREATE TABLE IF NOT EXISTS courses (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL UNIQUE,
    base_price_usd  NUMERIC(10, 2) NOT NULL,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Localized prices calculated by the heavy pipeline
CREATE TABLE IF NOT EXISTS course_prices (
    id                  SERIAL PRIMARY KEY,
    course_id           INTEGER NOT NULL REFERENCES courses(id),
    country             VARCHAR(2) NOT NULL,
    currency            VARCHAR(3) NOT NULL,
    price_local         NUMERIC(12, 2) NOT NULL,
    exchange_rate_used  NUMERIC(12, 4) NOT NULL,
    calculated_date     DATE NOT NULL,
    variation_pct       NUMERIC(6, 2),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_course_price_date
        UNIQUE (course_id, country, calculated_date)
);

CREATE INDEX IF NOT EXISTS idx_course_prices_date
    ON course_prices(calculated_date DESC);

-- Significant variation alerts (>5%)
CREATE TABLE IF NOT EXISTS price_alerts (
    id              SERIAL PRIMARY KEY,
    course_id       INTEGER NOT NULL REFERENCES courses(id),
    country         VARCHAR(2) NOT NULL,
    previous_price  NUMERIC(12, 2),
    current_price   NUMERIC(12, 2) NOT NULL,
    variation_pct   NUMERIC(6, 2) NOT NULL,
    alert_date      DATE NOT NULL,
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_price_alert_date
        UNIQUE (course_id, country, alert_date)
);
