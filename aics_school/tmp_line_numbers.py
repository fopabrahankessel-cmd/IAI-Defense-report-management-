from pathlib import Path

path = Path(
    r"c:/Users/fopak/OneDrive/Documents/SE3A NOTES/ADVANCED OOP (DJANGO)/Django CA/aics_school/core/templates/core/report_detail.html"
)
for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if 30 <= i <= 50:
        print(i, line.rstrip())
