from pathlib import Path
import json
import shlex
import subprocess
import tempfile

from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, cmake_layout
from conan.tools.env import VirtualRunEnv


class GolemConsumer(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"
    test_type = "explicit"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        package = Path(self.dependencies["golem"].package_folder)
        for name in ("LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"):
            if not (package / "licenses" / name).is_file():
                raise RuntimeError("Missing legal file: " + name)
        if not can_run(self):
            return
        executable = Path(self.build_folder, self.cpp.build.bindirs[0], "consumer")
        self.run(shlex.quote(str(executable)), env="conanrun")
        if not self.dependencies["golem"].options.with_cli:
            return
        cli = package / "bin/golem"
        with tempfile.TemporaryDirectory(prefix="golem-conan-") as tmp:
            root = Path(tmp).resolve()
            def call(*args):
                with VirtualRunEnv(self).vars().apply():
                    result = subprocess.run([str(cli), *map(str, args)], check=True,
                                            capture_output=True, text=True, timeout=30)
                return json.loads(result.stdout)
            call("init", root / "project")
            capsule = root / "project/capsule.json"
            call("capsule", "validate", capsule)
            result = call("run", "--noop", capsule, "--output", root / "run")
            assert result["state"] == "SUCCEEDED" and result["acceptance_verified"] is False
            assert call("replay", root / "run")["bundle_verified"] is True
            bill = call("cost", "report", root / "run")
            assert len(bill["entries"]) == 6 and bill["actual"]["nano_cost"] == "0"
