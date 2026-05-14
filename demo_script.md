# Kịch Bản Demo Video (Thời lượng mục tiêu: ~2 phút)

Em hãy mở file văn bản này để ở một góc màn hình nhỏ, và mở **trình duyệt web** (ở trang MCP Inspector) cùng với **Terminal** ở phần màn hình chính để tiến hành quay.

---

### Mở đầu (0:00 - 0:15)
- **Hành động:** Hiển thị giao diện terminal.
- **Thuyết minh:** 
  > "Chào mọi người, đây là bài Lab 26 của em - Xây dựng Database MCP Server bằng FastMCP và SQLite. Đầu tiên, em sẽ chạy file test tự động để chứng minh server hoạt động đúng."
- **Thao tác Terminal:** 
  Chạy lệnh `python implementation/verify_server.py` (hoặc `.venv/bin/python implementation/verify_server.py`). Chờ kết quả hiện ra toàn bộ dấu tick xanh (29/29 checks passed).
  > "Như mọi người thấy, tất cả 29 test cases từ happy path đến error validation đều passed."

### Khởi động Inspector & Khám phá Resource (0:15 - 0:40)
- **Hành động:** Chuyển sang trình duyệt đang mở URL của MCP Inspector (`http://localhost:44851` hoặc tương tự).
- **Thuyết minh:** 
  > "Bây giờ em sẽ dùng MCP Inspector để tương tác trực tiếp với Server."
- **Thao tác trình duyệt:** 
  1. Bấm nút **Connect**.
  2. Chuyển sang tab **Resources**. Bấm vào `schema://database` để lấy toàn bộ Database Schema.
  > "Đây là resource `schema://database`, nó trả về toàn bộ schema của các bảng hiện có như courses, enrollments và students, giúp LLM hiểu được cấu trúc DB."

### Demo Tool 1: `search` (0:40 - 1:05)
- **Hành động:** Chuyển sang tab **Tools**.
- **Thuyết minh:** 
  > "Tiếp theo là phần Tools. Em sẽ thử tính năng `search` để tìm các bạn sinh viên thuộc khoá A1 và có điểm lớn hơn 80."
- **Thao tác trình duyệt:** 
  Chọn tool `search`. Điền JSON vào ô Argument (có thể copy/paste nhanh):
  ```json
  {
    "table": "students",
    "filters": {
      "cohort": {"eq": "A1"},
      "score": {"gt": 80}
    },
    "order_by": "score",
    "descending": true
  }
  ```
  Bấm **Run Tool**. Cuộn kết quả cho thấy danh sách trả về kèm pagination metadata (`has_more`, `next_offset`).

### Demo Error Handling & Security (1:05 - 1:30)
- **Hành động:** Vẫn ở tool `search`.
- **Thuyết minh:** 
  > "Server được thiết kế cực kỳ an toàn. Nếu LLM tự bịa ra một cái bảng hoặc một cột không tồn tại, nó sẽ bị chặn ngay lập tức chứ không đưa trực tiếp vào query SQL."
- **Thao tác trình duyệt:**
  Sửa arg `table` thành `"nonexistent_table"` rồi bấm **Run Tool**.
  > "Kết quả trả về lỗi rõ ràng: Unknown table 'nonexistent_table'."
  Sửa arg `table` về `"students"`, nhưng trong filter sửa chữ `"score"` thành `"ghost_column"` rồi bấm **Run Tool**.
  > "Tương tự, lỗi Unknown column sẽ báo ngay lập tức."

### Demo Tool 2: `aggregate` (1:30 - 1:50)
- **Hành động:** Đổi sang tool `aggregate`.
- **Thuyết minh:** 
  > "Cuối cùng, em test tính năng `aggregate` để xem điểm trung bình của sinh viên theo từng khoá."
- **Thao tác trình duyệt:**
  Điền JSON vào ô Argument:
  ```json
  {
    "table": "students",
    "metric": "avg",
    "column": "score",
    "group_by": "cohort"
  }
  ```
  Bấm **Run Tool**. Cho thấy kết quả gộp nhóm rõ ràng (A1, A2, B1...).

### Kết thúc (1:50 - 2:00)
- **Thuyết minh:** 
  > "Ngoài ra server của em cũng đã làm phần Bonus hỗ trợ PostgreSQL backend và SSE Auth Middleware. Cấu hình chi tiết em có để trong file README. Demo của em đến đây là hết, cảm ơn mọi người."
- **Hành động:** Tắt quay màn hình.
