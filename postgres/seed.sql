INSERT INTO courses (title, slug, base_price_usd, active) VALUES
    ('Introducción a la psicología clínica',  'intro-psicologia-clinica',   49.00, TRUE),
    ('Terapia cognitivo-conductual',           'terapia-cognitivo-conductual', 89.00, TRUE),
    ('Psicología positiva y bienestar',        'psicologia-positiva-bienestar', 35.00, TRUE),
    ('Manejo del estrés y ansiedad',           'manejo-estres-ansiedad',      29.00, TRUE),
    ('Neuropsicología aplicada',               'neuropsicologia-aplicada',   120.00, TRUE)
ON CONFLICT (slug) DO NOTHING;
