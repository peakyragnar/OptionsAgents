# In your live_monitoring_dashboard.py, change this line:

# OLD:
def __init__(self, data_dir: str = "data", db_path: str = None):
    self.db_path = db_path or os.getenv("OA_GAMMA_DB", "data/intraday.db")

# NEW:  
def __init__(self, data_dir: str = "data", db_path: str = None):
    self.db_path = db_path or os.getenv("OA_GAMMA_DB", "data/live.db")  # Changed to live.db