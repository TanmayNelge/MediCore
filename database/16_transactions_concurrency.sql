-- =====================================================================
-- 16_transactions_concurrency.sql
-- MediCore HCMS - Transactions, ACID and concurrency (requirement 4).
--
-- HOW TO RUN: open TWO worksheets in SQL Developer (or two SQLcl
-- windows), both connected as HCMS_ADMIN. Run the "SESSION A" lines in
-- the first and "SESSION B" lines in the second, in the numbered order.
-- Everything is ROLLED BACK at the end, so the seed data is unchanged.
-- (The web app's DBMS Concept Lab page runs scenarios 1, 2, 4 and 5
--  automatically with two real Oracle connections and shows each step.)
-- NOT executed by install.py.
-- =====================================================================

-- =====================================================================
-- ACID in this project
--   A - Atomicity  : book_appointment inserts APPOINTMENT + SERVICE_QUEUE;
--                    any error -> ROLLBACK of both (08_procedures.sql).
--   C - Consistency: PK/FK/UNIQUE/CHECK constraints + triggers
--                    (e.g. trg_prescription_stock_check) reject any
--                    statement that would break a business rule; the
--                    statement is rolled back, the DB stays valid.
--   I - Isolation  : Oracle default READ COMMITTED with multi-version
--                    read consistency: readers never block writers and
--                    never see uncommitted data (no dirty reads).
--   D - Durability : after COMMIT the redo log is on disk - the payment
--                    survives a crash / restart of the database.
-- =====================================================================

-- ---------------------------------------------------------------------
-- SCENARIO 1 - Atomicity with SAVEPOINT / ROLLBACK TO
-- ---------------------------------------------------------------------
-- (single session; SET SERVEROUTPUT ON first)
DECLARE
    v_bill   NUMBER;
    v_status bill.status%TYPE;
    PROCEDURE show(p_step VARCHAR2) IS
    BEGIN
        SELECT status INTO v_status FROM bill WHERE bill_id = v_bill;
        DBMS_OUTPUT.PUT_LINE(RPAD(p_step, 45) || ' bill ' || v_bill || ' status=' || v_status ||
                             ' balance=' || fn_bill_balance(v_bill));
    END;
BEGIN
    SELECT MIN(bill_id) INTO v_bill FROM bill WHERE status = 'UNPAID';
    show('1 start');
    SAVEPOINT sp_start;
    INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (v_bill, 100, 'CASH');
    show('2 after payment (trigger flipped status)');
    SAVEPOINT sp_after_payment;
    BEGIN
        INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (-1, 50, 'CASH');
    EXCEPTION WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('3 bad insert rejected: ' || SQLERRM);   -- ORA-02291 FK violation
        ROLLBACK TO sp_after_payment;                                   -- first payment still pending
    END;
    show('4 after ROLLBACK TO sp_after_payment');
    ROLLBACK TO sp_start;
    show('5 after ROLLBACK TO sp_start');
    ROLLBACK;
END;
/

-- ---------------------------------------------------------------------
-- SCENARIO 2 - Isolation: no dirty reads (READ COMMITTED)
-- ---------------------------------------------------------------------
-- 1 SESSION A:
UPDATE medicine SET stock_quantity = stock_quantity + 1000 WHERE medicine_code = 'MED-001';
-- 2 SESSION B: still sees the OLD value (A has not committed)
SELECT stock_quantity FROM medicine WHERE medicine_code = 'MED-001';
-- 3 SESSION A:
ROLLBACK;

-- ---------------------------------------------------------------------
-- SCENARIO 3 - Lost update prevented with SELECT ... FOR UPDATE
--   Two billing clerks pay the SAME bill at the same moment.
-- ---------------------------------------------------------------------
-- 1 SESSION A:  locks the bill row
SELECT bill_id, status FROM bill WHERE bill_id = 5 FOR UPDATE;
-- 2 SESSION B:  BLOCKS here until A commits/rolls back (row lock, TX enqueue)
SELECT bill_id, status FROM bill WHERE bill_id = 5 FOR UPDATE;
-- 3 SESSION A:
ROLLBACK;            -- B now continues and sees the current balance
-- 4 SESSION B:
ROLLBACK;
-- record_payment() in 08_procedures.sql uses exactly this pattern, so the
-- second clerk can never take the balance below zero.

-- ---------------------------------------------------------------------
-- SCENARIO 4 - NOWAIT and SKIP LOCKED (queue workers)
-- ---------------------------------------------------------------------
-- 1 SESSION A: nurse 1 calls the next WAITING patient
--   (FETCH FIRST cannot be combined with FOR UPDATE - ORA-02014 - so the
--    first waiting row is picked in a sub-query and locked by its key)
SELECT queue_id, patient_id FROM service_queue
 WHERE queue_id = (SELECT queue_id FROM service_queue
                    WHERE status = 'WAITING' AND queue_date = TRUNC(SYSDATE)
                    ORDER BY priority_level, arrival_time FETCH FIRST 1 ROWS ONLY)
 FOR UPDATE;
-- 2 SESSION B: NOWAIT fails immediately instead of waiting
SELECT queue_id FROM service_queue WHERE status = 'WAITING' AND queue_date = TRUNC(SYSDATE)
 FOR UPDATE NOWAIT;                       -- ORA-00054 resource busy
-- 3 SESSION B: SKIP LOCKED simply takes the NEXT free patient
--   (this is what get_next_patient() in 11_queue.sql does)
SELECT queue_id, patient_id FROM service_queue
 WHERE status = 'WAITING' AND queue_date = TRUNC(SYSDATE)
 ORDER BY priority_level, arrival_time
 FOR UPDATE SKIP LOCKED;
-- 4 both sessions:
ROLLBACK;

-- ---------------------------------------------------------------------
-- SCENARIO 5 - Deadlock (ORA-00060) and how lock ordering avoids it
-- ---------------------------------------------------------------------
-- 1 SESSION A:
UPDATE room_bed SET daily_rate = daily_rate WHERE room_bed_id = 1;
-- 2 SESSION B:
UPDATE room_bed SET daily_rate = daily_rate WHERE room_bed_id = 2;
-- 3 SESSION A: waits for B
UPDATE room_bed SET daily_rate = daily_rate WHERE room_bed_id = 2;
-- 4 SESSION B: closes the cycle -> Oracle detects it within ~3 s and
--   raises ORA-00060 in ONE of the sessions (that statement is rolled back)
UPDATE room_bed SET daily_rate = daily_rate WHERE room_bed_id = 1;
-- 5 both: ROLLBACK;
-- Prevention: transfer_bed() always locks beds in ascending room_bed_id
-- order (ORDER BY room_bed_id FOR UPDATE), so a cycle cannot form.

-- ---------------------------------------------------------------------
-- SCENARIO 6 - SERIALIZABLE isolation (phantom-free snapshot)
-- ---------------------------------------------------------------------
-- 1 SESSION A:
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SELECT COUNT(*) FROM appointment WHERE appt_date = TRUNC(SYSDATE);
-- 2 SESSION B: books a new appointment for today and COMMITs
--   (e.g. through the web app)
-- 3 SESSION A: the count is UNCHANGED - A works on a snapshot taken when
--   its transaction began. Under READ COMMITTED it would see the new row
--   (a "phantom"). If A now tried to update a row B changed, Oracle would
--   raise ORA-08177 "can't serialize access".
SELECT COUNT(*) FROM appointment WHERE appt_date = TRUNC(SYSDATE);
COMMIT;

-- ---------------------------------------------------------------------
-- SCENARIO 7 - Statement-level atomicity with a trigger
-- ---------------------------------------------------------------------
-- Prescribing more than the stock: trg_prescription_stock_check raises
-- -20011 and the WHOLE add_prescription() call (prescription header +
-- item) is rolled back - no orphan prescription header remains.
DECLARE
    v_id NUMBER;
BEGIN
    add_prescription(1, 1, NULL, 46, '10mg once daily', 5, 99999, v_id);
EXCEPTION
    WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('Rejected: ' || SQLERRM);
END;
/

-- Locks currently held (run as SYSTEM while a scenario is in progress):
-- SELECT s.sid, s.username, l.type, l.lmode, l.request, o.object_name
--   FROM v$lock l JOIN v$session s ON s.sid = l.sid
--   LEFT JOIN dba_objects o ON o.object_id = l.id1
--  WHERE s.username IS NOT NULL;
