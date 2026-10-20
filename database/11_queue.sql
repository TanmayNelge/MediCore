-- =====================================================================
-- 11_queue.sql
-- MediCore HCMS - Priority-aware queue operations (SERVICE_QUEUE table
-- defined in 01_schema.sql). Run AFTER 07_functions.sql (uses
-- determine_appointment_priority).
--
-- Design: SERVICE_QUEUE generalizes OPD, Emergency, Lab, and Pharmacy
-- queues via queue_type, avoiding four near-identical tables.
-- queue_number is scoped per type+date; priority_level 1 = most urgent;
-- status flows WAITING -> CALLED -> IN_SERVICE -> COMPLETED, or CANCELLED.
-- Behavior is hybrid priority + FIFO: within the same priority_level,
-- earlier arrival_time wins; across levels, lower priority_level always
-- wins, so an emergency patient jumps a full OPD line regardless of
-- arrival order.
-- =====================================================================
-- Add a patient to a queue
CREATE OR REPLACE PROCEDURE add_to_queue(
    p_queue_type IN VARCHAR2, p_patient_id IN NUMBER,
    p_doctor_id IN NUMBER DEFAULT NULL, p_department_id IN NUMBER DEFAULT NULL,
    p_queue_id OUT NUMBER
) IS
    v_qnum NUMBER;
    v_priority NUMBER;
BEGIN
    SELECT NVL(MAX(queue_number),0) + 1 INTO v_qnum
    FROM service_queue WHERE queue_type = p_queue_type AND queue_date = TRUNC(SYSDATE);
    v_priority := determine_appointment_priority(p_patient_id, p_queue_type);
    INSERT INTO service_queue (queue_type, queue_number, patient_id, doctor_id, department_id, priority_level)
    VALUES (p_queue_type, v_qnum, p_patient_id, p_doctor_id, p_department_id, v_priority)
    RETURNING queue_id INTO p_queue_id;
    COMMIT;
END add_to_queue;
/
-- Get and lock the next patient to call for a given queue type (priority, then FIFO)
CREATE OR REPLACE PROCEDURE get_next_patient(
    p_queue_type IN VARCHAR2, p_queue_id OUT NUMBER, p_patient_id OUT NUMBER
) IS
    CURSOR c_next IS
        SELECT queue_id, patient_id FROM service_queue
        WHERE queue_type = p_queue_type AND status = 'WAITING' AND queue_date = TRUNC(SYSDATE)
        ORDER BY priority_level ASC, arrival_time ASC
        FOR UPDATE SKIP LOCKED;   -- concurrency-safe: two receptionists won't grab the same patient
BEGIN
    OPEN c_next;
    FETCH c_next INTO p_queue_id, p_patient_id;
    IF c_next%NOTFOUND THEN
        CLOSE c_next;
        p_queue_id := NULL; p_patient_id := NULL;
        RETURN;
    END IF;
    UPDATE service_queue SET status = 'CALLED', called_time = SYSTIMESTAMP
    WHERE CURRENT OF c_next;
    CLOSE c_next;
    COMMIT;
END get_next_patient;
/
-- Prioritize an emergency patient (used when a walk-in emergency arrives)
CREATE OR REPLACE PROCEDURE prioritize_emergency(p_patient_id IN NUMBER, p_queue_id OUT NUMBER) IS
BEGIN
    add_to_queue('EMERGENCY', p_patient_id, NULL, NULL, p_queue_id);
    UPDATE service_queue SET priority_level = 1 WHERE queue_id = p_queue_id;
    COMMIT;
END prioritize_emergency;
/
-- Mark a patient as served (called -> in_service -> completed, collapsed to one call for simplicity)
CREATE OR REPLACE PROCEDURE mark_queue_completed(p_queue_id IN NUMBER) IS
BEGIN
    UPDATE service_queue SET status = 'COMPLETED' WHERE queue_id = p_queue_id AND status IN ('CALLED','IN_SERVICE');
    IF SQL%ROWCOUNT = 0 THEN
        RAISE_APPLICATION_ERROR(-20020, 'Queue entry not in a completable state.');
    END IF;
    COMMIT;
END mark_queue_completed;
/
-- Cancel a queue entry (e.g., patient left)
CREATE OR REPLACE PROCEDURE cancel_queue_entry(p_queue_id IN NUMBER) IS
BEGIN
    UPDATE service_queue SET status = 'CANCELLED' WHERE queue_id = p_queue_id AND status = 'WAITING';
    COMMIT;
END cancel_queue_entry;
/
-- Estimated waiting time (computed on read, never stored - it would go
-- stale). Position and rough ETA for a given queue, using a fixed average
-- service time per queue type:
--
-- SELECT queue_id, patient_id, priority_level,
--        ROW_NUMBER() OVER (ORDER BY priority_level, arrival_time) AS position_in_line,
--        (ROW_NUMBER() OVER (ORDER BY priority_level, arrival_time) - 1) *
--          CASE queue_type WHEN 'EMERGENCY' THEN 5 WHEN 'LAB' THEN 8 WHEN 'PHARMACY' THEN 3 ELSE 12 END
--          AS est_wait_minutes
-- FROM service_queue
-- WHERE queue_type = 'OPD' AND status = 'WAITING' AND queue_date = TRUNC(SYSDATE);
-- FIFO vs priority queue (viva note): a pure FIFO queue is fair but wrong
-- for healthcare (a heart-attack walk-in must not wait behind 15 routine
-- OPD patients); a pure priority queue can starve low-priority patients
-- indefinitely. ORDER BY priority_level, arrival_time is a hybrid: priority
-- class first (bounded to 5 levels, so starvation is limited), FIFO within
-- a class - the standard real-world triage pattern.
-- On Oracle Advanced Queuing (AQ): DBMS_AQ is for asynchronous,
-- transactional messaging between producers/consumers (e.g. "notify
-- pharmacy when a prescription is added"). It is conceptually relevant but
-- NOT used for the patient-facing queue here - the queue is a simple,
-- directly queryable table because the requirement is "show current
-- position / call next," a table-scan/ORDER BY problem, not a
-- message-passing problem. Noted as an extension point, not implemented,
-- to avoid overengineering.
