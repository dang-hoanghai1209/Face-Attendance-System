import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import get_current_user, require_admin
from services import report_service


_FONT_CANDIDATES = [
    (
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ),
    (
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/tahomabd.ttf",
    ),
    (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
]


def _register_pdf_fonts():
    for regular_path, bold_path in _FONT_CANDIDATES:
        regular = Path(regular_path)
        bold = Path(bold_path)
        if not regular.exists():
            continue

        try:
            pdfmetrics.registerFont(TTFont("ReportUnicode", str(regular)))
            pdfmetrics.registerFont(TTFont("ReportUnicodeBold", str(bold if bold.exists() else regular)))
            return "ReportUnicode", "ReportUnicodeBold"
        except Exception:
            continue

    return "Helvetica", "Helvetica-Bold"


_PDF_FONT, _PDF_FONT_BOLD = _register_pdf_fonts()

PAGE_W, PAGE_H = A4
MARGIN = 40
BASE_DIR = Path(__file__).resolve().parents[1]
EVALUATION_REPORTS_DIR = BASE_DIR / "reports"
EVALUATION_METRICS_CSV = EVALUATION_REPORTS_DIR / "evaluation_metrics.csv"
EVALUATION_DETAILS_CSV = EVALUATION_REPORTS_DIR / "evaluation_details.csv"
MODEL_TEST_LOG_CSV = EVALUATION_REPORTS_DIR / "model_test_log.csv"
STATUS_LABELS = {
    "present": "Có mặt",
    "late": "Đi trễ",
    "manual": "Thủ công",
    "absent": "Vắng",
}
SUMMARY_COLUMNS = {
    "student_code": "Mã SV",
    "full_name": "Họ tên",
    "class_name": "Lớp",
    "present": "Có mặt",
    "late": "Đi trễ",
    "manual": "Thủ công",
    "absent": "Vắng",
    "attended": "Tổng có mặt",
    "total_sessions": "Tổng buổi",
    "rate": "Tỷ lệ chuyên cần",
    "warning": "Cảnh báo",
}
SESSION_COLUMNS = {
    "student_code": "Mã SV",
    "full_name": "Họ tên",
    "class_name": "Lớp",
    "subject": "Môn học",
    "session_date": "Ngày học",
    "start_time": "Giờ bắt đầu",
    "end_time": "Giờ kết thúc",
    "status": "Trạng thái",
    "check_in_at": "Vào lớp",
    "check_out_at": "Ra về",
    "check_in_conf": "Tin cậy vào",
    "check_out_conf": "Tin cậy ra",
    "note": "Ghi chú",
}

router = APIRouter(prefix="/reports", tags=["Reports"])


def _safe_filename(value: str):
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value).strip("_")


def _new_pdf(stream):
    c = canvas.Canvas(stream, pagesize=A4)
    return c, PAGE_H - MARGIN


def _check_page(c, y, line_h=16, reserve=60):
    if y - line_h < reserve:
        c.showPage()
        c.setFont(_PDF_FONT, 10)
        return PAGE_H - MARGIN
    return y


def _draw_header(c, y, title, subtitle=""):
    c.setFont(_PDF_FONT_BOLD, 13)
    c.drawString(MARGIN, y, title)
    y -= 18
    if subtitle:
        c.setFont(_PDF_FONT, 10)
        c.drawString(MARGIN, y, subtitle)
        y -= 14
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 12
    return y


def _draw_row(c, y, cols, widths, bold=False):
    font = _PDF_FONT_BOLD if bold else _PDF_FONT
    c.setFont(font, 9)
    x = MARGIN
    for text, width in zip(cols, widths):
        c.drawString(x + 2, y, str(text)[: int(width / 5.5)])
        x += width
    return y - 14


def _fmt_dt(iso):
    if not iso:
        return "-"
    try:
        from datetime import datetime

        value = datetime.fromisoformat(str(iso))
        return value.strftime("%d/%m %H:%M")
    except Exception:
        return str(iso)[:16]


def _metric_value(metrics, label, default=0):
    match = metrics.loc[metrics.iloc[:, 0] == label]
    if match.empty:
        return default
    try:
        return float(match.iloc[0, 1])
    except Exception:
        return default


def _format_percent(value):
    try:
        return f"{float(value):.1%}"
    except Exception:
        return "-"


def _format_confidence(value):
    if not isinstance(value, (int, float)):
        return "-"
    return f"{value * 100:.1f}%"


def _format_time_range(start_time, end_time):
    if not start_time and not end_time:
        return "Chưa đặt giờ"
    return f"{start_time or 'Chưa đặt'} - {end_time or 'Chưa đặt'}"


def _summary_export_frame(rows):
    if not rows:
        return pd.DataFrame(columns=list(SUMMARY_COLUMNS.values()))

    normalized = []
    for row in rows:
        item = dict(row)
        item["rate"] = _format_percent(item.get("rate"))
        item["warning"] = "Có" if item.get("warning") else "Không"
        normalized.append(item)
    return pd.DataFrame(normalized).rename(columns=SUMMARY_COLUMNS)


def _session_export_frame(rows):
    normalized = []
    for row in rows:
        item = dict(row)
        item["status"] = STATUS_LABELS.get(item.get("status"), item.get("status"))
        item["start_time"] = item.get("start_time") or "-"
        item["end_time"] = item.get("end_time") or "-"
        item["check_in_at"] = _fmt_dt(item.get("check_in_at"))
        item["check_out_at"] = _fmt_dt(item.get("check_out_at"))
        item["check_in_conf"] = _format_confidence(item.get("check_in_conf"))
        item["check_out_conf"] = _format_confidence(item.get("check_out_conf"))
        normalized.append(item)
    return pd.DataFrame(normalized).rename(columns=SESSION_COLUMNS)


def _format_excel_sheet(worksheet):
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    header_font = Font(name="Arial", bold=True, color="111827")
    body_font = Font(name="Arial", color="111827")

    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = body_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        width = min(max(max_length + 2, 10), 34)
        worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width

    worksheet.freeze_panes = "A2"


@router.get("/dashboard/stats")
def get_dashboard_stats(_current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return report_service.get_dashboard_stats(db)


@router.get("/model-evaluation/stats")
def get_model_evaluation_stats(_current_user=Depends(require_admin)):
    if not EVALUATION_METRICS_CSV.exists() or not EVALUATION_DETAILS_CSV.exists():
        if MODEL_TEST_LOG_CSV.exists():
            try:
                logs = pd.read_csv(MODEL_TEST_LOG_CSV)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Cannot read model test log: {exc}") from exc

            if not logs.empty:
                confidence_values = pd.to_numeric(logs.get("confidence"), errors="coerce")
                confidence_values = confidence_values[confidence_values >= 0]
                avg_confidence = float(confidence_values.mean()) if not confidence_values.empty else 0.0
                processing_values = pd.to_numeric(logs.get("processing_time_ms"), errors="coerce").dropna()
                recognized = logs["status"].isin(["success", "uncertain"]) if "status" in logs else []
                not_recognized = logs["status"].isin(["unknown", "no_face", "multiple_faces"]).sum() if "status" in logs else 0
                return {
                    "has_data": True,
                    "sample_count": int(len(logs)),
                    "recognized_correct": int(recognized.sum()) if hasattr(recognized, "sum") else 0,
                    "recognized_wrong": 0,
                    "not_recognized": int(not_recognized),
                    "accuracy": 0,
                    "average_confidence": round(avg_confidence, 4),
                    "average_processing_time_ms": round(float(processing_values.mean()), 2) if not processing_values.empty else None,
                    "source": "model_test_log",
                }

        return {
            "has_data": False,
            "message": "Chưa có dữ liệu đánh giá mô hình. Hãy sử dụng chức năng Kiểm thử mô hình để tạo kết quả.",
        }

    try:
        metrics = pd.read_csv(EVALUATION_METRICS_CSV)
        details = pd.read_csv(EVALUATION_DETAILS_CSV)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot read evaluation reports: {exc}") from exc

    total_images = int(_metric_value(metrics, "Total images", 0))
    if total_images <= 0 or details.empty:
        return {
            "has_data": False,
            "message": "Chưa có dữ liệu đánh giá mô hình. Hãy sử dụng chức năng Kiểm thử mô hình để tạo kết quả.",
        }

    tp = int(_metric_value(metrics, "TP", 0))
    tn = int(_metric_value(metrics, "TN", 0))
    fp = int(_metric_value(metrics, "FP", 0))
    fn = int(_metric_value(metrics, "FN", 0))
    recognized_correct = tp + tn
    recognized_wrong = fp + fn

    status_series = details["status"] if "status" in details else pd.Series(dtype=str)
    not_recognized = int(status_series.isin(["unknown", "no_face"]).sum())
    avg_confidence = 0.0
    if "confidence" in details:
        confidence_values = pd.to_numeric(details["confidence"], errors="coerce")
        confidence_values = confidence_values[confidence_values >= 0]
        avg_confidence = float(confidence_values.mean()) if not confidence_values.empty else 0.0

    avg_processing_time_ms = None
    for column in ("processing_time_ms", "processing_ms"):
        if column in details:
            values = pd.to_numeric(details[column], errors="coerce").dropna()
            avg_processing_time_ms = float(values.mean()) if not values.empty else None
            break

    return {
        "has_data": True,
        "sample_count": total_images,
        "recognized_correct": recognized_correct,
        "recognized_wrong": recognized_wrong,
        "not_recognized": not_recognized,
        "accuracy": _metric_value(metrics, "Accuracy", 0),
        "average_confidence": round(avg_confidence, 4),
        "average_processing_time_ms": round(avg_processing_time_ms, 2) if avg_processing_time_ms is not None else None,
        "source": "evaluation_csv",
    }


@router.get("/summary/{class_name}")
def get_summary_by_class(class_name: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return report_service.build_class_summary(class_name, db)


@router.get("/warnings/{class_name}")
def get_warnings_by_class(class_name: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    summary = report_service.build_class_summary(class_name, db)
    return [item for item in summary if item["warning"]]


@router.get("/session/{session_id}")
def get_session_report(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _session, report_rows = report_service.build_session_report(session_id, db)
    return report_rows


@router.get("/export/excel/{class_name}")
def export_excel(class_name: str, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    summary = report_service.build_class_summary(class_name, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu trong lớp này.")

    warnings = [item for item in summary if item["warning"]]
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        _summary_export_frame(summary).to_excel(writer, index=False, sheet_name="Tong hop")
        _summary_export_frame(warnings).to_excel(writer, index=False, sheet_name="Canh bao")
        _format_excel_sheet(writer.sheets["Tong hop"])
        _format_excel_sheet(writer.sheets["Canh bao"])
    stream.seek(0)

    filename = _safe_filename(f"attendance_{class_name}") or "attendance_report"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )


@router.get("/export/pdf/{class_name}")
def export_pdf(class_name: str, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    summary = report_service.build_class_summary(class_name, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu trong lớp này.")

    stream = io.BytesIO()
    c, y = _new_pdf(stream)

    title = f"Báo cáo chuyên cần - Lớp {class_name}"
    subtitle = f"Tổng số sinh viên: {len(summary)}  |  Tổng buổi học: {summary[0]['total_sessions']}"
    y = _draw_header(c, y, title, subtitle)

    headers = ["Mã SV", "Họ tên", "Có mặt", "Trễ", "Vắng", "Tổng", "Tỷ lệ", "Cảnh báo"]
    widths = [80, 220, 55, 45, 50, 50, 60, 60]
    y = _draw_row(c, y, headers, widths, bold=True)
    c.setLineWidth(0.3)
    c.line(MARGIN, y + 10, PAGE_W - MARGIN, y + 10)

    for item in summary:
        y = _check_page(c, y)
        cols = [
            item["student_code"],
            item["full_name"],
            item["present"],
            item["late"],
            item["absent"],
            item["total_sessions"],
            f"{item['rate']:.1%}",
            "!" if item["warning"] else "",
        ]
        y = _draw_row(c, y, cols, widths)

    c.save()
    stream.seek(0)

    filename = _safe_filename(f"attendance_{class_name}") or "attendance_report"
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
    )


@router.get("/export/excel/warnings/{class_name}")
def export_warning_excel(class_name: str, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    summary = report_service.build_class_summary(class_name, db)
    if not summary:
        raise HTTPException(status_code=404, detail="No data found for this class.")

    warnings = [item for item in summary if item["warning"]]
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        _summary_export_frame(warnings).to_excel(writer, index=False, sheet_name="Canh bao")
        _format_excel_sheet(writer.sheets["Canh bao"])
    stream.seek(0)

    filename = _safe_filename(f"attendance_warnings_{class_name}") or "attendance_warnings"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )


@router.get("/export/excel/session/{session_id}")
def export_session_excel(session_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    session, rows = report_service.build_session_report(session_id, db)
    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this session.")

    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        _session_export_frame(rows).to_excel(writer, index=False, sheet_name="Bao cao buoi")
        _format_excel_sheet(writer.sheets["Bao cao buoi"])
    stream.seek(0)

    filename = _safe_filename(
        f"attendance_session_{session.id}_{session.class_name}_{session.session_date}"
    ) or f"attendance_session_{session.id}"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )


@router.get("/export/pdf/session/{session_id}")
def export_session_pdf(session_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    session, rows = report_service.build_session_report(session_id, db)
    if not rows:
        raise HTTPException(status_code=404, detail="No data found for this session.")

    stream = io.BytesIO()
    c, y = _new_pdf(stream)

    title = f"Báo cáo buổi học #{session.id} - {session.class_name} - {session.subject}"
    subtitle = (
        f"Ngày: {session.session_date}  |  "
        f"Giờ: {_format_time_range(session.start_time, session.end_time)}  |  "
        f"Sĩ số: {len(rows)}"
    )
    y = _draw_header(c, y, title, subtitle)

    headers = ["Mã SV", "Họ tên", "Trạng thái", "Vào lớp", "Ra về", "Tin cậy"]
    widths = [80, 200, 90, 110, 110, 65]
    y = _draw_row(c, y, headers, widths, bold=True)
    c.setLineWidth(0.3)
    c.line(MARGIN, y + 10, PAGE_W - MARGIN, y + 10)

    present_count = sum(1 for row in rows if row["status"] in ("present", "late", "manual"))
    absent_count = sum(1 for row in rows if row["status"] == "absent")

    for item in rows:
        y = _check_page(c, y)
        confidence = item.get("check_in_conf")
        confidence_text = f"{confidence * 100:.1f}%" if isinstance(confidence, float) else "-"
        cols = [
            item["student_code"],
            item["full_name"],
            STATUS_LABELS.get(item["status"], item["status"]),
            _fmt_dt(item.get("check_in_at")),
            _fmt_dt(item.get("check_out_at")),
            confidence_text,
        ]
        y = _draw_row(c, y, cols, widths)

    y = _check_page(c, y, reserve=40)
    y -= 8
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 14
    c.setFont(_PDF_FONT_BOLD, 9)
    c.drawString(MARGIN, y, f"Có mặt: {present_count}   Vắng: {absent_count}   Tổng: {len(rows)}")

    c.save()
    stream.seek(0)

    filename = _safe_filename(
        f"attendance_session_{session.id}_{session.class_name}_{session.session_date}"
    ) or f"attendance_session_{session.id}"
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
    )
