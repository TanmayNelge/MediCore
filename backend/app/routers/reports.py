# app/routers/reports.py
# Report generation. Every report is ONE SQL statement that demonstrates a
# specific DBMS concept (tagged in "concept"), executed on the READ-ONLY
# connection (readonly1) - reports can never modify data.
#
#   GET /reports/catalog          -> list of reports + parameters
#   GET /reports/run/{report_id}  -> run one report (params as query string)
#
# The three original endpoints (/reports/dashboard, /reports/doctor-workload,
# /reports/admitted-patients) are kept for the pages that already use them.

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.jwt import AppUser, require_roles
from app.db.helpers import query
from app.db.session import get_connection, get_readonly_connection

router = APIRouter()

REPORTS = [
    {
        "id": "dept_revenue", "title": "Revenue by department",
        "description": "Billed amount per department and revenue stream, with a grand total row.",
        "concept": "View + GROUP BY ROLLUP + GROUPING() + CASE",
        "params": [{"name": "months", "label": "Last N months", "type": "int", "default": 6}],
        "chart": {"label": "department", "value": "billed"},
        "sql": """SELECT CASE WHEN GROUPING(department_name) = 1 THEN '== ALL DEPARTMENTS ==' ELSE department_name END AS department,
       SUM(bills) AS bills, SUM(billed_amount) AS billed, SUM(consultation_amount) AS consultation,
       SUM(lab_amount) AS lab, SUM(medicine_amount) AS medicine, SUM(inpatient_amount) AS inpatient
  FROM vw_department_revenue
 WHERE bill_month >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -:months)
 GROUP BY ROLLUP (department_name)
 ORDER BY GROUPING(department_name), billed DESC""",
    },
    {
        "id": "noshow_by_dept", "title": "No-show rate by department",
        "description": "Share of resolved appointments the patient did not attend; only departments with enough volume.",
        "concept": "4-table JOIN + GROUP BY + HAVING + conditional aggregation",
        "params": [{"name": "min_appts", "label": "Min. resolved appointments", "type": "int", "default": 50}],
        "chart": {"label": "department_name", "value": "no_show_pct"},
        "sql": """SELECT dep.department_name,
       COUNT(*) AS resolved,
       SUM(CASE WHEN a.status = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_shows,
       ROUND(100 * SUM(CASE WHEN a.status = 'NO_SHOW' THEN 1 ELSE 0 END) / COUNT(*), 1) AS no_show_pct,
       ROUND(AVG(a.appt_date - TRUNC(CAST(a.created_at AS DATE))), 1) AS avg_lead_days
  FROM appointment a
  JOIN doctor d       ON d.doctor_id = a.doctor_id
  JOIN department dep ON dep.department_id = d.department_id
 WHERE a.status IN ('COMPLETED', 'NO_SHOW')
 GROUP BY dep.department_name
HAVING COUNT(*) >= :min_appts
 ORDER BY no_show_pct DESC""",
    },
    {
        "id": "monthly_trend", "title": "Monthly appointment trend",
        "description": "Appointments per month by outcome, with month-over-month change.",
        "concept": "GROUP BY TRUNC(date,'MM') + window function LAG() OVER",
        "params": [{"name": "months", "label": "Last N months", "type": "int", "default": 12}],
        "chart": {"label": "month", "value": "total"},
        "sql": """SELECT TO_CHAR(TRUNC(appt_date, 'MM'), 'YYYY-MM') AS month,
       COUNT(*) AS total,
       SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN status = 'NO_SHOW'   THEN 1 ELSE 0 END) AS no_shows,
       SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled,
       COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY TRUNC(appt_date, 'MM')) AS change_vs_prev
  FROM appointment
 WHERE appt_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -:months) AND appt_date < TRUNC(SYSDATE)
 GROUP BY TRUNC(appt_date, 'MM')
 ORDER BY TRUNC(appt_date, 'MM')""",
    },
    {
        "id": "top_diagnoses", "title": "Most common diagnoses",
        "description": "Diagnoses ranked by number of cases, with share of severe cases.",
        "concept": "GROUP BY + HAVING + RANK() OVER + ratio",
        "params": [{"name": "min_cases", "label": "Min. cases", "type": "int", "default": 20}],
        "chart": {"label": "disease_name", "value": "cases"},
        "sql": """SELECT RANK() OVER (ORDER BY COUNT(*) DESC) AS rank_no,
       ds.disease_name, dg.disease_code, COUNT(*) AS cases,
       COUNT(DISTINCT dg.patient_id) AS patients,
       ROUND(100 * SUM(CASE WHEN dg.severity = 'SEVERE' THEN 1 ELSE 0 END) / COUNT(*), 1) AS severe_pct
  FROM diagnosis dg JOIN disease ds ON ds.disease_code = dg.disease_code
 GROUP BY ds.disease_name, dg.disease_code
HAVING COUNT(*) >= :min_cases
 ORDER BY cases DESC""",
    },
    {
        "id": "frequent_no_show", "title": "Patients who frequently miss appointments",
        "description": "Patients with repeated no-shows, and whether they have another visit booked (call list).",
        "concept": "Correlated sub-queries + EXISTS + GROUP BY / HAVING",
        "params": [{"name": "min_no_shows", "label": "Min. no-shows", "type": "int", "default": 3}],
        "chart": {"label": "patient", "value": "no_shows"},
        "sql": """SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient, p.phone,
       COUNT(*) AS no_shows,
       (SELECT COUNT(*) FROM appointment x WHERE x.patient_id = p.patient_id
           AND x.status IN ('COMPLETED','NO_SHOW')) AS resolved_visits,
       TO_CHAR(MAX(a.appt_date), 'YYYY-MM-DD') AS last_no_show,
       CASE WHEN EXISTS (SELECT 1 FROM appointment f WHERE f.patient_id = p.patient_id
                            AND f.status = 'SCHEDULED' AND f.appt_date >= TRUNC(SYSDATE))
            THEN 'YES - call to confirm' ELSE 'no' END AS has_upcoming
  FROM patient p
  JOIN appointment a ON a.patient_id = p.patient_id AND a.status = 'NO_SHOW'
 GROUP BY p.patient_id, p.first_name, p.last_name, p.phone
HAVING COUNT(*) >= :min_no_shows
 ORDER BY no_shows DESC, last_no_show DESC""",
    },
    {
        "id": "outstanding_ageing", "title": "Outstanding bills - ageing",
        "description": "Money still owed, grouped into 0-30 / 31-90 / 90+ day buckets.",
        "concept": "View on a view (vw_outstanding_bills -> vw_patient_billing_summary) + GROUP BY",
        "params": [],
        "chart": {"label": "ageing_bucket", "value": "balance_due"},
        "sql": """SELECT ageing_bucket, COUNT(*) AS bills, SUM(total_amount) AS billed,
       SUM(total_paid) AS paid, SUM(balance_due) AS balance_due,
       ROUND(AVG(days_outstanding)) AS avg_days
  FROM vw_outstanding_bills
 GROUP BY ageing_bucket
 ORDER BY MIN(days_outstanding)""",
    },
    {
        "id": "payment_mix", "title": "Collections by payment mode",
        "description": "Payments received per month and mode with sub-totals.",
        "concept": "GROUP BY ROLLUP on two columns (sub-totals + grand total)",
        "params": [{"name": "months", "label": "Last N months", "type": "int", "default": 3}],
        "chart": {"label": "payment_mode", "value": "collected"},
        "sql": """SELECT CASE WHEN GROUPING(TRUNC(paid_date, 'MM')) = 1 THEN '== TOTAL =='
            ELSE TO_CHAR(TRUNC(paid_date, 'MM'), 'YYYY-MM') END AS month,
       CASE WHEN GROUPING(payment_mode) = 1 THEN '(all modes)' ELSE payment_mode END AS payment_mode,
       COUNT(*) AS payments, SUM(amount_paid) AS collected
  FROM payment
 WHERE paid_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -:months)
 GROUP BY ROLLUP (TRUNC(paid_date, 'MM'), payment_mode)
 ORDER BY TRUNC(paid_date, 'MM') NULLS LAST, GROUPING(payment_mode), collected DESC""",
    },
    {
        "id": "bed_occupancy", "title": "Bed occupancy by department",
        "description": "Beds per department, how many are occupied right now, and average length of stay.",
        "concept": "LEFT OUTER JOIN + correlated scalar sub-query + CASE",
        "params": [],
        "chart": {"label": "department_name", "value": "occupancy_pct"},
        "sql": """SELECT dep.department_name, COUNT(rb.room_bed_id) AS beds,
       SUM(CASE WHEN rb.status = 'OCCUPIED' THEN 1 ELSE 0 END) AS occupied,
       SUM(CASE WHEN rb.status = 'MAINTENANCE' THEN 1 ELSE 0 END) AS maintenance,
       ROUND(100 * SUM(CASE WHEN rb.status = 'OCCUPIED' THEN 1 ELSE 0 END) / NULLIF(COUNT(rb.room_bed_id), 0), 1) AS occupancy_pct,
       (SELECT ROUND(AVG(ad.discharge_date - ad.admit_date), 1)
          FROM admission ad JOIN room_bed b2 ON b2.room_bed_id = ad.room_bed_id
         WHERE b2.department_id = dep.department_id AND ad.status = 'DISCHARGED') AS avg_stay_days
  FROM department dep
  LEFT JOIN room_bed rb ON rb.department_id = dep.department_id
 GROUP BY dep.department_id, dep.department_name
HAVING COUNT(rb.room_bed_id) > 0
 ORDER BY occupancy_pct DESC""",
    },
    {
        "id": "inventory_alerts", "title": "Pharmacy stock & expiry alerts",
        "description": "Medicines at/below reorder level or expiring soon.",
        "concept": "View + JOIN + date arithmetic + OR filter",
        "params": [{"name": "days", "label": "Expiring within (days)", "type": "int", "default": 120}],
        "chart": {"label": "medicine_name", "value": "stock_quantity"},
        "sql": """SELECT v.medicine_name, m.category, v.stock_quantity, v.reorder_level, v.stock_status,
       TO_CHAR(m.expiry_date, 'YYYY-MM-DD') AS expiry_date, m.expiry_date - TRUNC(SYSDATE) AS days_to_expiry,
       (SELECT NVL(SUM(pi.quantity), 0) FROM prescription_item pi JOIN prescription pr ON pr.prescription_id = pi.prescription_id
         WHERE pi.medicine_id = m.medicine_id AND pr.prescribed_date >= TRUNC(SYSDATE) - 30) AS used_last_30_days
  FROM vw_medicine_inventory_status v
  JOIN medicine m ON m.medicine_id = v.medicine_id
 WHERE v.stock_status = 'REORDER' OR m.expiry_date <= TRUNC(SYSDATE) + :days
 ORDER BY v.stock_status DESC, days_to_expiry""",
    },
    {
        "id": "lab_turnaround", "title": "Lab test volume & turnaround",
        "description": "Orders, completion and average days to result per test.",
        "concept": "View with LEFT JOIN + AVG of date difference",
        "params": [],
        "chart": {"label": "test_name", "value": "orders"},
        "sql": "SELECT * FROM vw_lab_turnaround WHERE orders > 0 ORDER BY orders DESC",
    },
    {
        "id": "doctor_ranking", "title": "Doctor workload ranking",
        "description": "Completed consultations per doctor, ranked inside their department.",
        "concept": "DENSE_RANK() OVER (PARTITION BY ...) - analytic function",
        "params": [{"name": "days", "label": "Last N days", "type": "int", "default": 90}],
        "chart": {"label": "doctor", "value": "completed"},
        "sql": """SELECT dep.department_name, 'Dr. ' || d.first_name || ' ' || d.last_name AS doctor,
       COUNT(*) AS completed,
       DENSE_RANK() OVER (PARTITION BY dep.department_name ORDER BY COUNT(*) DESC) AS rank_in_department,
       SUM(d.consultation_fee) AS consultation_revenue
  FROM appointment a
  JOIN doctor d       ON d.doctor_id = a.doctor_id
  JOIN department dep ON dep.department_id = d.department_id
 WHERE a.status = 'COMPLETED' AND a.appt_date >= TRUNC(SYSDATE) - :days
 GROUP BY dep.department_name, d.doctor_id, d.first_name, d.last_name
 ORDER BY dep.department_name, rank_in_department""",
    },
    {
        "id": "age_gender", "title": "Patient age / gender profile",
        "description": "Patients per age band split by gender.",
        "concept": "PIVOT + CASE bucketing on a derived column",
        "params": [],
        "chart": {"label": "age_band", "value": "total"},
        "sql": """SELECT age_band, NVL(male, 0) AS male, NVL(female, 0) AS female, NVL(other, 0) AS other,
       NVL(male, 0) + NVL(female, 0) + NVL(other, 0) AS total
  FROM (SELECT CASE WHEN MONTHS_BETWEEN(SYSDATE, dob) / 12 < 13 THEN '00-12'
                    WHEN MONTHS_BETWEEN(SYSDATE, dob) / 12 < 20 THEN '13-19'
                    WHEN MONTHS_BETWEEN(SYSDATE, dob) / 12 < 40 THEN '20-39'
                    WHEN MONTHS_BETWEEN(SYSDATE, dob) / 12 < 60 THEN '40-59'
                    ELSE '60+' END AS age_band, gender
          FROM patient)
 PIVOT (COUNT(*) FOR gender IN ('M' AS male, 'F' AS female, 'O' AS other))
 ORDER BY age_band""",
    },
    {
        "id": "insurance_mix", "title": "Insurance coverage",
        "description": "Patients per insurer, share of all patients and average sum insured.",
        "concept": "GROUP BY + scalar sub-query in SELECT (percentage of total) + UNION ALL",
        "params": [],
        "chart": {"label": "provider", "value": "patients"},
        "sql": """SELECT provider_name AS provider, COUNT(*) AS patients,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM patient), 1) AS pct_of_patients,
       ROUND(AVG(coverage_amount)) AS avg_cover,
       SUM(CASE WHEN valid_until < TRUNC(SYSDATE) THEN 1 ELSE 0 END) AS expired
  FROM insurance_policy GROUP BY provider_name
UNION ALL
SELECT '(self-pay / no policy)', COUNT(*), ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM patient), 1), NULL, NULL
  FROM patient p WHERE NOT EXISTS (SELECT 1 FROM insurance_policy ip WHERE ip.patient_id = p.patient_id)
 ORDER BY 2 DESC""",
    },
    {
        "id": "ml_risk", "title": "ML: upcoming high-risk appointments",
        "description": "Output of the no-show model joined to live appointment data (active model only).",
        "concept": "View joining ML_PREDICTION + ML_MODEL_RUN + 4 tables",
        "params": [],
        "chart": {"label": "patient_name", "value": "probability"},
        "sql": """SELECT TO_CHAR(appt_date, 'YYYY-MM-DD') AS appt_date, appt_time, patient_name, phone, doctor_name,
       department_name, ROUND(probability * 100, 1) AS probability, risk_band, risk_factors
  FROM vw_upcoming_noshow_risk WHERE risk_band IN ('HIGH', 'MEDIUM')
 ORDER BY probability DESC""",
    },
    {
        "id": "audit_trail", "title": "Audit trail (admin only)",
        "description": "Latest changes recorded by the audit triggers, with the Oracle user who made them.",
        "concept": "Trigger-populated audit table + LEFT JOIN to APP_USER",
        "params": [{"name": "max_rows", "label": "Rows", "type": "int", "default": 50}],
        "admin_only": True,
        "chart": None,
        "sql": """SELECT al.audit_id, TO_CHAR(al.action_timestamp, 'YYYY-MM-DD HH24:MI:SS') AS at_time,
       NVL(u.username, '(schema owner)') AS changed_by, al.table_name, al.operation, al.record_id,
       DBMS_LOB.SUBSTR(al.old_value, 200, 1) AS old_value, DBMS_LOB.SUBSTR(al.new_value, 200, 1) AS new_value
  FROM audit_log al LEFT JOIN app_user u ON u.user_id = al.user_id
 ORDER BY al.action_timestamp DESC FETCH FIRST :max_rows ROWS ONLY""",
    },
]
_BY_ID = {r["id"]: r for r in REPORTS}


@router.get("/reports/catalog")
def catalog():
    return {"reports": [{k: v for k, v in r.items() if k != "sql"} | {"sql": r["sql"]} for r in REPORTS]}


def _binds(rep, request: Request):
    binds = {}
    for p in rep["params"]:
        raw = request.query_params.get(p["name"], p["default"])
        try:
            binds[p["name"]] = int(raw) if p["type"] == "int" else str(raw)
        except (TypeError, ValueError):
            raise HTTPException(422, f"Parameter {p['name']} must be {p['type']}")
    return binds


@router.get("/reports/run/{report_id}")
def run_report(report_id: str, request: Request, conn=Depends(get_readonly_connection)):
    rep = _BY_ID.get(report_id)
    if not rep:
        raise HTTPException(404, f"Unknown report '{report_id}'")
    if rep.get("admin_only"):
        raise HTTPException(400, "Use /reports/audit for the audit trail (admin connection).")
    res = query(conn, rep["sql"], _binds(rep, request))
    return {**res, "report": {k: v for k, v in rep.items() if k != "sql"}}


@router.get("/reports/audit")
def audit(request: Request, conn=Depends(get_connection), user: AppUser = Depends(require_roles("ADMIN"))):
    """AUDIT_LOG is not granted to READONLY_ROLE, so this one runs on the
    caller's own (admin1) connection."""
    rep = _BY_ID["audit_trail"]
    res = query(conn, rep["sql"], _binds(rep, request))
    return {**res, "report": {k: v for k, v in rep.items() if k != "sql"}}


@router.get("/reports/dashboard")
def dashboard_kpis(conn=Depends(get_readonly_connection)):
    """Dashboard cards in one round trip (six scalar sub-queries)."""
    sql = """SELECT
      (SELECT COUNT(*) FROM patient) AS total_patients,
      (SELECT COUNT(*) FROM appointment WHERE appt_date = TRUNC(SYSDATE)) AS todays_appointments,
      (SELECT COUNT(*) FROM service_queue WHERE status='WAITING' AND queue_date=TRUNC(SYSDATE)) AS current_queue,
      (SELECT COUNT(*) FROM room_bed WHERE status='AVAILABLE') AS available_beds,
      (SELECT COUNT(*) FROM lab_order WHERE status IN ('ORDERED','SAMPLE_COLLECTED')) AS pending_labs,
      (SELECT NVL(SUM(amount_paid),0) FROM payment WHERE paid_date >= TRUNC(SYSDATE) - 6) AS revenue_7_days,
      (SELECT COUNT(*) FROM vw_upcoming_noshow_risk WHERE risk_band = 'HIGH') AS high_risk_upcoming,
      (SELECT NVL(SUM(balance_due),0) FROM vw_outstanding_bills) AS outstanding_amount
    FROM dual"""
    return query(conn, sql)


@router.get("/reports/doctor-workload")
def doctor_workload(conn=Depends(get_readonly_connection)):
    return query(conn, "SELECT * FROM vw_doctor_workload ORDER BY total_appointments DESC")


@router.get("/reports/admitted-patients")
def admitted_patients(conn=Depends(get_readonly_connection)):
    return query(conn, "SELECT admission_id, patient_name, room_no, bed_no, TO_CHAR(admit_date, 'YYYY-MM-DD') AS admit_date, "
                       "admitting_doctor FROM vw_current_admitted_patients ORDER BY admit_date")
