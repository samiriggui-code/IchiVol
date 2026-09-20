"""Build (and cache) per-bar closed-candle signals for every symbol."""
import glob, json, pickle, sys
from concurrent.futures import ProcessPoolExecutor
from research_lab.data import CACHE
from research_lab.signals import compute_bar_signals, to_candles
from research_lab.universe import A_UNIVERSE, select_extended

PKL = CACHE / "signals_v1.pkl"


def one(sym):
    f1 = glob.glob(str(CACHE / f"{sym}_1h_*.json"))[0]
    f4 = glob.glob(str(CACHE / f"{sym}_4h_*.json"))[0]
    c = to_candles(json.load(open(f1)))
    h = to_candles(json.load(open(f4)))
    sig = compute_bar_signals(c, h)
    return sym, {cd.time: (cd, sg) for cd, sg in zip(c, sig)}


def build(force=False):
    if PKL.exists() and not force:
        return pickle.load(open(PKL, "rb"))
    syms = list(A_UNIVERSE) + select_extended()["extra"]
    with ProcessPoolExecutor(max_workers=4) as ex:
        data = dict(ex.map(one, syms))
    pickle.dump(data, open(PKL, "wb"))
    return data


if __name__ == "__main__":
    d = build(force="--force" in sys.argv)
    print({k: len(v) for k, v in list(d.items())[:3]}, len(d))
