import csv
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from database import SessionLocal
from face_service import (
    ENABLE_LEGACY_EMBEDDINGS,
    fetch_db_embeddings,
    image_bytes_to_embedding,
    load_legacy_embeddings,
    match_embedding,
)


EVALUATION_DIR = BASE_DIR / "evaluation_data"
KNOWN_DIR = EVALUATION_DIR / "known"
UNKNOWN_DIR = EVALUATION_DIR / "unknown"
REPORTS_DIR = BASE_DIR / "reports"
LEGACY_DB_PATH = BASE_DIR / "data" / "embedding_db.pkl"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def safe_divide(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def list_images(directory):
    if not directory.exists():
        return []

    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def recognize_image(image_path, db_embeddings, legacy_embeddings):
    image_bytes = image_path.read_bytes()
    embedding = image_bytes_to_embedding(image_bytes)

    if embedding is None:
        return {
            "status": "no_face",
            "student_code": None,
            "confidence": -1.0,
        }

    status, student_code, confidence = match_embedding(
        embedding,
        db_embeddings,
        legacy_embeddings=legacy_embeddings,
        include_legacy=ENABLE_LEGACY_EMBEDDINGS,
    )

    return {
        "status": status,
        "student_code": None if student_code == "Unknown" else student_code,
        "confidence": confidence,
    }


def evaluate_known_images(db_embeddings, legacy_embeddings):
    rows = []
    counters = {"tp": 0, "fn": 0}

    if not KNOWN_DIR.exists():
        return rows, counters

    for student_dir in sorted(path for path in KNOWN_DIR.iterdir() if path.is_dir()):
        label = student_dir.name
        for image_path in list_images(student_dir):
            result = recognize_image(image_path, db_embeddings, legacy_embeddings)
            predicted_code = result["student_code"]
            is_tp = result["status"] == "success" and predicted_code == label
            outcome = "TP" if is_tp else "FN"
            counters["tp" if is_tp else "fn"] += 1

            rows.append(
                {
                    "dataset_type": "known",
                    "image_path": str(image_path.relative_to(BASE_DIR)),
                    "true_label": label,
                    "predicted_student_code": predicted_code or "",
                    "status": result["status"],
                    "confidence": result["confidence"],
                    "confidence_percent": detail_confidence_percent(result["confidence"]),
                    "result": outcome,
                }
            )

    return rows, counters


def evaluate_unknown_images(db_embeddings, legacy_embeddings):
    rows = []
    counters = {"tn": 0, "fp": 0, "uncertain_unknown": 0}

    for image_path in list_images(UNKNOWN_DIR):
        result = recognize_image(image_path, db_embeddings, legacy_embeddings)
        predicted_code = result["student_code"]

        if result["status"] == "success":
            outcome = "FP"
            counters["fp"] += 1
        else:
            outcome = "TN"
            counters["tn"] += 1
            if result["status"] == "uncertain":
                counters["uncertain_unknown"] += 1

        rows.append(
            {
                "dataset_type": "unknown",
                "image_path": str(image_path.relative_to(BASE_DIR)),
                "true_label": "unknown",
                "predicted_student_code": predicted_code or "",
                "status": result["status"],
                "confidence": result["confidence"],
                "confidence_percent": detail_confidence_percent(result["confidence"]),
                "result": outcome,
            }
        )

    return rows, counters


def calculate_metrics(tp, tn, fp, fn):
    total = tp + tn + fp + fn
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    return {
        "total_images": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": safe_divide(tp + tn, total),
        "precision": precision,
        "recall": recall,
        "f1_score": safe_divide(2 * precision * recall, precision + recall),
        "far": safe_divide(fp, fp + tn),
        "frr": safe_divide(fn, fn + tp),
    }


def metric_rows(metrics):
    return [
        ("Total images", metrics["total_images"]),
        ("TP", metrics["tp"]),
        ("TN", metrics["tn"]),
        ("FP", metrics["fp"]),
        ("FN", metrics["fn"]),
        ("Accuracy", metrics["accuracy"]),
        ("Precision", metrics["precision"]),
        ("Recall", metrics["recall"]),
        ("F1-score", metrics["f1_score"]),
        ("FAR", metrics["far"]),
        ("FRR", metrics["frr"]),
    ]


def write_metrics_csv(metrics):
    output_path = REPORTS_DIR / "evaluation_metrics.csv"
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Chỉ số", "Giá trị"])
        for label, value in metric_rows(metrics):
            writer.writerow([label, value])


def write_details_csv(rows):
    output_path = REPORTS_DIR / "evaluation_details.csv"
    fieldnames = [
        "dataset_type",
        "image_path",
        "true_label",
        "predicted_student_code",
        "status",
        "confidence",
        "confidence_percent",
        "result",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def percent_text(value):
    return f"{value * 100:.2f}%"


def detail_confidence_percent(value):
    if value < 0:
        return "0%"
    return percent_text(value)


def format_metric_value(label, value):
    if label in {"Accuracy", "Precision", "Recall", "F1-score", "FAR", "FRR"}:
        return percent_text(value)
    return str(value)


def save_evaluation_summary(metrics):
    rows = [[label, format_metric_value(label, value)] for label, value in metric_rows(metrics)]

    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=180)
    fig.patch.set_facecolor("white")
    ax.axis("off")
    ax.set_title(
        "Bảng chỉ số đánh giá pipeline nhận dạng khuôn mặt",
        fontsize=17,
        fontweight="bold",
        pad=22,
    )

    table = ax.table(
        cellText=rows,
        colLabels=["Chỉ số", "Giá trị"],
        colLoc="center",
        cellLoc="center",
        colWidths=[0.56, 0.32],
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.65)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d9e2ec")
        cell.set_linewidth(1.0)
        if row == 0:
            cell.set_facecolor("#0f766e")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f8fafc")
            if col == 0:
                cell.set_text_props(weight="bold", color="#172033")
            else:
                cell.set_text_props(color="#172033")

    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "evaluation_summary.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_confusion_matrix(metrics):
    matrix = [
        [metrics["tp"], metrics["fn"]],
        [metrics["fp"], metrics["tn"]],
    ]
    row_labels = ["Thực tế hợp lệ", "Thực tế không hợp lệ"]
    col_labels = ["Dự đoán hợp lệ", "Dự đoán không hợp lệ"]

    fig, ax = plt.subplots(figsize=(8.8, 6.8), dpi=180)
    fig.patch.set_facecolor("white")
    image = ax.imshow(matrix, cmap="Blues", vmin=0)

    ax.set_title(
        "Ma trận nhầm lẫn của kết quả nhận dạng khuôn mặt",
        fontsize=16,
        fontweight="bold",
        pad=22,
    )
    ax.set_xticks(range(2), labels=col_labels, fontsize=11)
    ax.set_yticks(range(2), labels=row_labels, fontsize=11)
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    max_value = max(max(row) for row in matrix) if matrix else 0
    threshold = max_value / 2 if max_value else 0
    cell_names = [["TP", "FN"], ["FP", "TN"]]
    for row_index in range(2):
        for col_index in range(2):
            value = matrix[row_index][col_index]
            text_color = "white" if value > threshold else "#172033"
            ax.text(
                col_index,
                row_index,
                f"{cell_names[row_index][col_index]}\n{value}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=24,
                fontweight="bold",
            )

    for edge in ax.spines.values():
        edge.set_visible(False)

    ax.set_xticks([0.5], minor=True)
    ax.set_yticks([0.5], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=4)
    ax.tick_params(which="minor", bottom=False, left=False)

    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.ax.tick_params(labelsize=10)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        db_embeddings = fetch_db_embeddings(db)
    finally:
        db.close()

    legacy_embeddings = load_legacy_embeddings(LEGACY_DB_PATH) if ENABLE_LEGACY_EMBEDDINGS else {}

    known_rows, known_counters = evaluate_known_images(db_embeddings, legacy_embeddings)
    unknown_rows, unknown_counters = evaluate_unknown_images(db_embeddings, legacy_embeddings)

    tp = known_counters["tp"]
    fn = known_counters["fn"]
    tn = unknown_counters["tn"]
    fp = unknown_counters["fp"]
    uncertain_unknown = unknown_counters["uncertain_unknown"]

    metrics = calculate_metrics(tp, tn, fp, fn)
    detail_rows = known_rows + unknown_rows
    status_counts = Counter(row["status"] for row in detail_rows)

    write_metrics_csv(metrics)
    write_details_csv(detail_rows)
    save_evaluation_summary(metrics)
    save_confusion_matrix(metrics)

    if metrics["total_images"] == 0:
        print("Warning: no test images found in backend/evaluation_data.")

    print("Evaluation completed.")
    print(f"Total images: {metrics['total_images']}")
    print(f"TP={tp}, TN={tn}, FP={fp}, FN={fn}")
    print(f"Accuracy={percent_text(metrics['accuracy'])}")
    print(f"Precision={percent_text(metrics['precision'])}")
    print(f"Recall={percent_text(metrics['recall'])}")
    print(f"F1-score={percent_text(metrics['f1_score'])}")
    print(f"FAR={percent_text(metrics['far'])}")
    print(f"FRR={percent_text(metrics['frr'])}")
    print("Status counts:")
    for status in ["success", "uncertain", "unknown", "no_face"]:
        print(f"{status}={status_counts[status]}")
    print(f"Reports saved to: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
