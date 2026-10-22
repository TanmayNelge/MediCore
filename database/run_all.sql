-- =====================================================================
-- run_all.sql
-- MediCore HCMS - runs the full init chain in order (alternative to
-- install.py for people who prefer SQL*Plus / SQLcl / SQL Developer F5).
-- Usage, connected as the HCMS_ADMIN schema owner:
--   SQL> @run_all.sql
--
-- Then run 12_security_roles.sql SEPARATELY, connected as SYSTEM (it
-- creates other users / roles / a profile, not HCMS_ADMIN objects).
-- =====================================================================
SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
SET FEEDBACK OFF
@03_sequences.sql
@01_schema.sql
@04_sample_data.sql
@05_views.sql
@06_indexes.sql
@07_functions.sql
@08_procedures.sql
@09_packages.sql
@10_triggers.sql
@14_bill_status_trigger.sql
@11_queue.sql
-- @04b_bulk_data.sql       -- optional: 60 extra future appointments
-- @12_security_roles.sql   -- run separately as SYSTEM, see note above
-- 13_audit.sql, 15_demo_queries.sql, 16_transactions_concurrency.sql are
-- demo / report scripts - open them and run statement by statement.
SET FEEDBACK ON
SELECT object_type, COUNT(*) AS objects,
       SUM(CASE WHEN status = 'INVALID' THEN 1 ELSE 0 END) AS invalid
FROM user_objects GROUP BY object_type ORDER BY object_type;
PROMPT MediCore HCMS schema, data and PL/SQL objects created.
PROMPT Next: run 12_security_roles.sql as SYSTEM, then see ../README.md.
