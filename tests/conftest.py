import sys
from pathlib import Path

# Ensure `import src...` works regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
