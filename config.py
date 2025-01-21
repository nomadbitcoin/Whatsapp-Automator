import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Ensure directories exist
for dir_path in [DATA_DIR, TEMP_DIR, OUTPUT_DIR]:
    os.makedirs(dir_path, exist_ok=True)

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

GROUP_ANALYZE = False
PDF_ANALYZE = True
AUDIO_ANALYZE = True
IMAGE_ANALYZE = True
TRY_GET_FIRST_MESSAGE = False
