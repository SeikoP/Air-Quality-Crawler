import pandas as pd
import numpy as np
from pathlib import Path
import io
import logging
import datetime
import pickle
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload
# from googleapiclient.errors import HttpError
from sqlalchemy import create_engine
import dotenv
from fastapi import FastAPI
from time import sleep
from typing import Dict, List
import os
from fastapi import FastAPI
from pathlib import Path
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('converted.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
dotenv.load_dotenv()

app = FastAPI()


@app.post("/main")
async def main(data: dict):
    csv_file = data.get("csv_file")
    csv_content = data.get("csv_content")
    
    if csv_content:
        df = pd.read_csv(io.StringIO(csv_content))
        source_folder = CLEANER_DIR
    elif csv_file:
        file_path = Path(csv_file)
        # Nếu truyền đường dẫn tương đối, hiểu là file trong CRAWL_DATA_DIR
        if not file_path.is_absolute():
            file_path = CRAWL_DATA_DIR / file_path
        if file_path.exists() and file_path.is_file():
            df = pd.read_csv(file_path)
            # Lưu file clean vào cùng tháng với file gốc
            try:
                month_folder = file_path.parent.name
                source_folder = CLEANER_DIR / month_folder
                source_folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                source_folder = CLEANER_DIR
        else:
            logger.error("CSV file not found or outside allowed directory")
            return {"status": "error", "message": "CSV file not found or outside allowed directory"}
    else:
        logger.error("No valid CSV data provided")
        return {"status": "error", "message": "No valid CSV data provided"}
    
    df = clean_data(df)
    mapping = transform_data(df)

    # Lưu file clean vào đúng thư mục
    cleaned_file = source_folder / 'cleaned_air_quality.csv'
    df.to_csv(cleaned_file, index=False, encoding='utf-8-sig')
    logger.info(f"Saved cleaned data to {cleaned_file}")

    # Lưu các bảng transform vào DATA_TRANFORM_DIR
    for table_name, table_data in mapping.items():
        table_path = TRANFORM_DIR / f"{table_name}.csv"
        table_data.to_csv(table_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved {table_name} to {table_path}")
        save_to_postgres(table_data, table_name, engine, if_exists='replace')
    
    return {
        "status": "success",
        "message": f"Processed {len(df)} records",
        "cleaned_file": str(cleaned_file)
    }

# Configuration
DOCKER_DATA_DIR = Path("/app/data")
if DOCKER_DATA_DIR.exists():
    BASE_DIR = Path("/app")
    CRAWL_DATA_DIR = DOCKER_DATA_DIR / 'data_export'
    # Folder chứa file clean và transform
    CLEANER_DIR = DOCKER_DATA_DIR
else:
    BASE_DIR = Path(r'D:\Project_Dp-15')
    CRAWL_DATA_DIR = BASE_DIR / 'Source' / 'data_crawler' / 'data' / 'data_export'
    # Folder chứa file clean và transform
    CLEANER_DIR = BASE_DIR / 'Source' / 'data_cleaner' / 'data'

CLEANED_DIR = CLEANER_DIR / 'data_cleaned'
TRANFORM_DIR = CLEANER_DIR / 'data_tranform'

# Tạo thư mục nếu chưa có
for folder in [CLEANED_DIR,TRANFORM_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

TOKEN_FILE = BASE_DIR / 'clean' / 'token_drive.pkl'
CREDENTIALS_FILE = 'credentials_oauth.json'
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://username:password@host:port/database_name')
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Initialize SQLAlchemy engine
engine = create_engine(DATABASE_URL)

def setup_directories():
    """Create data directory if it doesn't exist."""
    global DATA_DIR 
    DATA_DIR = CLEANED_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_data() -> pd.DataFrame:
    """Load và nối tất cả các file CSV crawl được trong data_export."""
    try:
        csv_files = list(CRAWL_DATA_DIR.glob('*.csv'))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {CRAWL_DATA_DIR}")
        df = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)
        logger.info(f"Loaded {len(df)} records from {len(csv_files)} files in {CRAWL_DATA_DIR}")
        return df
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

def save_to_csv(df: pd.DataFrame, mapping: Dict[str, pd.DataFrame]):
    """Save cleaned DataFrame and transformed tables to CSV in the data directory."""
    try:
        # Save cleaned data
        output_path = DATA_DIR / 'cleaned_air_quality.csv'
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved cleaned data to {output_path}")

        # Save transformed tables
        for table_name, table_data in mapping.items():
            file_path = DATA_DIR / f"{table_name}.csv"
            table_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"Saved {table_name} to {file_path}")
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")
        raise

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and preprocess the DataFrame."""
    try:
        # Define columns
        numeric_cols = ['aqi', 'pm25', 'pm10', 'o3', 'no2', 'so2', 'co', 'nh3', 'temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'visibility']
        categorical_cols = ['city', 'province', 'city_source', 'source', 'status', 'weather_condition']

        # Fill missing values
        df.fillna({col: df[col].mean() for col in numeric_cols}, inplace=True)
        df.fillna({col: 'unknown' for col in categorical_cols}, inplace=True)

        # Handle numeric columns: remove negative values and cap outliers
        for col in numeric_cols:
            df[col] = df[col].clip(lower=0, upper=df[col].quantile(0.999)).round(2)

        # Process timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').fillna(method='ffill')

        # Normalize weather condition
        weather_mapping = {
            'clouds': 'cloudy', 'clear': 'clear', 'rain': 'rain',
            'snow': 'snow', 'mist': 'mist', 'fog': 'fog'
        }
        df['weather_condition'] = (
            df['weather_condition'].str.lower().str.strip()
            .replace('', np.nan).fillna('unknown')
            .replace(weather_mapping)
        )

        # Normalize categorical columns
        df[categorical_cols] = df[categorical_cols].apply(lambda x: x.str.lower().str.strip())

        # Remove duplicates
        initial_rows = df.shape[0]
        df = df.drop_duplicates()
        logger.info(f"Removed {initial_rows - df.shape[0]} duplicate rows")

        # Validate coordinates
        df['longitude'] = df['longitude'].apply(lambda x: x if -180 <= x <= 180 else np.nan)
        df['latitude'] = df['latitude'].apply(lambda x: x if -90 <= x <= 90 else np.nan)
        df['longitude'] = df.groupby('city')['longitude'].transform(lambda x: x.fillna(x.mean()))
        df['latitude'] = df.groupby('city')['latitude'].transform(lambda x: x.fillna(x.mean()))

        # Drop unnecessary columns
        df = df.drop(columns=['uv_index', 'aqi_cn'], errors='ignore')

        return df
    except Exception as e:
        logger.error(f"Error cleaning data: {e}")
        raise

def transform_data(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Transform data into normalized tables."""
    try:
        # Create cities table
        cities = (
            df[['city', 'province', 'latitude', 'longitude']]
            .drop_duplicates()
            .reset_index(drop=True)
            .assign(city_id=lambda x: x.index + 1)
            [['city_id', 'city', 'province', 'latitude', 'longitude']]
            .rename(columns={'city': 'city_name'})
        )

        # Create sources table
        sources = (
            df[['source']]
            .drop_duplicates()
            .reset_index(drop=True)
            .assign(source_id=lambda x: x.index + 1)
            [['source_id', 'source']]
            .rename(columns={'source': 'source_name'})
        )

        # Create weather conditions table
        conditions = (
            df[['weather_condition']]
            .drop_duplicates()
            .reset_index(drop=True)
            .assign(condition_id=lambda x: x.index + 1)
            [['condition_id', 'weather_condition']]
            .rename(columns={'weather_condition': 'condition_name'})
        )

        # Create mappings
        city_map = cities.set_index(['city_name', 'province'])['city_id'].to_dict()
        source_map = sources.set_index('source_name')['source_id'].to_dict()
        condition_map = conditions.set_index('condition_name')['condition_id'].to_dict()

        # Map IDs to main DataFrame
        df['city_id'] = df.apply(lambda x: city_map.get((x['city'], x['province'])), axis=1)
        df['source_id'] = df['source'].map(source_map)
        df['condition_id'] = df['weather_condition'].map(condition_map)

        # Create air quality table
        air_quality = (
            df[[
                'timestamp', 'city_id', 'source_id', 'condition_id', 'aqi', 'pm25', 'pm10', 'o3',
                'no2', 'so2', 'co', 'nh3', 'temperature', 'humidity', 'pressure', 'wind_speed',
                'wind_direction', 'visibility', 'status'
            ]]
            .reset_index(drop=True)
            .assign(record_id=lambda x: x.index + 1)
        )

        return {
            'AirQualityRecord': air_quality,
            'City': cities,
            'Source': sources,
            'WeatherCondition': conditions
        }
    except Exception as e:
        logger.error(f"Error transforming data: {e}")
        raise

def save_to_csv(df: pd.DataFrame, mapping: Dict[str, pd.DataFrame]):
    """Save cleaned DataFrame and transformed tables to CSV."""
    try:
        # Save cleaned data
        output_path = CLEANED_DIR / 'cleaned_air_quality.csv'
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved cleaned data to {output_path}")

        # Save transformed tables
        for table_name, table_data in mapping.items():
            file_path = TRANFORM_DIR / f"{table_name}.csv"
            table_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"Saved {table_name} to {file_path}")
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")
        raise

def save_to_postgres(df: pd.DataFrame, table_name: str, engine, if_exists: str = 'append', chunksize: int = 1000):
    """Save DataFrame to PostgreSQL table."""
    try:
        df.to_sql(table_name, engine, if_exists=if_exists, index=False, chunksize=chunksize)
        logger.info(f"Saved {len(df)} records to PostgreSQL table {table_name}")
    except Exception as e:
        logger.error(f"Error saving to PostgreSQL table {table_name}: {e}")
        raise

# def authenticate() -> object:
#     """Authenticate with Google Drive API."""
#     try:
#         creds = None
#         if TOKEN_FILE.exists():
#             with open(TOKEN_FILE, 'rb') as token:
#                 creds = pickle.load(token)
#         if not creds or not creds.valid:
#             flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
#             creds = flow.run_local_server(port=0)
#             with open(TOKEN_FILE, 'wb') as token:
#                 pickle.dump(creds, token)
#         return creds
#     except Exception as e:
#         logger.error(f"Error authenticating with Google Drive: {e}")
#         raise

# def upload_or_update_file(
#     service, file_path: Path, folder_id: str, skip_upload_if_not_exist: bool = False,
#     skip_update_if_exist: bool = False, retries: int = 3
# ) -> str:
#     """Upload or update a file to Google Drive with retry logic."""
#     file_name = file_path.name
#     for attempt in range(retries):
#         try:
#             query = f"name = '{file_name}' and '{folder_id}' in parents and trashed = false"
#             results = service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=1).execute()
#             files = results.get('files', [])
#             media = MediaFileUpload(str(file_path), resumable=True)

#             if files:
#                 file_id = files[0]['id']
#                 if skip_update_if_exist:
#                     logger.info(f"File '{file_name}' exists, skipping update")
#                     return f"https://drive.google.com/file/d/{file_id}/view"
#                 logger.info(f"Updating existing file '{file_name}'")
#                 service.files().update(fileId=file_id, media_body=media).execute()
#             else:
#                 if skip_upload_if_not_exist:
#                     logger.info(f"File '{file_name}' does not exist, skipping upload")
#                     return None
#                 logger.info(f"Uploading new file '{file_name}'")
#                 file_metadata = {'name': file_name, 'parents': [folder_id]}
#                 file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
#                 file_id = file.get('id')

#             try:
#                 service.permissions().create(
#                     fileId=file_id, body={'type': 'anyone', 'role': 'reader'}, fields='id'
#                 ).execute()
#             except Exception as perm_error:
#                 logger.warning(f"Error setting permissions for {file_name}: {perm_error}")

#             file_url = f"https://drive.google.com/file/d/{file_id}/view"
#             logger.info(f"File uploaded: {file_url}")
#             return file_url
#         except HttpError as e:
#             if attempt < retries - 1:
#                 sleep(2 ** attempt)
#                 continue
#             logger.error(f"Failed to upload {file_name} after {retries} attempts: {e}")
#             return None

# def get_or_create_folder(service, folder_name: str, parent_folder_id: str = None) -> str:
#     """Get or create a Google Drive folder."""
#     try:
#         query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
#         if parent_folder_id:
#             query += f" and '{parent_folder_id}' in parents"
#         results = service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=10).execute()
#         folders = results.get('files', [])
#         if folders:
#             folder_id = folders[0]['id']
#             logger.info(f"Found folder '{folder_name}' (ID: {folder_id})")
#             return folder_id
#         logger.info(f"Creating new folder '{folder_name}'")
#         metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
#         if parent_folder_id:
#             metadata['parents'] = [parent_folder_id]
#         folder = service.files().create(body=metadata, fields='id').execute()
#         folder_id = folder.get('id')
#         logger.info(f"Created folder '{folder_name}' (ID: {folder_id})")
#         return folder_id
#     except Exception as e:
#         logger.error(f"Error managing folder '{folder_name}': {e}")
#         raise

# def upload_to_google_drive(df: pd.DataFrame, mapping: Dict[str, pd.DataFrame]):
#     """Upload files to Google Drive."""
#     UPLOAD_TO_GOOGLE_DRIVE = False  # Toggle based on environment variable or config
#     if not UPLOAD_TO_GOOGLE_DRIVE:
#         logger.info("Google Drive upload disabled")
#         return

#     try:
#         creds = authenticate()
#         service = build('drive', 'v3', credentials=creds)
#         doc_folder = get_or_create_folder(service, 'DOC', '1ear6Kj0s-bqJe2vOLMNJ8fsdy7ERLbil')
#         resources_folder = get_or_create_folder(service, 'Resources', doc_folder)
#         data_source_folder = get_or_create_folder(service, 'Data Source', resources_folder)
#         data_cleaned_folder = get_or_create_folder(service, 'Data Cleaned', resources_folder)
#         normalized_data_folder = get_or_create_folder(service, 'Normalized Data', resources_folder)

#         # Save and upload source data
#         source_file = DATA_DIR / 'air_quality_data_source.csv'
#         df.to_csv(source_file, index=False, encoding='utf-8-sig')
#         upload_or_update_file(service, source_file, data_source_folder)

#         # Upload cleaned data
#         cleaned_file = CLEANED_DIR / 'cleaned_air_quality.csv'
#         upload_or_update_file(service, cleaned_file, data_cleaned_folder)

#         # Upload transformed data
#         for file_path in TRANSFORM_DIR.glob('*.csv'):
#             upload_or_update_file(service, file_path, normalized_data_folder)

#     except Exception as e:
#         logger.error(f"Error uploading to Google Drive: {e}")

@app.get("/air-quality")
def get_air_quality():
    """FastAPI endpoint to retrieve recent air quality records."""
    try:
        query = 'SELECT * FROM "AirQualityRecord" ORDER BY timestamp DESC LIMIT 100'
        df = pd.read_sql(query, engine)
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error retrieving air quality data: {e}")
        return {"error": str(e)}

def main():
    """Main function to orchestrate the data processing pipeline."""
    try:
        setup_directories()
        df = load_data()
        df = clean_data(df)
        mapping = transform_data(df)
        save_to_csv(df, mapping)
        for table_name, table_data in mapping.items():
            save_to_postgres(table_data, table_name, engine, if_exists='replace')
        # upload_to_google_drive(df, mapping)
        logger.info("Data processing pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

if __name__ == '__main__':
    main()