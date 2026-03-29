
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        # ── LLM APIs ───────────────────────────────────────────────────
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY','')
        self.DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY','')

        # ── AWS (for data sources) ─────────────────────────────────────
        self.AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID','')
        self.AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY','')

        # ── Supabase (database) ────────────────────────────────────────
        self.SUPABASE_URL = os.getenv('SUPABASE_URL','')
        self.SUPABASE_KEY = os.getenv('SUPABASE_KEY','')
        self.SUPABASE_PASSWORD = os.getenv('SUPABASE_PASSWORD','')

        # ── Email (for notifications) ──────────────────────────────────
        self.SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
        self.SMTP_USER = os.getenv('SMTP_USER', '')
        self.SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
        self.EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@esg-system.com')

        # ── Scheduler config ───────────────────────────────────────────
        self.SCAN_INTERVAL_MINUTES = int(os.getenv('SCAN_INTERVAL_MINUTES', '30'))
        self.MAX_SCAN_RESULTS = int(os.getenv('MAX_SCAN_RESULTS', '100'))

        # ── API Keys for data sources ──────────────────────────────────
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY', '')
        self.NEWS_API_KEY = os.getenv('NEWS_API_KEY', '')

        # ── Debug mode ─────────────────────────────────────────────────
        self.DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

   