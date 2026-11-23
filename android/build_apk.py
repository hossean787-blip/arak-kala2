"""Build the unsigned Arak Kala APK with Android SDK Build Tools 36."""
import argparse
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
SOURCE = APP / "src" / "main"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=os.environ.get("ANDROID_HOME"))
    parser.add_argument("--jdk", type=Path, default=os.environ.get("JAVA_HOME"))
    parser.add_argument("--output", type=Path, default=ROOT / "Arak-Kala-unsigned.apk")
    args = parser.parse_args()
    if args.sdk is None or args.jdk is None:
        parser.error("Set ANDROID_HOME and JAVA_HOME or pass --sdk and --jdk")

    gradle = (APP / "build.gradle").read_text(encoding="utf-8")
    namespace = re.search(r"namespace '([^']+)'", gradle).group(1)
    version_name = re.search(r"versionName '([^']+)'", gradle).group(1)
    min_sdk = re.search(r"minSdk (\d+)", gradle).group(1)
    target_sdk = re.search(r"targetSdk (\d+)", gradle).group(1)
    compile_sdk = re.search(r"compileSdk (\d+)", gradle).group(1)
    version_code = re.search(r"versionCode (\d+)", gradle).group(1)

    executable = ".exe" if os.name == "nt" else ""
    sdk_tools = args.sdk / "build-tools" / "36.0.0"
    java_bin = args.jdk / "bin"
    android_jar = args.sdk / "platforms" / ("android-" + compile_sdk) / "android.jar"

    with TemporaryDirectory(prefix="arak-kala-") as directory:
        work = Path(directory)
        classes, generated, dex = [work / name for name in ("classes", "generated", "dex")]
        for folder in (classes, generated, dex):
            folder.mkdir()

        manifest_text = (SOURCE / "AndroidManifest.xml").read_text(encoding="utf-8")
        manifest = work / "AndroidManifest.xml"
        manifest.write_text(manifest_text.replace("<manifest ", f'<manifest package="{namespace}" ', 1),
                            encoding="utf-8")
        resources, base, java_archive = [work / name for name in ("res.zip", "base.apk", "classes.jar")]
        subprocess.run([sdk_tools / ("aapt2" + executable), "compile", "--dir", SOURCE / "res",
                        "-o", resources], check=True)
        subprocess.run([sdk_tools / ("aapt2" + executable), "link", "-I", android_jar,
                        "--manifest", manifest, "--java", generated,
                        "--min-sdk-version", min_sdk, "--target-sdk-version", target_sdk,
                        "--version-code", version_code, "--version-name", version_name,
                        "-o", base, resources], check=True)
        java_sources = sorted((SOURCE / "java").rglob("*.java")) + sorted(generated.rglob("*.java"))
        subprocess.run([java_bin / ("javac" + executable), "--release", "17", "-encoding", "UTF-8",
                        "-classpath", android_jar, "-d", classes, *java_sources], check=True)
        subprocess.run([java_bin / ("jar" + executable), "--create", "--file", java_archive,
                        "-C", classes, "."], check=True)
        subprocess.run([java_bin / ("java" + executable), "-cp", sdk_tools / "lib" / "d8.jar",
                        "com.android.tools.r8.D8", "--release", "--min-api", min_sdk,
                        "--lib", android_jar, "--output", dex, java_archive], check=True)
        with ZipFile(base, "a") as package:
            for name in sorted(dex.glob("classes*.dex")):
                package.write(name, name.name)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sdk_tools / ("zipalign" + executable), "-P", "16", "-f", "4",
                        base, args.output], check=True)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
