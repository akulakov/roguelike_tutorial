#python3
import json
import numpy as np
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
a = np.full((3,2), fill_value=1, order="F")
a2 = a.tolist()
a3 = np.array(a2)

graphic_dt = np.dtype(
    [
        ("ch", np.int32), ("fg", "3B"), ("bg", "3B"), ])
tile_dt = np.dtype(
    [
        ("walkable", bool), ("transparent", bool), ("dark", graphic_dt), ("light", graphic_dt),
    ])
from typing import Tuple
def new_tile(
    *,
    walkable: int,
    transparent: int,
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
) -> np.ndarray:
    return np.array((walkable, transparent, dark, light), dtype=tile_dt)
floor = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(" "), (255, 255, 255), (50, 50, 150)),
    light=(ord(" "), (255, 255, 255), (200, 180, 50)),
)

ar = np.full((1,2), fill_value=floor, order='F')
print("a", a)
print()
a = json.dumps(ar, cls=NumpyEncoder)

def load(jdata):
    rows = json.loads(jdata)
    for n,r in enumerate(rows):
        for m,col in enumerate(r):
            a,b,c,d=col
            ar[n,m] = np.array((a,b,tuple(c),tuple(d)), dtype=tile_dt)

print("ar", ar)
#np.savez('test.npz', a=a)
#data = np.load('test.npz')
