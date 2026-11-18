"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def _clip_box_line(text):
    try:
        class_id, cx, cy, w, h = parse_yolo_line(text)
    except (ValueError, OverflowError):
        return None

    left, right = cx - w / 2, cx + w / 2
    top, bottom = cy - h / 2, cy + h / 2
    if right <= left or bottom <= top:
        return None
    if 0 <= left and right <= 1 and 0 <= top and bottom <= 1:
        return text

    left, right = max(0.0, left), min(1.0, right)
    top, bottom = max(0.0, top), min(1.0, bottom)
    if right <= left or bottom <= top:
        return None

    new_cx = (left + right) / 2
    new_cy = (top + bottom) / 2
    return f"{class_id} {new_cx} {new_cy} {right - left} {bottom - top}"


def fix(ds, issues, cfg):
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    removals = set()
    missing_labels = set()
    rename_classes = False
    line_codes = defaultdict(lambda: defaultdict(set))

    for issue in issues:
        if issue.severity != ERROR:
            continue
        code = issue.code
        if code in remove_codes or code.startswith("DUP_IMAGE_"):
            removals.add(issue.image)
        elif code == "BAD_CLASS_NAME":
            rename_classes = True
        elif code == "MISSING_LABEL_FILE":
            missing_labels.add(issue.image)
        elif issue.line is not None and (code in drop_codes or code == "BOX_OUT_OF_IMAGE"):
            line_codes[issue.image][issue.line].add(code)

    fixes = []
    images = defaultdict(list)
    for path in ds.image_files():
        images[path.stem].append(path)
    labels = {path.stem: path for path in ds.label_files()}

    for stem in sorted(removals):
        paths = list(images.get(stem, []))
        if stem in labels:
            paths.append(labels[stem])
        if paths:
            for path in paths:
                path.unlink(missing_ok=True)
            fixes.append(dict(
                image=stem, line=None, action="remove_image",
                before=", ".join(path.name for path in paths), after="",
            ))

    if rename_classes:
        path = ds.yaml_path
        contents = path.read_text(encoding="utf-8") if path.exists() else ""
        data = yaml.safe_load(contents) or {}
        old_names = data.get("names")
        new_names = list(cfg["classes"])
        if old_names != new_names and old_names != dict(enumerate(new_names)):
            data["names"] = new_names
            path.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            fixes.append(dict(
                image=path.name, line=None, action="rename_classes",
                before=str(old_names), after=str(new_names),
            ))

    for stem in sorted(line_codes.keys() - removals):
        path = labels.get(stem)
        if path is None:
            continue

        before_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        after_lines = []
        for line_no, before in enumerate(before_lines, 1):
            codes = line_codes[stem].get(line_no, set())
            if codes & drop_codes:
                after = None
            elif "BOX_OUT_OF_IMAGE" in codes:
                after = _clip_box_line(before)
            else:
                after = before

            if after is not None:
                after_lines.append(after)
            if after != before:
                fixes.append(dict(
                    image=stem, line=line_no,
                    action="drop_line" if after is None else "clip_box",
                    before=before, after=after if after is not None else "",
                ))

        if after_lines != before_lines:
            new_text = "\n".join(after_lines) + ("\n" if after_lines else "")
            path.write_text(new_text, encoding="utf-8")

    for stem in sorted(missing_labels - removals):
        if stem in images and stem not in labels:
            fixes.append(dict(
                image=stem, line=None, action="needs_label",
                before="(không có file)", after="chuyển người gán",
            ))

    return fixes
