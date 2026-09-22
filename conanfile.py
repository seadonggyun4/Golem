"""Public source-available Golem package; no private project assets exported."""
from pathlib import Path
import re

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import copy, rmdir
from conan.tools.gnu import PkgConfigDeps


class GolemConan(ConanFile):
    name = "golem"
    package_type = "static-library"
    license = "PolyForm-Noncommercial-1.0.0"
    author = "Donggyun Seo <seadonggyun@gmail.com>"
    url = "https://github.com/seadonggyun4/Golem"
    description = "Headless Agentic Work Engine with durable evidence and policy boundaries"
    settings = "os", "arch", "compiler", "build_type"
    options = {"fPIC": [True], "with_cli": [True, False]}
    default_options = {"fPIC": True, "with_cli": True}
    required_conan_version = ">=2.28 <3"

    def set_version(self):
        header = Path(self.recipe_folder, "include/golem/version.h").read_text()
        self.version = re.search(r'^#define GOLEM_VERSION_STRING "([^"]+)"', header, re.M)[1]

    def export(self):
        copy(self, "version.h", src=str(Path(self.recipe_folder, "include/golem")),
             dst=str(Path(self.export_folder, "include/golem")))

    def export_sources(self):
        for name in ("CMakeLists.txt", "LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"):
            copy(self, name, src=self.recipe_folder, dst=self.export_sources_folder)
        for directory, patterns in (("src", ("*.c", "*.h")),
                                    ("include", ("*.h",)), ("cmake", ("*.cmake.in",))):
            for pattern in patterns:
                copy(self, pattern, src=str(Path(self.recipe_folder, directory)),
                     dst=str(Path(self.export_sources_folder, directory)))

    def configure(self):
        self.settings.rm_safe("compiler.cppstd")
        self.settings.rm_safe("compiler.libcxx")

    def validate(self):
        if str(self.settings.os) not in ("Linux", "Macos"):
            raise ConanInvalidConfiguration("Golem currently supports Linux and macOS only")

    def requirements(self):
        self.requires("openssl/3.6.0")
        self.requires("json-c/0.18")
        self.requires("md4c/0.5.2")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        CMakeDeps(self).generate()
        PkgConfigDeps(self).generate()
        toolchain = CMakeToolchain(self)
        toolchain.variables.update({
            "BUILD_TESTING": False, "GOLEM_BUILD_CLI": bool(self.options.with_cli),
            "GOLEM_BUILD_BINDINGS": False, "GOLEM_BUILD_NODE_BINDING": False,
            "GOLEM_BUILD_BENCHMARKS": False, "GOLEM_BUILD_FUZZERS": False,
            "GOLEM_ENABLE_SANITIZERS": False,
            "CMAKE_POSITION_INDEPENDENT_CODE": bool(self.options.fPIC),
            "CMAKE_INSTALL_LIBDIR": "lib",
        })
        toolchain.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        CMake(self).install()
        for name in ("LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"):
            copy(self, name, src=self.source_folder, dst=str(Path(self.package_folder, "licenses")))
        # Consumers resolve dependencies from Conan's graph, never host installations.
        rmdir(self, str(Path(self.package_folder, "lib/cmake")))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Golem")
        self.cpp_info.set_property("cmake_target_name", "Golem::golem")
        self.cpp_info.libs = ["golem"]
        if self.options.with_cli:
            self.runenv_info.prepend_path("PATH", str(Path(self.package_folder, "bin")))
