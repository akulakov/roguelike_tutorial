from copy import copy
from random import randint, random, choice, choices
from dataclasses import dataclass
import tcod

from game_map import GameMap, Stairs
import tile_types
import entity
from util import Loc

max_items_by_floor = [
   (1, 1),
   (4, 2),
]

max_monsters_by_floor = [
   (1, 2),
   (4, 3),
   (6, 5),
]

class RectangularRoom:
    auspicious = 0

    def __init__(self, x, y, width, height):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height
        self.p1 = Loc(x,y)
        self.p2 = Loc(x+width, y+height)
        self.entries = []

    def __repr__(self):
        x1,x2,y1,y2 = self.x1, self.x2, self.y1, self.y2
        return f'<{x1},{y1} {x2},{y2}>'

    @property
    def center(self):
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)
        return Loc(center_x, center_y)

    @property
    def inner(self):
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def inner2(self):
        return Loc(self.x1+2, self.y1+2), Loc(self.x2-2, self.y2-2)

    def __contains__(self, loc):
        return self.x1 <= loc.x <= self.x2 and self.y1 <= loc.y <= self.y2

    def walls(self):
        l = []
        p1, p2 = self.p1, self.p2
        for y in range(p1.y, p2.y):
            l.append(Loc(p1.x, y))
            l.append(Loc(p2.x, y))
        for x in range(p1.x, p2.x):
            l.append(Loc(x, p1.y))
            l.append(Loc(x, p2.y))
        return l

    def locs(self, check=None):
        """`check` func will result in early return"""
        l = []
        p1, p2 = self.p1, self.p2
        for y in range(p1.y, p2.y):
            for x in range(p1.x, p2.x):
                loc = Loc(x, y)
                if check and check(loc):
                    return
                else:
                    l.append(loc)
        return l

    def inner2_locs(self):
        l = []
        p1, p2 = self.inner2()
        for y in range(p1.y, p2.y):
            for x in range(p1.x, p2.x):
                l.append(Loc(x,y))
        return l

    def intersects(self, other):
        return self.x1-1 <= other.x2 and self.x2+1 >= other.x1 and self.y1-1 <= other.y2 and self.y2+1 >= other.y1

    def interval_x(self):
        return Interval(self.x1, self.x2)
    def interval_y(self):
        return Interval(self.y1, self.y2)

    def closest_x(self, o):
        """Closest x coordinates to other room."""
        if o.x1 > self.x2:
            return o.x1, self.x2
        return o.x2, self.x1

    def closest_y(self, o):
        """Closest y coordinates to other room."""
        if o.y1 > self.y2:
            return o.y1, self.y2
        return o.y2, self.y1

    def horizontal_to(self, o):
        x1,x2,y1,y2 = self.x1, self.x2, self.y1, self.y2
        return y2-y1 < x2-x1

def spawn(type, dungeon, engine, loc):
    if type.id in engine.specials:
        return
    m = type(engine, loc.x, loc.y)
    dungeon.entities.add(m)
    if m.id:
        engine.specials[m.id] = m

    if isinstance(m, entity.Living):
        items = get_entities_at_random(item_chances, randint(0,2), engine.level)
        for i in items:
            m.inventory.add(i(engine))
        m.inventory.add(entity.LightningScroll(engine))
        if random()>.5:
            m.asleep = -1
            #print('in spawn, adding', m, m.loc, m.asleep)

    # spawn a box with contents
    if isinstance(m, (entity.Box, entity.UndergroundSpace)):
        items = get_entities_at_random(item_chances, randint(0,2), engine.level)
        for i in items:
            if i not in (entity.Box, entity.UndergroundSpace):
                m.inventory.add(i(engine))
    if isinstance(m, entity.Living):
        if m.asleep:
            print('in spawn, m, m.loc, m.asleep', m, m.loc, m.asleep)
    return m

E = entity
item_chances = {
   0: [(E.HealthPotion, 35), (E.ChainMail, 25), (E.Box, 35)],
   2: [(E.ConfusionScroll, 10)],
   4: [(E.LightningScroll, 25), (E.Sword, 5)],
   6: [(E.FireballScroll, 25), (E.ChainMail, 15)],
   8: [(E.BurlyArmor, 10), (E.CreakingArmor, 5)],
}

enemy_chances = {
   0: [(E.Orc, 20), (E.Gremlin, 80)],
   3: [(E.BroomTroll, 85)],
   5: [(E.Troll, 30)],
   7: [(E.Troll, 60)],
   8: [(E.ThwackingOrc, 40)],
   9: [(E.BurningOrc, 40)],
   10: [(E.ResoluteOrc, 40)],
   11: [(E.KnurledGoblin, 40)],
   12: [(E.MusculousGoblin, 40)],
   13: [(E.SatyricGoblin, 40)],
   14: [(E.InsuperableTroll, 40)],
}

def get_entities_at_random(weighted_chances_by_floor, number_of_entities, floor):
    entity_weighted_chances = {}

    for key, values in weighted_chances_by_floor.items():
        if key > floor:
            break
        else:
            for value in values:
                entity = value[0]
                weighted_chance = value[1]
                entity_weighted_chances[entity] = weighted_chance

    entities = list(entity_weighted_chances.keys())
    entity_weighted_chance_values = list(entity_weighted_chances.values())
    return choices(entities, weights=entity_weighted_chance_values, k=number_of_entities)

def place_entities(room, dungeon, engine):
    monsters = get_entities_at_random(enemy_chances, randint(0,2), engine.level)
    items = get_entities_at_random(item_chances, randint(0,2), engine.level)
    from entity import Water

    if random()>.9:
        loc = Loc( randint(room.x1 + 1, room.x2 - 1), randint(room.y1 + 1, room.y2 - 1) )
        spawn(Water, dungeon, engine, loc)

    for e in monsters + items:
        loc = Loc( randint(room.x1 + 1, room.x2 - 1), randint(room.y1 + 1, room.y2 - 1) )
        if not any(loc==entity.loc for entity in dungeon.entities):
            spawn(e, dungeon, engine, loc)
            if issubclass(e, entity.Living) and e.gen_companions:
                odds, mn, mx = e.gen_companions
                if random()>odds:
                    n = randint(mn, mx)
                    lst = dungeon.empty_lst(loc.adj_locs())[:n]
                    for loc in lst:
                        spawn(e, dungeon, engine, loc)

def place_special(room, dungeon, engine, cls):
    for _ in range(50):
        loc = Loc( randint(room.x1 + 1, room.x2 - 1), randint(room.y1 + 1, room.y2 - 1) )
        if not any(loc==entity.loc for entity in dungeon.entities):
            print("special cls", cls, loc)
            spawn(cls, dungeon, engine, loc)
            return

def place_vertical(room, dungeon, engine, cls):
    for _ in range(50):
        loc = Loc( randint(room.x1 + 1, room.x2 - 1), randint(room.y1 + 1, room.y2 - 1) )
        if loc not in (dungeon.left, dungeon.right, dungeon.up):
            print("vertial cls", cls, loc)
            spawn(cls, dungeon, engine, loc)
            return

@dataclass
class Interval:
    a:int
    b:int

    def inner(self):
        return Interval(self.a+2, self.b-2)

    def intersects(self, o):
        c = max(self.a, o.a)
        d = min(self.b, o.b)
        if (d-c) >= 0:
            return Interval(c, d)

    def intersects_inner(self, o):
        return self.inner().intersects(o.inner())

    def random(self):
        return randint(self.a, self.b)

    def __repr__(self):
        return f'<{self.a}->{self.b}>'

def line(a,b,x=None,y=None):
    if a>b:
        a,b = b,a
    l = []
    for c in range(a,b+1):
        if x:
            l.append((x,c))
        else:
            l.append((c,y))
    return l

def z_line(a, b):
    """line in a z-shape."""
    l=[]
    if abs(a.x-b.x) > abs(a.y-b.y):
        if a.x>b.x:
            a,b=b,a
        m = a.x + int((b.x-a.x)/2)
        l.extend(line(a.x, m, y=a.y))
        l.extend(line(a.y, b.y, x=m))
        l.extend(line(m, b.x, y=b.y))
    else:
        if a.y>b.y:
            a,b=b,a
        m = a.y + int((b.y-a.y)/2)
        l.extend(line(a.y, m, x=a.x))
        l.extend(line(a.x, b.x, y=m))
        l.extend(line(m, b.y, x=b.x))
    return l

def l_line(a, b):
    l = []
    if a.x>b.x:
        a,b=b,a
    l.extend(line(a.x, b.x, y=a.y))
    l.extend(line(a.y, b.y, x=b.x))
    return l


def generate_special_dungeon(max_rooms, room_min_size, room_max_size, map_width, map_height, player, engine, up_map, special_level):
    if special_level.custom_map:
        dungeon = engine.custom_maps[special_level.custom_map]
        dungeon.entities = {player}
        dungeon.level = engine.level+1
        print("dungeon.up", dungeon.up)
        print("engine", engine)
        if not dungeon.up:
            dungeon.up = Stairs(engine.game_map.random_empty(), above_loc=player.loc)
        dungeon.up.game_map = engine.game_map
    else:
        dungeon = GameMap(map_width, map_height, {player}, engine.level+1)
    engine.game_map = dungeon
    rooms = []
    rnum = 1
    for r in special_level.rooms or ():
        room = RectangularRoom(*r)
        rooms.append(room)
        dungeon.tiles[room.inner] = tile_types.floor
        place_entities(room, dungeon, engine)
        rooms.append(room)

        cls = entity.special_data.get((engine.level,rnum))
        if cls:
            place_special(room, dungeon, engine, cls)
        place_vertical(room, dungeon, engine, entity.UndergroundSpace)
        rnum += 1
    if not special_level.custom_map:
        create_stairs(engine, dungeon, rooms, up_map)
    engine.total_levels += 1
    dungeon.rooms = rooms
    return dungeon


def generate_dungeon(max_rooms, room_min_size, room_max_size, map_width, map_height, player, engine, up_map):
    rooms = []
    dungeon = GameMap(map_width, map_height, {player}, engine.level+1)

    # set this so that spawned monsters can set it from engine
    engine.game_map = dungeon

    x_var = 20
    rm_starts = [[(3,3), (3+x_var,3+5)],
                 [(25,3), (25+x_var,3+5)],
                 [(55,3), (55+x_var,3+5)],
                 [(55,16), (55+x_var,16+5)],
                 [(25,16), (25+x_var,16+5)],
                 [(3,16), (3+x_var,16+5)],
                ]

    tun_locs = set()
    def adj(tun):
        """Adjacent to another tunnel."""
        for x,y in tun:
            intr = Loc(x,y).adj() & tun_locs
            if intr:
                return Loc(*tuple(intr)[0])
        return False

    rnum = 1
    for r in range(max_rooms):
        if random()>.9:
            continue
        room_width = randint(room_min_size, room_max_size)
        room_height = randint(room_min_size, room_max_size)

        c1, c2 = rm_starts[r]
        x = randint(c1[0], c2[0])
        y = randint(c1[1], c2[1])

        room_width = env(room_width, dungeon.width-x-1)
        room_height = env(room_height, dungeon.height-y-1)

        new_room = RectangularRoom(x, y, room_width, room_height)

        if any(new_room.intersects(other_room) for other_room in rooms):
            continue


        if not rooms:
            if engine.level==0:
                player.loc = copy(new_room.center)
        else:
            tun = None
            r1 = rooms[-1]
            r2 = new_room
            i1 = r1.interval_y()
            i2 = r2.interval_y()
            intr = i1.intersects_inner(i2)
            if not intr:
                tun = z_line(r1.center, r2.center)
                if adj(tun):
                    tun = l_line(r1.center, r2.center)
                    if adj(tun):
                        continue

            if not tun:
                i1 = r1.interval_x()
                i2 = r2.interval_x()
                intr2 = i1.intersects_inner(i2)

            if tun:
                pass
            elif intr:
                x1,x2 = r1.closest_x(r2)
                for n in range(50):
                    y = intr.random()
                    i = adj([(x1,y),(x2,y)])
                    if not i: break
                    if i.y>y: y-=1
                    if i.y<y: y+=1
                    i = adj([(x1,y),(x2,y)])
                    if not i: break
                else:
                    tun = z_line(r1.center, r2.center)
                    if adj(tun):
                        tun = l_line(r1.center, r2.center)
                        if adj(tun):
                            continue

                tun = tun or line(x1, x2, y=y)
            elif intr2:
                x = intr2.random()
                y1,y2 = r1.closest_y(r2)
                tun = line(y1, y2, x=x)
            if set(tun) & tun_locs:
                continue

            if random()>.5:
                for x,y in tun:
                    if x in (r1.x1, r1.x2) or y in (r1.y1,r1.y2):
                        d = entity.Door(engine, x, y)
                        if random()>.8:
                            d.locked = True
                        dungeon.entities.add(d)
                        break
            for x,y in tun:
                dungeon.tiles[x,y] = tile_types.floor
                tun_locs.add((x,y))
                r1walls = set(r1.walls())
                r2walls = set(r2.walls())
                l = Loc(x,y)
                if l in r1walls:
                    r1.entries.append(l)
                elif l in r2walls:
                    r2.entries.append(l)

        dungeon.tiles[new_room.inner] = tile_types.floor
        place_entities(new_room, dungeon, engine)
        rooms.append(new_room)


        cls = entity.special_data.get((engine.level,rnum))
        if cls:
            place_special(new_room, dungeon, engine, cls)
        place_vertical(new_room, dungeon, engine, entity.UndergroundSpace)
        rnum += 1

    create_stairs(engine, dungeon, rooms, up_map)
    engine.total_levels += 1
    dungeon.rooms = rooms
    hidden_room(dungeon, rooms, map_width, map_height)
    return dungeon

def create_stairs(engine, dungeon, rooms, up_map):
    locs = ()
    if engine.total_levels <= engine.max_levels:
        loc = loc2 = 0
        if random()>.1:
            for _ in range(50):
                r = choice(rooms)
                locs = r.inner2_locs()
                if locs:
                    loc = choice(locs)
                    if not dungeon.get_entities_at_loc(loc):
                        dungeon.tiles[loc.x, loc.y] = tile_types.down_stairs
                        break
        if not loc or random()>.1:
            for _ in range(50):
                r = choice(rooms)
                locs = list(set(r.inner2_locs()) - {loc})
                if locs:
                    loc2 = choice(locs)
                    if not dungeon.get_entities_at_loc(loc2):
                        dungeon.tiles[loc2.x, loc2.y] = tile_types.down_stairs
                        break
        locs = loc, loc2
        if loc and loc2:
            loc, loc2 = sorted(locs)
            dungeon.left, dungeon.right = Stairs(loc, down_dir='left'), Stairs(loc2, down_dir='right')
            print('placing left and right stairs')
        else:
            dir = choice(('left','right'))
            setattr(dungeon, dir, Stairs(loc or loc2, down_dir=dir))

    if engine.level > 0:
        for _ in range(50):
            r = choice(rooms)
            locs2 = list(set(r.inner2_locs()) - set(locs))
            if locs2:
                loc = choice(locs2)
                dungeon.tiles[loc.x, loc.y] = tile_types.up_stairs
                dungeon.up = Stairs(loc, above_loc=engine.player.loc, game_map=up_map)
                break
        else:
            raise Exception('No tile found for up_stairs')

def hidden_room_tunnel(dungeon, room):
    print("room", room)
    lst = dungeon.find_walkable(room.p1.mod(1,0), Loc(0,-1))
    if lst: return lst

    lst = dungeon.find_walkable(room.p1.mod(0,1), Loc(-1,0))
    if lst: return lst

    lst = dungeon.find_walkable(room.p2.mod(0,-1), Loc(1,0))
    if lst: return lst

    lst = dungeon.find_walkable(room.p2.mod(-1,0), Loc(0,1))
    if lst: return lst


def hidden_room(dungeon, rooms, map_width, map_height):
    # if not random()>.75:
        # return
    for _ in range(50):
        x,y = randint(3,map_width-3), randint(3,map_height-3)
        r = RectangularRoom(x, y, 3, 3)
        if any(r.intersects(_r) for _r in rooms):
            continue
        locs = r.locs()
        if not any(dungeon.walkable(l) for l in locs):
            lst = hidden_room_tunnel(dungeon, r)
            if not lst:
                continue

            for loc in lst[:-1]:
                dungeon.tiles[loc.x, loc.y] = tile_types.floor
            loc = lst[-1]
            dungeon.tiles[loc.x, loc.y] = tile_types.hidden_passage
            dungeon.hidden_rooms = [r]
            dungeon.hidden_tile = loc
            dungeon.tiles[r.inner] = tile_types.floor
            return r

def env(val, max, min=0):
    if val>max:
        val = max
    if val<min:
        val = min
    return val

def tunnel_between(start, end):
    x1, y1 = start
    x2, y2 = end
    if random() < 0.5:
        corner_x, corner_y = x2, y1

    else:
        corner_x, corner_y = x1, y2

    for t in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield t
    for t in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield t
