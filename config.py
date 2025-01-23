import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Ensure directories exist
for dir_path in [DATA_DIR, TEMP_DIR, OUTPUT_DIR, LOG_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()  # INFO, DEBUG, ERROR, etc.
LOG_TO_FILE = True
LOG_TO_CONSOLE = True
LOG_FORMAT = {
    'console': '%(asctime)s - %(levelname)s - %(message)s',
    'file': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
}

# Feature flags
GROUP_ANALYZE = False
PDF_ANALYZE = True
AUDIO_ANALYZE = True
IMAGE_ANALYZE = True
TRY_GET_FIRST_MESSAGE = False

# Keywords for receipt detection
RECEIPT_KEYWORDS = [
    'comprovante',
    'pagamento',
    'transferência',
    'pix',
    'valor',
    'data da transação',
    'beneficiário',
    'ted',
    'doc',
    'recibo',
    'autenticação',
    'instituição'
]
