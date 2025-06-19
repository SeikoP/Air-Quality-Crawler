# 🌍 Air Quality Monitoring System

## 📌 Giới thiệu

Hệ thống này thực hiện thu thập dữ liệu chất lượng không khí từ các nguồn như **IQAir**, **WAQI**, và **OpenWeatherMap**, làm sạch và chuyển đổi dữ liệu, sau đó cung cấp API thời gian thực để phục vụ trình bày dữ liệu qua Power BI hoặc các dashboard tương tác.

## 🧱 Cấu trúc dự án

```
├── data_crawler.py       # Thu thập dữ liệu từ nhiều API/web
├── clean_data.py         # Làm sạch, chuẩn hóa, lưu vào DB, Google Drive
├── api.py                # Cung cấp các API FastAPI để truy xuất dữ liệu
├── .env                  # Biến môi trường như DATABASE_URL, API_KEY,...
├── requirements.txt      # Danh sách thư viện cần cài đặt
└── README.md             # Tài liệu này
```

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

### 2. Cấu hình `.env`
```env
DATABASE_URL=postgresql+psycopg2://user:pass@host:port/db
OPENWEATHER_API_KEY=your_key
WAQI_TOKEN=your_token
BASE_DIR=D:\Project_Dp-15
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
