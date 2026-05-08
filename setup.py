# Script cài đặt
from pathlib import Path

from setuptools import find_packages, setup


BASE_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"


def load_requirements(path: Path) -> list[str]:
    """Đọc runtime dependencies từ requirements.txt, bỏ comment và dòng trống."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


setup(
    name="zalo-crawler",
    version="1.0.1",
    packages=find_packages(),
    install_requires=load_requirements(REQUIREMENTS_FILE),
    author="Your Name",
    author_email="your.email@example.com",
    description="A modular Zalo message crawler",
    keywords="zalo, crawler, selenium, message",
    python_requires=">=3.9",
)
