import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "bond_notifier"))

os.environ["BOT_TOKEN"] = "000000000:test-token"
os.environ["DB_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="bondschecker-tests-")) / "bonds.db"
)
