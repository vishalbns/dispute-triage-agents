"""Central configuration. Everything swappable lives here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")          # every entry point picks this up
DB_PATH = ROOT / "dispute.db"
POLICY_DIR = ROOT / "policies"
CHROMA_DIR = ROOT / ".chroma"

# Which model backend to use: "bedrock" (the real target) or "anthropic" (works without AWS).
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "bedrock")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
ANTHROPIC_MODEL_ID = os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-5")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# Embeddings: "local" uses Chroma's built-in model, "titan" uses Bedrock.
EMBEDDINGS = os.getenv("EMBEDDINGS", "local")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Optional Bedrock Guardrail. Leave unset to use the local checks only.
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "DRAFT")

# Any provisional credit at or above this needs a human, no exceptions.
AUTO_APPROVE_CEILING_CENTS = 0      # 0 means every money movement needs approval

# ---- member notifications -------------------------------------------------
# Leave SMTP_HOST unset and decisions are written to outbox/ instead of sent.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
# macOS only: read the password from Keychain instead of putting it in .env
SMTP_KEYCHAIN_SERVICE = os.getenv("SMTP_KEYCHAIN_SERVICE", "")
