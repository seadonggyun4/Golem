"""Exercise installed host packages against a relocatable native installation."""
from pathlib import Path
import shutil
import subprocess
import sys

prefix, root, node_package = (Path(arg).resolve() for arg in sys.argv[1:])
library = prefix / "lib" / ("libgolem_binding.dylib" if sys.platform == "darwin" else "libgolem_binding.so")
addon = prefix / "lib/golem/node/golem_node.node"
if not library.is_file() or not addon.is_file() or not (node_package / "index.mjs").is_file():
    raise SystemExit("missing installed native or host package")
subprocess.run([sys.executable, str(root / "bindings/tests/test_python.py"), str(library), str(root), "--installed"],
               check=True, timeout=60)
node = shutil.which("node")
if node is None:
    raise SystemExit("Node.js is required for installed binding tests")
subprocess.run([node, str(root / "bindings/tests/test_node.mjs"), str(addon), str(root),
                str(node_package / "index.mjs")], check=True, timeout=60)
