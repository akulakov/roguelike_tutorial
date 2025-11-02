
from copy import copy
class Loc:
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x, self.y = x,y

    def __iter__(self):
        yield self.x
        yield self.y

    def __lt__(self, o):
        return tuple(self) < tuple(o)

    def adj(self):
        x,y=self
        return set([(x+1,y),(x-1,y),(x,y+1),(x,y-1), (x+1,y+1), (x-1,y-1), (x+1,y-1), (x-1,y+1)])

    def adj_locs(self, include_self=False):
        l = [Loc(*tup) for tup in self.adj()]
        if include_self:
            l.append(copy(self))
        return l

    def mod(self, mx=0, my=0, mult=1):
        return Loc(self.x+mx*mult, self.y+my*mult)

    def is_pos(self):
        return self.x>0 or self.y>0

    def perpendicular_dirs(self, mod):
        """Given a direction, give 2 perpendiculars, i.e. for right, return up and down, etc."""
        return [Loc(mod.y, mod.x), Loc(-mod.y, -mod.x)]

    def __add__(self, mod):
        return Loc(self.x+mod.x, self.y+mod.y)

    def dir_to(self, loc):
        return Loc(loc.x - self.x, loc.y - self.y
)
    def dist(self, loc):
        dx = loc.x - self.x
        dy = loc.y - self.y
        return max(abs(dx), abs(dy))  # Chebyshev distance.

    def __getitem__(self, idx):
        return tuple(self)[idx]

    def __repr__(self):
        return f'<{self.x},{self.y}>'

    def __eq__(self, o):
        # doesn't work for opening doors???
        # return isinstance(o, self.__class__) and o and tuple(self)==tuple(o)
        return o and tuple(self)==tuple(o)

    def __hash__(self):
        return hash(tuple(self))

    def opposite(self):
        return Loc(-self.x, -self.y)
