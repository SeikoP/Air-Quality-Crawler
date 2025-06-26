# 🌍 Air Quality Monitoring System

## 📌 Giới thiệu

Hệ thống này thực hiện thu thập dữ liệu chất lượng không khí từ các nguồn như **IQAir**, **WAQI**, và **OpenWeatherMap**, làm sạch và chuyển đổi dữ liệu, sau đó cung cấp API thời gian thực để phục vụ trình bày dữ liệu qua Power BI hoặc các dashboard tương tác.

## 🧱 Cấu trúc dự án

```
├── data_crawler.py       # Thu thập dữ liệu từ nhiều API/web
├── clean_data.py         # Làm sạch, chuẩn hóa, lưu vào DB, Google Drive
├── api.py                # Cung cấp các API FastAPI để truy xuất dữ liệu
├── .env.example          # Mẫu biến môi trường (không chứa thông tin nhạy cảm)
├── requirements.txt      # Danh sách thư viện cần cài đặt
└── README.md             # Tài liệu này
```

## ⚠️ Lưu ý bảo mật khi public lên GitHub

- **KHÔNG commit file `.env` thật, file chứa API key, mật khẩu, token, hoặc file dữ liệu cá nhân.**
- **KHÔNG commit file `credentials_oauth.json`, `token_drive.pkl`, hoặc bất kỳ file nào chứa thông tin xác thực.**
- **Chỉ commit file `.env.example` với các biến môi trường mẫu, không có giá trị thực.**
- **Kiểm tra `.gitignore` đã loại trừ các file/thư mục nhạy cảm.**

## ⚙️ Các chức năng chính

### 1. **Thu thập dữ liệu - `data_crawler.py`**
- Crawl dữ liệu từ các nguồn:
  - 🌫️ [IQAir](https://www.iqair.com/)
  - 💨 [WAQI](https://waqi.info/)
  - 🌦️ [OpenWeatherMap](https://openweathermap.org/)
- Hỗ trợ crawl đa luồng, retry, logging chi tiết.

### 2. **Làm sạch và chuẩn hóa - `clean_data.py`**
- Làm sạch dữ liệu, xử lý NaN, normalize thông tin thời tiết.
- Tách bảng `City`, `Source`, `WeatherCondition`, `AirQualityRecord`.
- Lưu vào PostgreSQL và CSV.
- Tích hợp upload Google Drive theo folder.

### 3. **API FastAPI - `api.py`**
Các endpoint nổi bật:
| Endpoint | Chức năng |
|---------|-----------|
| `/` | Dashboard HTML demo |
| `/air-quality` | Lấy 100 bản ghi mới nhất |
| `/kpi-summary` | Tóm tắt AQI trung bình, PM2.5 trung bình |
| `/cities` | Danh sách city_id |
| `/province-summary` | AQI trung bình theo tỉnh |
| `/time-series?city_id=X` | Dữ liệu chuỗi thời gian |
| `/map-data` | Dữ liệu bản đồ các thành phố |
| `/source-breakdown` | Số bản ghi theo nguồn dữ liệu |
| `/filter?...` | API filter theo `city_id`, `source_id`, `timestamp` |
| `/calculation-tab` | Trung bình/ngày theo thành phố |
| `/latest-by-city` | Bản ghi mới nhất của từng thành phố |

## 🏁 Hướng dẫn chạy

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường

- **Tạo file `.env` từ mẫu `.env.example` và điền thông tin phù hợp (KHÔNG commit file `.env` thật lên GitHub):**
```env
DATABASE_URL=postgresql+psycopg2://user:pass@host:port/db
OPENWEATHER_API_KEY=your_key
WAQI_TOKEN=your_token
IQAIR_API_KEY=your_key
# ...other keys...
```

### 3. Chạy crawler
```bash
python data_crawler.py
```

### 4. Làm sạch & lưu vào DB + Drive
```bash
python clean_data.py
```

### 5. Chạy API
```bash
uvicorn api:app --reload --port 8000
```

## 🐳 Triển khai Docker & Tích hợp n8n

### 1. Build & Run với Docker

- **Tạo file `.env` ở thư mục `Source` (nếu chưa có).**
- **Lưu ý:** Đảm bảo các API key như `IQAIR_API_KEY`, `OPENWEATHER_API_KEY` đã được điền trong `.env` để crawler hoạt động đầy đủ.
- **Build image cho từng service:**
  ```bash
  # Ví dụ cho data_crawler
  docker build -t air-crawler -f Dockerfile.crawler .
  # Ví dụ cho data_cleaner
  docker build -t air-cleaner -f Dockerfile.cleaner .
  # Ví dụ cho API
  docker build -t air-api -f Dockerfile.api .
  ```
- **Chạy container với biến môi trường và mount volume để lưu dữ liệu ra ngoài (nếu cần):**
  ```bash
  docker run --env-file .env -v $(pwd)/data:/app/data air-crawler
  ```
  > **Lưu ý:** Mount volume để lấy dữ liệu CSV ra ngoài container, ví dụ: `-v $(pwd)/data:/app/data` (Linux/macOS) hoặc `-v %cd%\data:/app/data` (Windows).

- **Khuyến nghị dùng Docker Compose để chạy nhiều service:**
  ```yaml
  version: '3.8'
  services:
    crawler:
      build:
        context: .
        dockerfile: Dockerfile.crawler
      env_file: .env
      restart: unless-stopped

    cleaner:
      build:
        context: .
        dockerfile: Dockerfile.cleaner
      env_file: .env
      restart: unless-stopped

    api:
      build:
        context: .
        dockerfile: Dockerfile.api
      env_file: .env
      ports:
        - "8000:8000"
      restart: unless-stopped

    db:
      image: postgres:14
      environment:
        POSTGRES_DB: air_quality_db
        POSTGRES_USER: postgres
        POSTGRES_PASSWORD: pass
      ports:
        - "5432:5432"
      volumes:
        - pgdata:/var/lib/postgresql/data

  volumes:
    pgdata:
  ```

### 2. Tích hợp với n8n

- **Gợi ý flow n8n:**
  1. **HTTP Request**: Gọi endpoint `/run_optimized_crawl` của crawler (POST).
     - Nếu cần truyền API key động (ví dụ IQAIR_API_KEY), truyền trong body JSON:
       ```json
       {
         "iqair_api_key": "your_key",
         "openweather_api_key": "your_key",
         "waqi_token": "your_token"
       }
       ```
     - Hoặc để crawler tự lấy từ biến môi trường.
  2. **HTTP Request**: Gọi endpoint `/main` của cleaner (POST, truyền `csv_file` hoặc `csv_content`).
  3. **(Tuỳ chọn) Query API hoặc DB**: Lấy dữ liệu sạch để xử lý tiếp.
- **Ví dụ cấu hình HTTP Request node:**
  - URL: `http://air-crawler:8000/run_optimized_crawl`
  - Method: POST
  - Body: `{}` hoặc truyền API key nếu cần.

- **Có thể lên lịch tự động bằng n8n Trigger node hoặc Cron node.**

## 📊 Ứng dụng & mở rộng

- Kết nối Power BI lấy dữ liệu real-time thông qua các endpoint JSON.
- Triển khai trên cloud (Heroku, Railway, EC2).
- Lên lịch tự động bằng Airflow hoặc `schedule`.

## ✅ Yêu cầu hệ thống

- Python 3.9+
- PostgreSQL
- Google Drive API (nếu cần upload)
- FastAPI, SQLAlchemy, Pandas, Uvicorn, Google API Client

## 🧑‍💻 Tác giả

Nguyễn Hữu Cường  
Dự án tốt nghiệp - Phân tích dữ liệu 2025

---

**Lưu ý:**  
- Khi public lên GitHub, hãy kiểm tra lại toàn bộ repo để đảm bảo không lộ thông tin nhạy cảm.
- Nếu lỡ commit thông tin nhạy cảm, hãy xóa commit đó và đổi lại các API key/mật khẩu liên quan.
