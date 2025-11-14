from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_connection

app = Flask(__name__)
CORS(app)

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"ok": False, "message": "Thiếu tài khoản hoặc mật khẩu"}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        return jsonify({"ok": True, "user": {"username": user["username"], "full_name": user["full_name"]}})
    else:
        return jsonify({"ok": False, "message": "Sai tài khoản hoặc mật khẩu"}), 401
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    print("DEBUG /api/register payload:", data)  # xem payload thực tế

    def as_text(v):
        if isinstance(v, str):
            return v
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict):
            # cố gắng lấy các key hay gặp khi gửi nhầm object
            for k in ("value", "username", "name"):
                if isinstance(v.get(k), str):
                    return v[k]
        return ""

    username = as_text(data.get("username")).strip()
    password = as_text(data.get("password")).strip()
    full_name = as_text(data.get("full_name")).strip()

    if not username or not password or not full_name:
        return jsonify({"ok": False, "message": "Thiếu username/password/full_name"}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id FROM users WHERE username=%s LIMIT 1", (username,))
    if cur.fetchone():
        cur.close();
        conn.close()
        return jsonify({"ok": False, "message": "Tài khoản đã tồn tại"}), 409

    cur.execute(
        "INSERT INTO users (username, password, full_name) VALUES (%s, %s, %s)",
        (username, password, full_name)
    )
    conn.commit()
    cur.close();
    conn.close()
    return jsonify({"ok": True, "message": "Đăng ký thành công"})
@app.route("/api/lines")
def get_lines():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            LineID   AS idline,
            LineName AS ten_line
        FROM productionline
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(rows)
@app.route("/api/lines/<int:idline>/machines")
def get_machines_by_line(idline):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            MachineID   AS id,
            MachineName AS name
        FROM machine
        WHERE LineID = %s
    """, (idline,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)
@app.route("/api/machines/<int:machine_id>/day")
def get_machine_day(machine_id):
    day = request.args.get("day")
    if not day:
        return jsonify({"error": "Missing day param"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # --------- LẤY DỮ LIỆU THỜI GIAN (dayvalues) ----------
    cursor.execute("""
        SELECT 
            Days,
            PowerRun,
            Operation,
            SmallStop,
            Fault,
            Break,
            Maintenance,
            Eat,
            Waiting,
            MachineryEdit,
            ChangeProductCode,
            Glue_CleaningPaper,
            Others
        FROM dayvalues
        WHERE MachineID = %s AND Days = %s
        LIMIT 1
    """, (machine_id, day))

    row = cursor.fetchone()

    # (tí nữa còn dùng connection, đừng đóng vội)
    if not row:
        cursor.close()
        conn.close()
        return jsonify({
            "machine_id": machine_id,
            "day": day,
            "data": None
        })

    # ---- POWER RUN: 2 chữ sau dấu chấm ----
    raw_power = row.get("PowerRun")
    try:
        power_val = float(raw_power) if raw_power else 0.0
    except:
        power_val = 0.0
    power_run_str = f"{power_val:.2f}"

    # ---- CÁC CATEGORY (cho pie + bảng) ----
    categories_raw = {
        "Operation":          float(row["Operation"]          or 0.0),
        "SmallStop":          float(row["SmallStop"]          or 0.0),
        "Fault":              float(row["Fault"]              or 0.0),
        "Break":              float(row["Break"]              or 0.0),
        "Maintenance":        float(row["Maintenance"]        or 0.0),
        "Eat":                float(row["Eat"]                or 0.0),
        "Waiting":            float(row["Waiting"]            or 0.0),
        "MachineryEdit":      float(row["MachineryEdit"]      or 0.0),
        "ChangeProductCode":  float(row["ChangeProductCode"]  or 0.0),
        "Glue_CleaningPaper": float(row["Glue_CleaningPaper"] or 0.0),
        "Others":             float(row["Others"]             or 0.0),
    }

    total_hours = sum(categories_raw.values())
    if total_hours <= 0:
        total_hours = 1.0

    color_map = {
        "Operation":          "#00a03e",
        "SmallStop":          "#f97316",
        "Fault":              "#ef4444",
        "Break":              "#eab308",
        "Maintenance":        "#6b21a8",
        "Eat":                "#22c55e",
        "Waiting":            "#0ea5e9",
        "MachineryEdit":      "#1d4ed8",
        "ChangeProductCode":  "#a855f7",
        "Glue_CleaningPaper": "#fb7185",
        "Others":             "#6b7280",
    }

    detail_rows = []
    pie_data = []

    for label, value in categories_raw.items():
        hours = float(value)
        h = int(hours)
        m = int(round((hours - h) * 60))
        time_str = f"{h}h {m}m"

        ratio = round((hours / total_hours) * 100.0, 2)
        ratio_text = f"{ratio:.2f}%"

        detail_rows.append({
            "label": label,
            "value": hours,
            "time": time_str,
            "ratio": ratio,
            "ratio_text": ratio_text,
            "color": color_map[label],
        })

        pie_data.append({
            "name": label,
            "value": ratio,
            "color": color_map[label],
        })

    # --------- THÊM PHẦN PRODUCT: TOTAL / OK / NG / RATIO ----------
    # TODO: sửa lại tên bảng + cột cho đúng DB thực tế của bạn
    #
    # Ví dụ: bảng dayproduct có cột:
    #   MachineID, Days, Total, OK, NG
    #
    cursor.execute("""
        SELECT 
            totalproduct_actual AS Total,
            totalproduct_ok as OK,
            totalproduct_ok as NG
        FROM production_output
        WHERE machineid = %s AND days = %s
        LIMIT 1
    """, (machine_id, day))

    prod = cursor.fetchone()
    cursor.close()
    conn.close()

    if prod:
        total = float(prod["Total"] or 0)
        ok = float(prod["OK"] or 0)
        ng = float(prod["NG"] or 0)
    else:
        total, ok, ng = 0.0, 0.0, 0.0

    ratio = (ok * 100.0 / total) if total > 0 else 0.0

    product = {
        "total": int(total),
        "ok": int(ok),
        "ng": int(ng),
        "ratio": round(ratio, 2),
        "ratio_text": f"{ratio:.2f}%"
    }

    # --------- KẾT QUẢ TRẢ VỀ ----------
    result = {
        "machine_id": machine_id,
        "day": row["Days"],
        "power_run": power_run_str,
        "total_hours": round(total_hours, 2),
        "pie": pie_data,
        "details": detail_rows,
        "product": product,          # 👈 FE dùng cho bảng PRODUCT
    }

    return jsonify(result)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)