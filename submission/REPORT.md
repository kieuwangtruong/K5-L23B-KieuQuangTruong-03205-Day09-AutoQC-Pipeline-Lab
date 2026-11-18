# Báo cáo Day 09 — Kiều Quang Trường, 03205

## 1. Kết luận trước
**Hold.** Pipeline nhận 224 ảnh raw, loại 19 ảnh ở cửa vào, giữ và xuất bản nháp `clean_v1` gồm 205 ảnh. Sau khi mô phỏng duyệt 80/125 ảnh trong hàng đợi, còn 0 lỗi bắt buộc và 38/205 ảnh có cảnh báo chưa duyệt (18.54%), vượt ngưỡng Hold 10%.

## 2. Lỗi và phân việc
`02_error_list_v1.csv` ghi 55 lỗi bắt buộc và 153 cảnh báo. Trong đó, 19 lỗi ảnh được chặn khi nhập lô, còn 36 lỗi bắt buộc và 153 cảnh báo được phát hiện khi QC 205 ảnh đã nhận. Các lỗi theo dòng dùng mẫu số 675 dòng nhãn có nội dung trong 199 file nhãn của lô này.

| Mã lỗi | Số lượng / mẫu số | Ai xử lý và vì sao |
|---|---:|---|
| `CORRUPT_IMAGE` | 2/224 ảnh | Máy loại ảnh không giải mã được. |
| `BAD_SIZE` | 3/224 ảnh | Máy loại ảnh dưới ngưỡng kích thước. |
| `DUP_IMAGE_EXACT` | 8/224 ảnh | Máy loại bản trùng byte. |
| `DUP_IMAGE_NEAR` | 2/224 ảnh | Máy loại ảnh gần trùng theo pHash. |
| `LEAK_TEST` | 4/224 ảnh | Máy loại ảnh trùng kho test/val. |
| `MISSING_LABEL_FILE` | 6/205 ảnh | Người gán nhãn và xác nhận nội dung. |
| `BAD_CLASS_NAME` | 2/4 tên lớp | Máy ghi lại tên lớp theo cấu hình. |
| `BAD_FORMAT` | 3/675 dòng | Máy bỏ dòng sai định dạng YOLO. |
| `BAD_CLASS_ID` | 6/675 dòng | Máy bỏ dòng có ID ngoài danh sách lớp. |
| `BOX_ZERO` | 4/675 dòng | Máy bỏ box có chiều rộng hoặc chiều cao bằng 0 hoặc âm. |
| `BOX_OUT_OF_IMAGE` | 8/675 dòng | Máy cắt box về biên ảnh. |
| `DUP_BOX` | 7/675 dòng | Máy bỏ dòng box trùng cùng lớp xuất hiện sau. |
| `EMPTY_LABEL` | 12/199 file | Người phân biệt ảnh nền với ảnh bị thiếu box. |
| `BOX_TINY` | 6/675 dòng | Người xác nhận box nhỏ có cần giữ. |
| `BOX_HUGE` | 3/675 dòng | Người kiểm tra box phủ phần lớn ảnh. |
| `CLASS_RARE` | 4/8 token lớp | Người kiểm tra phân bố và đối chiếu ID sai. |
| `POSSIBLE_MISSING` | 53 cờ/205 ảnh | Người xác nhận có vật thể bị thiếu nhãn. |
| `POSSIBLE_WRONG_CLASS` | 18 cờ/205 ảnh | Người quyết định lớp đúng. |
| `POSSIBLE_LOOSE_BOX` | 28 cờ/205 ảnh | Người kiểm tra box có ôm sát vật. |
| `POSSIBLE_FALSE_POS` | 29 cờ/675 dòng | Người xác nhận box có tương ứng với vật thật. |

`03_fixes.csv` ghi 20 dòng bị bỏ, 8 box được cắt, 1 lần ghi lại tên lớp và 6 lượt chuyển người gán nhãn. Ba ca có thể đối chiếu trực tiếp là `img_0001:3` có box trùng, `img_0030:9` có box tràn mép trái và `img_0031` thiếu file nhãn.

`img_0020` đứng đầu hàng đợi với điểm 11.524 do cộng điểm từ dòng đã bỏ và các cảnh báo thiếu box, sai lớp có trọng số theo độ tin cậy. Sáu ảnh thiếu file nhãn cũng được ưu tiên với điểm 10 và đều được duyệt. Trong 80 ảnh được duyệt, 74 ảnh có cảnh báo ngữ nghĩa, bao phủ 94/123 cờ ngữ nghĩa của vòng 2. Đây là số cờ được đưa ra xem xét.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 4 | Gần trùng `1.000 / 0.500` → `1.000 / 0.667` | Bắt 4/6 ca gần trùng, tăng từ 3/6, với 0 cờ nhầm trên calib. Mức 4 là ngưỡng nhỏ nhất trong sweep bắt được 4 ca. |
| `second_opinion.conf` | 0.25 | 0.60 | Thiếu box `0.500 / 1.000` → `0.571 / 1.000`.<br>Sai lớp `0.556 / 0.833` → `0.625 / 0.833`.<br>Box lỏng `0.286 / 0.400` → `0.200 / 0.200`. | Cờ nhầm của hai nhóm thiếu box và sai lớp giảm từ 12 xuống 9, đồng thời vẫn bắt 8/8 ca thiếu box và 5/6 ca sai lớp. Đổi lại, số ca box lỏng bắt được giảm từ 2/5 xuống 1/5. |

Bộ calib có 39 ảnh, gồm 6 ca gần trùng chèn sẵn. Tăng pHash từ 2 lên 4 giúp bắt thêm một ca trên calib. Khi chỉ so các ảnh trong lô raw với nhau, cả hai mức đều gắn cờ gần trùng cho 2/224 ảnh. Ở ngưỡng 20, con số tăng lên 77/224 ảnh. Ví dụ, cặp `img_0015` và `img_0009` được gắn cờ ở mức 20, với chênh lệch RGB tuyệt đối trung bình 58.32/255 sau khi đưa về cùng kích thước 128 × 128. Các cặp trong raw cần được xem lại để xác nhận, vì precision trên bộ calib chỉ đo các ca trong bộ đó.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**Thử cửa chặn với ngân sách duyệt 0 ảnh.** Lượt thử dùng cùng cấu hình và ghi kết quả riêng trong `work/step4-budget0/`. Sau bước sửa tự động còn 6/205 ảnh mắc lỗi `MISSING_LABEL_FILE`. Gate trả **Rework**, mã thoát **20**, trường `exported` là `null` và thư mục `export/clean_v1/` của lượt thử vắng mặt.

```powershell
python -m pipeline.run --budget 0 --work work/step4-budget0/run --reports work/step4-budget0/reports --export-dir work/step4-budget0/export
```

**Hai điểm mù đo được trên bộ calib.**

- **Ảnh gần trùng bị biến đổi mạnh.** Ngưỡng pHash 4 bỏ sót 2/6 ca gần trùng. Cặp `calib_037` / `calib_015` có khoảng cách 16 và cặp `calib_038` / `calib_024` có khoảng cách 18, đều vượt ngưỡng.
- **Box lỏng.** Với ngưỡng `conf = 0.60`, chỉ 1/5 ca chèn sẵn nhận cảnh báo `POSSIBLE_LOOSE_BOX`. Ví dụ, `calib_006` có box được phóng theo hệ số 1.48 và không nhận cảnh báo này.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Bài nộp ưu tiên hoàn thành phần lõi QC và cửa chặn trước khi thực hiện thí nghiệm train.

## 6. Quyết định và ghi chú AI
Giữ quyết định **Hold** cho lô hiện tại. Với 205 ảnh, Release yêu cầu 0 lỗi bắt buộc và tối đa 20 ảnh có cảnh báo chưa duyệt. Cần xử lý thêm ít nhất 18/38 ảnh hiện còn cảnh báo rồi chạy QC lại trước khi phát hành.

- **Prompt chính.** Nhờ Codex hướng dẫn và cung cấp mẫu cho bốn module dựa trên docstring và các ca test trong repo.
- **Cách kiểm.** Chạy unit test, kiểm thử tích hợp, đối chiếu các ca chèn sẵn trên calib và thử gate với ngân sách duyệt 0.
- **Một lần AI sai.** Lượt thử đầu của mẫu `label_format` thiếu import `parse_yolo_line` trong đoạn kiểm thử tách rời và báo `NameError`. AI chạy lại trong module có sẵn các import, qua 14/14 test của module.
