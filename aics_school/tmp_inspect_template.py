from pathlib import Path
import re

path = Path(
    r"c:/Users/fopak/OneDrive/Documents/SE3A NOTES/ADVANCED OOP (DJANGO)/Django CA/aics_school/core/templates/core/report_detail.html"
)
content = path.read_text(encoding="utf-8")
tags = re.findall(r"\{[%{].*?[%}]\}", content, re.S)
for i, tag in enumerate(tags, 1):
    print(i, tag)
