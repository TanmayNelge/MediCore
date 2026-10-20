-- =====================================================================
-- 14_bill_status_trigger.sql
-- MediCore HCMS - trg_bill_status_update
--
-- WHY THIS FILE EXISTS:
-- backend/app/routers/billing.py's record_payment() endpoint has a
-- docstring that says: "bill.status flip to PAID/PARTIALLY_PAID happens
-- in trg_bill_status_update (Phase 8), not duplicated here." That
-- trigger was never actually written in 10_triggers.sql -- only
-- trg_bill_audit (which logs high-value bills to AUDIT_LOG) exists.
-- Without it, BILL.STATUS stays 'UNPAID' forever no matter how many
-- payments are recorded, which breaks vw_patient_billing_summary,
-- the billing UI, and the Phase 17.1 "Billing" functional test.
--
-- This is implemented as a COMPOUND TRIGGER (not a plain AFTER EACH ROW
-- trigger) because a row-level trigger on PAYMENT cannot itself SELECT
-- SUM(amount_paid) FROM payment WHERE bill_id = ... -- that would be a
-- read of the same table currently being modified by the firing
-- statement, which raises ORA-04091 (mutating table). The compound
-- trigger collects affected bill_ids during the AFTER EACH ROW section,
-- then does the aggregate SELECT + UPDATE once per bill in the AFTER
-- STATEMENT section, after the triggering DML has fully completed --
-- which is exactly when querying PAYMENT is safe again.
--
-- Run this as HCMS_ADMIN, after 10_triggers.sql (or any time after
-- 07_functions.sql, since it depends on calculate_bill_total()).
-- =====================================================================

CREATE OR REPLACE TRIGGER trg_bill_status_update
FOR INSERT OR UPDATE OR DELETE ON payment
COMPOUND TRIGGER

    TYPE t_bill_ids IS TABLE OF payment.bill_id%TYPE INDEX BY PLS_INTEGER;
    g_bill_ids  t_bill_ids;
    g_count     PLS_INTEGER := 0;

    AFTER EACH ROW IS
    BEGIN
        g_count := g_count + 1;
        g_bill_ids(g_count) := NVL(:NEW.bill_id, :OLD.bill_id);
    END AFTER EACH ROW;

    AFTER STATEMENT IS
        v_total NUMBER;
        v_paid  NUMBER;
    BEGIN
        FOR i IN 1 .. g_count LOOP
            v_total := calculate_bill_total(g_bill_ids(i));

            SELECT NVL(SUM(amount_paid), 0)
              INTO v_paid
              FROM payment
             WHERE bill_id = g_bill_ids(i);

            UPDATE bill
               SET status = CASE
                               WHEN v_total > 0 AND v_paid >= v_total THEN 'PAID'
                               WHEN v_paid > 0 AND v_paid < v_total  THEN 'PARTIALLY_PAID'
                               ELSE status  -- no payments yet, or bill already CANCELLED: leave as-is
                             END
             WHERE bill_id = g_bill_ids(i)
               AND status != 'CANCELLED';
        END LOOP;
        g_count := 0;
    END AFTER STATEMENT;

END trg_bill_status_update;
/

PROMPT trg_bill_status_update created -- BILL.STATUS now updates automatically on payment insert/update/delete.
