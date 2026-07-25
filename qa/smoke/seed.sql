-- Seed template for runtime smoke tests.
-- The oracle substitutes __MARKER__ with a unique value per run before execution.
-- This template inserts exactly ONE row into the users table.
INSERT INTO users (id, email, full_name, is_active, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'seeded-__MARKER__@smoke.internal',
    'Seeded User __MARKER__',
    true,
    NOW(),
    NOW()
);
