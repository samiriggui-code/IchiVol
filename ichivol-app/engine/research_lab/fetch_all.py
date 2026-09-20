import json, httpx
from research_lab.data import load_or_fetch, ms
from research_lab.universe import A_UNIVERSE, select_extended

START, END = ms(2025, 4, 1), ms(2026, 9, 20, 16)
syms = list(A_UNIVERSE) + select_extended()["extra"]
with httpx.Client() as c:
    for s in syms:
        for iv in ("1h", "4h"):
            rows = load_or_fetch(s, iv, START, END, c)
            print(s, iv, len(rows), flush=True)
