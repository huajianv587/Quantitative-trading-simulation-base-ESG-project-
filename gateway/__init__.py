# gateway/__init__.py
# 确保项目根目录在 sys.path 中，使 gateway.* 导入路径可用
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
