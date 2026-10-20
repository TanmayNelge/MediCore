-- =====================================================================
-- run_all.sql
-- MediCore HCMS - runs the full init chain in order.
-- Usage (SQL*Plus or SQLcl), connected as the HCMS_ADMIN schema owner:
--   SQL> @run_all.sql
--
-- Run 12_security_roles.sql SEPARATELY, connected as a DBA-privileged
-- user (SYSTEM or a user with CREATE USER/ROLE), since it creates other
-- database users and roles rather than HCMS_ADMIN objects.
-- =====================================================================
SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
@03_sequences.sql
@01_schema.sql
@04_sample_data.sql
@04b_bulk_data.sql
@05_views.sql
@06_indexes.sql
@07_functions.sql
@08_procedures.sql
@09_packages.sql
@10_triggers.sql
@14_bill_status_trigger.sql
@11_queue.sql
-- @12_security_roles.sql   -- run separately as a DBA user, see note above
@13_audit.sql
PROMPT MediCore HCMS core schema, data, and PL/SQL objects created.
PROMPT Next: run 12_security_roles.sql as a DBA user, then see ../README.md.
