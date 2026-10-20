# app/db/helpers.py
# Small shared helper so every router serializes cursor results the same
# way patients.py already established, instead of nine slightly different
# copies of the same three lines.

def rows_to_dicts(cursor, rows):
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]
