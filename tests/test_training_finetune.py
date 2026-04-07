import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_finetune_help_lists_num_train_epochs():
    result = subprocess.run(
        [sys.executable, "training/finetune.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "--num_train_epochs" in result.stdout
