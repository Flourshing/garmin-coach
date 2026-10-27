"""Start the managed-container Gateway; account credentials are added privately."""
import os

from prepare_openclaw import prepare

prepare()
os.execvp("openclaw", ["openclaw", "gateway", "run", "--port", os.environ.get("PORT", "8080")])
