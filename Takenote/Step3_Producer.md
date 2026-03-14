

---
### **Step 3: Python Producer (Binance → Kafka)**

#### **3.1 Cài đặt môi trường & Dependencies**

* **File `producer/requirements.txt**`: Khai báo các thư viện cần thiết.
* `confluent-kafka`: Thư viện chuẩn để làm việc với Kafka (dựa trên bộ thư viện C `librdkafka` cực nhanh).
* `websockets`: Dùng để kết nối lấy dữ liệu real-time từ sàn Binance.
* `python-dotenv`: Quản lý biến môi trường (config).



#### **3.2 Đóng gói với Docker**

* **File `producer/Dockerfile**`: Định nghĩa môi trường chạy ứng dụng.
* Sử dụng `python:3.12-slim` để tối ưu dung lượng image.
* `WORKDIR /app`: Tạo thư mục làm việc trong container.



#### **3.3 Logic xử lý chính (`producer.py`)**

Đoạn mã này thực hiện 3 nhiệm vụ: Kết nối WebSocket $\rightarrow$ Chuẩn hóa dữ liệu $\rightarrow$ Đẩy vào Kafka.

**Giải thích thuật ngữ:**

* **WebSocket**: Giao thức truyền dữ liệu hai chiều liên tục (khác với HTTP là yêu cầu-phản hồi), giúp nhận giá coin ngay khi có biến động.
* **Producer**: Thành phần gửi dữ liệu vào Kafka.
* **Bootstrap Servers**: Danh sách các địa chỉ (IP:Port) của Kafka broker để Producer kết nối ban đầu.
* **Topic**: "Thùng chứa" dữ liệu trong Kafka, ở đây là `crypto-prices`.
* **Acks (Acknowledgements)**: Cơ chế xác nhận. `acks=all` nghĩa là đảm bảo dữ liệu đã được ghi an toàn vào tất cả các bản sao trước khi báo thành công.

> 🔎 **Insight**: Việc sử dụng `producer.poll(0)` và `producer.flush()` là cực kỳ quan trọng trong lập trình Kafka. `poll(0)` giúp kích hoạt các callback (như báo lỗi) mà không làm nghẽn luồng nhận dữ liệu từ WebSocket, trong khi `flush()` đảm bảo không còn tin nhắn nào kẹt trong bộ nhớ đệm trước khi đóng chương trình.

#### **3.4 Kết nối hạ tầng (`docker-compose.yml`)**

Thêm service `producer` vào hệ thống.

* `depends_on`: Đảm bảo Kafka phải "khỏe mạnh" (`service_healthy`) thì Producer mới khởi động. Điều này tránh lỗi kết nối thất bại khi hạ tầng chưa sẵn sàng.

---

## 2. Nội dung ghi vào vở (Tư duy & Logic)

Trong vở, bạn không nên chép code. Hãy vẽ hình và ghi chú những từ khóa "sống còn" để hiểu cách các mảnh ghép liên kết với nhau.

### **Sơ đồ luồng dữ liệu (Data Flow)**

`Binance API` $\xrightarrow{WebSocket}$ `Python Producer` $\xrightarrow{Kafka Protocol}$ `Kafka Broker (Topic)`

### **Các ý chính cần nhớ:**

1. **Tại sao dùng Kafka ở giữa?**
* Để "đệm" dữ liệu. Nếu database (TimescaleDB) bị chậm, Kafka sẽ giữ hộ dữ liệu, Producer không bị treo.
* Tách biệt nguồn dữ liệu (Source) và nơi tiêu thụ (Sink).


2. **Logic của file Producer:**
* **Vòng lặp vô hạn (`async for`):** Duy trì kết nối liên tục. Nếu mất kết nối, phải có cơ chế `try...except` để tự động kết nối lại (Resilience).
* **Định dạng JSON:** Dữ liệu từ Binance về rất thô, ta phải lọc lại những trường cần thiết (price, symbol, quantity) trước khi gửi đi để tiết kiệm băng thông.


3. **Tại sao lại cần Dockerfile & Docker-compose?**
* **Dockerfile:** "Công thức nấu ăn" (Cài OS gì, cài thư viện gì).
* **Docker-compose:** "Người điều phối" (Gắn dây mạng giữa các container, quy định thứ tự khởi động).



---
