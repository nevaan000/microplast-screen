from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..config import DISCLAIMER, config
from .common import response_for_sample

router = APIRouter(prefix="/api", tags=["exports"])


def _result(sample_id: int) -> dict:
    result = response_for_sample(sample_id)
    if result["analysis"] is None:
        raise HTTPException(status_code=409, detail="The sample has no analysis to export")
    return result


@router.get("/export/{sample_id}.csv")
def export_csv(sample_id: int):
    result = _result(sample_id)
    output = io.StringIO()
    output.write(f"# Disclaimer: {DISCLAIMER}\n")
    rows = result["analysis"]["particles"]
    fieldnames = [
        "id", "idx", "shape_class", "label", "confidence", "length_mm", "width_mm", "area_mm2", "length_px", "width_px",
        "aspect_ratio", "circularity", "solidity", "color_name", "texture_std", "user_verified_class",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="sample-{sample_id}-particles.csv"'})


@router.get("/export/{sample_id}.json")
def export_json(sample_id: int):
    result = _result(sample_id)
    data = {"disclaimer": DISCLAIMER, **result}
    return Response(json.dumps(data, indent=2, default=str), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="sample-{sample_id}.json"'})


@router.get("/export/{sample_id}.pdf")
def export_pdf(sample_id: int):
    result = _result(sample_id)
    sample, analysis = result["sample"], result["analysis"]
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("MicroPlast Screen — Visual Screening Report", styles["Title"]), Spacer(1, 6 * mm)]
    story.append(Paragraph(DISCLAIMER, styles["BodyText"]))
    story.append(Spacer(1, 5 * mm))
    metadata = [["Sample", sample["name"]], ["Location", sample.get("location") or "—"], ["Created", sample["created_at"]], ["Suspected plastic", str(analysis["suspected_plastic"])], ["Total particles", str(analysis["total_particles"])], ["Concentration", f"{analysis['concentration_per_l'] or '—'} per L"]]
    table = Table(metadata, colWidths=[45 * mm, 125 * mm])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#9ab")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e7f5f5")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [table, Spacer(1, 5 * mm)]
    image_path = config.root_dir / analysis["annotated_path"]
    if image_path.exists():
        story.append(Image(str(image_path), width=175 * mm, height=131 * mm, kind="proportional"))
        story.append(Spacer(1, 5 * mm))
    records = [["ID", "Class", "Label", "Length", "Colour", "Confidence"]]
    for particle in analysis["particles"][:35]:
        length = f"{particle['length_mm']:.3f} mm" if particle["length_mm"] is not None else f"{particle['length_px']:.1f} px"
        records.append([str(particle["idx"]), particle["shape_class"], particle["label"], length, particle["color_name"], f"{particle['confidence'] * 100:.0f}%"])
    records_table = Table(records, repeatRows=1, colWidths=[12 * mm, 28 * mm, 37 * mm, 31 * mm, 28 * mm, 25 * mm])
    records_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#bbc")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b7285")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(records_table)
    document.build(story)
    return Response(output.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="sample-{sample_id}-report.pdf"'})
