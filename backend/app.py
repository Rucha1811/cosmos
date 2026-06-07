import os
import sys
import uuid
import csv
import io
import json
import re
import warnings
import logging
import socket
from datetime import datetime

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["GIT_PYTHON_REFRESH"] = "quiet"

import numpy as np
from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    send_from_directory,
    url_for,
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from PIL import Image
import cv2

from paddleocr import PaddleOCR

app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/api/*": {"origins": "*"}})

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'cards.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)


class CardScan(db.Model):
    __tablename__ = "card_scans"
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(512), nullable=False)
    full_text = db.Column(db.Text, default="")

    industry = db.Column(db.String(200), default="")
    sales_branch = db.Column(db.String(200), default="")
    rating = db.Column(db.String(50), default="")
    city = db.Column(db.String(200), default="")
    state = db.Column(db.String(200), default="")
    gstin = db.Column(db.String(200), default="")
    assigned_to = db.Column(db.String(200), default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    texts = db.relationship("TextEntry", backref="scan", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "filename": self.filename,
            "image_url": url_for("uploaded_file", filename=os.path.basename(self.image_path)),
            "full_text": self.full_text,
            "industry": self.industry or "",
            "sales_branch": self.sales_branch or "",
            "rating": self.rating or "",
            "city": self.city or "",
            "state": self.state or "",
            "gstin": self.gstin or "",
            "assigned_to": self.assigned_to or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
            "text_count": len(self.texts),
        }


class TextEntry(db.Model):
    __tablename__ = "text_entries"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("card_scans.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    confidence = db.Column(db.Float, default=0.0)
    box_points = db.Column(db.Text, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "box_points": json.loads(self.box_points) if self.box_points else [],
        }


with app.app_context():
    db.create_all()


ocr_instance = None


def get_ocr():
    global ocr_instance
    if ocr_instance is None:
        ocr_instance = PaddleOCR(ocr_version="PP-OCRv4", lang="en")
    return ocr_instance


def auto_fill_fields(texts):
    fields = {
        "industry": "",
        "sales_branch": "",
        "rating": "",
        "city": "",
        "state": "",
        "gstin": "",
        "assigned_to": "",
    }

    INDIAN_CITIES = [
        "MUMBAI", "DELHI", "BANGALORE", "BENGALURU", "CHENNAI", "KOLKATA",
        "HYDERABAD", "AHMEDABAD", "PUNE", "JAIPUR", "LUCKNOW", "SURAT",
        "KOCHI", "COIMBATORE", "INDORE", "BHOPAL", "CHANDIGARH", "NAGPUR",
        "GURGAON", "NOIDA", "THANE", "VADODARA", "AGRA", "VARANASI",
        "PATNA", "RANCHI", "BHUBANESWAR", "AMRITSAR", "MYSORE", "MANGALORE",
        "VIJAYAWADA", "VISAKHAPATNAM", "LUDHIANA", "JABALPUR", "MADURAI",
        "RAJKOT", "NASHIK", "SURAT", "KANPUR", "TRICHY", "GOA", "PANJI",
    ]

    INDIAN_STATES = [
        "MAHARASHTRA", "KARNATAKA", "TAMIL NADU", "TAMILNADU", "KERALA",
        "ANDHRA PRADESH", "ANDHRA PRADESH", "TELANGANA", "UTTAR PRADESH",
        "GUJARAT", "RAJASTHAN", "MADHYA PRADESH", "BIHAR", "WEST BENGAL",
        "PUNJAB", "HARYANA", "JHARKHAND", "ODISHA", "ASSAM", "GOA",
        "CHHATTISGARH", "UTTARAKHAND", "HIMACHAL PRADESH", "DELHI",
    ]

    gstin_pattern = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}\b')

    for t in texts:
        clean = t.strip()
        upper = clean.upper()

        if not clean:
            continue

        if not fields["gstin"] and gstin_pattern.match(upper):
            fields["gstin"] = clean
            continue

        if not fields["rating"]:
            if re.match(r'^[A-Z]\+{1,2}$', upper) or upper in ["PLATINUM", "GOLD", "SILVER", "DIAMOND"]:
                fields["rating"] = clean
                continue

        if not fields["sales_branch"]:
            if any(kw in upper for kw in ["BRANCH", "OFFICE", "DEPOT", "SHOWROOM", "FACTORY", "WORKS"]):
                if upper not in ["WORKS"] or clean == t.strip():
                    fields["sales_branch"] = clean
                    continue

        if not fields["city"] and upper in INDIAN_CITIES:
            fields["city"] = clean
            continue

        if not fields["state"]:
            state_norm = upper.replace(" ", "")
            if upper in INDIAN_STATES or state_norm in [s.replace(" ", "") for s in INDIAN_STATES]:
                fields["state"] = clean
                continue

        if not fields["assigned_to"]:
            words = clean.split()
            if 2 <= len(words) <= 4:
                has_digit = any(c.isdigit() for c in clean)
                is_email = "@" in clean
                has_special = any(c in clean for c in ["@", ".com", "www.", "//", "(", ")", "-"])
                is_short_addr = any(kw in upper for kw in ["ROAD", "STREET", "NAGAR", "COLONY", "LAYOUT"])
                if not has_digit and not is_email and not has_special and not is_short_addr and len(clean) > 5:
                    if all(w[0].isalpha() and w[0].isupper() for w in words if w):
                        fields["assigned_to"] = clean
                        continue

    if not fields["industry"]:
        for t in texts:
            clean = t.strip()
            if not clean or clean == fields["assigned_to"] or clean == fields["sales_branch"]:
                continue
            has_digit = any(c.isdigit() for c in clean)
            is_email = "@" in clean
            is_phone = re.match(r'^[\d\s\+\-\(\)]{7,}$', clean)
            if len(clean) > 2 and not is_email and not is_phone:
                fields["industry"] = clean
                break

    return fields


FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


@app.route("/")
def index():
    if os.path.isdir(FRONTEND_DIR):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({
        "status": "Card Scanner API is running",
        "docs": "/api/scans",
    })


@app.route("/static/<path:filename>")
def static_files(filename):
    if os.path.isdir(FRONTEND_DIR):
        return send_from_directory(os.path.join(FRONTEND_DIR, "static"), filename)
    return jsonify({"error": "Not found"}), 404


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/scan", methods=["POST"])
def scan_card():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No image selected"}), 400

    scan_uuid = str(uuid.uuid4())
    safe_name = f"{scan_uuid}.png"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)

    try:
        img = Image.open(file.stream)
        img = img.convert("RGB")
        img.save(filepath, "PNG")
    except Exception as e:
        return jsonify({"error": f"Invalid image: {str(e)}"}), 400

    try:
        ocr = get_ocr()
        result = ocr.predict(filepath)
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"OCR failed: {str(e)}"}), 500

    r = result[0]

    rec_texts = r["rec_texts"] if r.get("rec_texts") else []
    rec_scores = r["rec_scores"] if r.get("rec_scores") else []
    dt_polys = r.get("dt_polys") or []

    full_text = "\n".join(rec_texts) if rec_texts else ""

    auto_filled = auto_fill_fields(rec_texts)

    scan = CardScan(
        uuid=scan_uuid,
        filename=file.filename,
        image_path=filepath,
        full_text=full_text,
        industry=auto_filled["industry"],
        sales_branch=auto_filled["sales_branch"],
        rating=auto_filled["rating"],
        city=auto_filled["city"],
        state=auto_filled["state"],
        gstin=auto_filled["gstin"],
        assigned_to=auto_filled["assigned_to"],
    )
    db.session.add(scan)
    db.session.flush()

    text_entries = []
    for i, txt in enumerate(rec_texts):
        score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
        poly = []
        if i < len(dt_polys):
            poly = [[float(coord) for coord in pt] for pt in dt_polys[i]]
        entry = TextEntry(
            scan_id=scan.id,
            text=txt,
            confidence=score,
            box_points=json.dumps(poly),
        )
        db.session.add(entry)
        text_entries.append(entry)

    db.session.commit()

    img = r.get("img")
    if img is None:
        img = r.get("doc_preprocessor_res", {}).get("output_img")

    if img is not None and isinstance(img, np.ndarray):
        vis_path = os.path.join(app.config["UPLOAD_FOLDER"], f"vis_{safe_name}")
        h, w = img.shape[:2]
        scale = min(1200 / w, 1200 / h, 1.0)
        if scale < 1.0:
            nw, nh = int(w * scale), int(h * scale)
            img = cv2.resize(img, (nw, nh))
            dt_polys_scaled = []
            for poly in dt_polys:
                dt_polys_scaled.append([[pt[0] * scale, pt[1] * scale] for pt in poly])
        else:
            dt_polys_scaled = dt_polys

        vis = img.copy()
        for i, poly in enumerate(dt_polys_scaled):
            pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(vis, [pts], True, (0, 255, 0), 2)
            if i < len(rec_texts):
                label = f"{rec_texts[i]} ({rec_scores[i]:.2f})" if i < len(rec_scores) else rec_texts[i]
                cx, cy = int(np.mean([p[0] for p in poly])), int(np.mean([p[1] for p in poly]))
                cv2.putText(vis, label, (cx - 50, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.imwrite(vis_path, vis)
        vis_url = url_for("uploaded_file", filename=f"vis_{safe_name}")
    else:
        vis_url = url_for("uploaded_file", filename=safe_name)

    return jsonify({
        "scan": scan.to_dict(),
        "vis_url": vis_url,
        "texts": [t.to_dict() for t in text_entries],
    })


@app.route("/api/scans", methods=["GET"])
def list_scans():
    scans = CardScan.query.order_by(CardScan.created_at.desc()).all()
    return jsonify({"scans": [s.to_dict() for s in scans]})


@app.route("/api/scans/<scan_uuid>", methods=["GET"])
def get_scan(scan_uuid):
    scan = CardScan.query.filter_by(uuid=scan_uuid).first()
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    return jsonify({
        "scan": scan.to_dict(),
        "texts": [t.to_dict() for t in scan.texts],
    })


@app.route("/api/scans/<scan_uuid>", methods=["PATCH"])
def update_scan(scan_uuid):
    scan = CardScan.query.filter_by(uuid=scan_uuid).first()
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    for field in ["industry", "sales_branch", "rating", "city", "state", "gstin", "assigned_to"]:
        if field in data:
            setattr(scan, field, str(data[field]))

    db.session.commit()
    return jsonify({"scan": scan.to_dict()})


@app.route("/api/scans/<scan_uuid>", methods=["DELETE"])
def delete_scan(scan_uuid):
    scan = CardScan.query.filter_by(uuid=scan_uuid).first()
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    img_path = scan.image_path
    vis_path = os.path.join(
        os.path.dirname(img_path),
        "vis_" + os.path.basename(img_path),
    )

    db.session.delete(scan)
    db.session.commit()

    for p in [img_path, vis_path]:
        if os.path.exists(p):
            os.remove(p)

    return jsonify({"message": "Deleted"})


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    scans = CardScan.query.order_by(CardScan.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    header = [
        "Industry", "SalesBranch", "Rating", "City", "State",
        "GSTIN", "AssignedTo", "Createdat", "Updatedat"
    ]
    writer.writerow(header)

    for scan in scans:
        writer.writerow([
            scan.industry or "",
            scan.sales_branch or "",
            scan.rating or "",
            scan.city or "",
            scan.state or "",
            scan.gstin or "",
            scan.assigned_to or "",
            scan.created_at.strftime("%d-%b-%Y %H:%M") if scan.created_at else "",
            scan.updated_at.strftime("%d-%b-%Y %H:%M") if scan.updated_at else "",
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"card_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )


@app.route("/api/clear", methods=["DELETE"])
def clear_all():
    scans = CardScan.query.all()
    for scan in scans:
        img_path = scan.image_path
        vis_path = os.path.join(
            os.path.dirname(img_path),
            "vis_" + os.path.basename(img_path),
        )
        for p in [img_path, vis_path]:
            if os.path.exists(p):
                os.remove(p)
        db.session.delete(scan)
    db.session.commit()
    return jsonify({"message": "All scans cleared"})


if __name__ == "__main__":
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()
    print("=" * 60)
    print("  Card Scanner - PaddleOCR Web App")
    print("=" * 60)
    print(f"  Local:    http://127.0.0.1:5050")
    print(f"  Network:  http://{local_ip}:5050")
    print("")
    print(f"  On your mobile, open http://{local_ip}:5050")
    print(f"  (Connect both devices to the same Wi-Fi)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5050, debug=False)
