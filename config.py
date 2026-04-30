import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    PREFERRED_URL_SCHEME = "https"
    SECRET_KEY           = os.environ.get("SECRET_KEY", "paquetellegue-secret-2024-xK9mN")
    DATA_DIR             = os.path.join(BASE_DIR, "data")
    GUIAS_DIR            = os.path.join(BASE_DIR, "data", "guias")
    RECIBOS_DIR          = os.path.join(BASE_DIR, "data", "recibos")
    FACTURAS_DIR         = os.path.join(BASE_DIR, "data", "facturas")
    DB_PATH              = os.path.join(BASE_DIR, "data", "sistema.db")
    MAX_CONTENT_LENGTH   = 16 * 1024 * 1024
