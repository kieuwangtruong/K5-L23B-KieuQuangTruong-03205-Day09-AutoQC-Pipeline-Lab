"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    n_images = len(image_stems)
    n_errors = sum(1 for issue in issues if issue.severity == ERROR)

    unreviewed_images = set(image_stems).difference(reviewed)
    warn_images = {
        issue.image
        for issue in issues
        if issue.severity == WARN and issue.image in unreviewed_images
    }
    n_warn_images = len(warn_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0
    hold_threshold = cfg["gate"]["warn_ratio_hold"]

    if n_errors > 0:
        decision = "Rework"
        reason = f"Còn {n_errors} lỗi bắt buộc cần sửa."
    elif warn_ratio >= hold_threshold:
        decision = "Hold"
        reason = (
            f"Còn {n_warn_images}/{n_images} ảnh có cảnh báo chưa duyệt, "
            f"đạt ngưỡng Hold {hold_threshold:.2%}."
        )
    else:
        decision = "Release"
        reason = (
            f"Còn {n_warn_images} ảnh có cảnh báo chưa duyệt trên tổng số "
            f"{n_images} ảnh, dưới ngưỡng Hold {hold_threshold:.2%}."
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": [reason],
    }
