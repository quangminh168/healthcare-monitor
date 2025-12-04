import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-1234")

    # MySQL Aiven (đã chuẩn hoá)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail (có thể bỏ qua nếu chưa cần)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
