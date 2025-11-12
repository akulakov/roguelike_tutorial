import re
from random import shuffle, randint, random
import lzma, pickle
import tcod
import json
import binarytree
from tcod.map import compute_fov
from game_map import MessageLog, GameMap
from util import Loc
from actions import Impossible
import entity
from procgen import generate_dungeon, generate_special_dungeon
from input_handlers import EventHandler, MainMenu
import libtcodpy

screen_width = 80
screen_height = 50


class Engine:
    context = None
    console = None
    game_map = None
    event_handler = None
    total_levels = 0
    max_levels = 25

    def __init__(self, player):
        self.player = player
        self.messages = MessageLog()
        self.mouse_loc = Loc(0,0)
        self.level = 0
        n = list(range(1,100))
        shuffle(n)
        self.node_nums = n
        self.tree = binarytree.Node(self.node_nums.pop())
        self.cur_node = self.tree
        self.cur_node.parent = None
        self.specials = {}
        self.quests = {}
        self.custom_maps = {}

    def incomplete_nodes(self, node, lst):
        """Nodes that have stairs but respective game-maps were not yet generated."""
        if not node:
            return
        if node.left:
            self.incomplete_nodes(node.left.game_map, lst)
        if node.right:
            self.incomplete_nodes(node.right.game_map, lst)
        node.incomplete_left = node.incomplete_right = False
        if node.left and not node.left.game_map:
            node.incomplete_left = True
            lst.append(node)
        if node.right and not node.right.game_map:
            node.incomplete_right = True
            lst.append(node)

    def show_tree(self):
        s = str(self.tree)
        s = s.split('\n')
        s2 = []
        node = self.cur_node
        node_pat = r'[^\d]{}[^\d]'

        for l in s:
            l = ' '+l+' '
            mt = re.search(node_pat.format(node.value), l)
            if mt:
                l = [''] + list(l)
                l.extend(('',''))
                try: l[mt.start()+1] = '*'
                except IndexError: pass
                try: l[mt.end()] = '*'
                except IndexError: pass
                l = ''.join(l)
            s2.append(l)

        incomplete = []
        self.incomplete_nodes(self.root_map, incomplete)
        incomplete = set(incomplete)
        incomplete_nodes = []
        for n in list(self.tree):
            if n.game_map in incomplete:
                incomplete_nodes.append(n)
        for n, l in enumerate(s2):
            for node in incomplete_nodes:
                mt = re.search(node_pat.format(node.value), l)
                if mt:
                    s = s2[n+1] + ' '*100
                    s = list(s)
                    f = mt.start()+1
                    if node.game_map.incomplete_left:
                        if s[f] == ' ':
                            s[f] = '/'
                        elif s[f-1]==' ':
                            s[f-1] = '/'
                    if node.game_map.incomplete_right:
                        if s[f] == ' ':
                            s[f] = '\\'
                        elif s[f+1]==' ':
                            s[f+1] = '\\'

                    s = ''.join(s).rstrip()
                    s2[n+1] = s

        return s2

    def down(self):
        self.level += 1     # new_map depends on this
        m = self.game_map
        st = m.get_down_map(self.player.loc)
        if st.game_map:
            m = st.game_map
            self.cur_node = getattr(self.cur_node, st.down_dir)
        else:
            m = st.game_map = new_map(self, self.player, m)
            node = binarytree.Node(self.node_nums.pop())
            setattr(self.cur_node, st.down_dir, node)
            node.parent = self.cur_node
            self.cur_node = node

        self.player.loc = m.up.loc
        self.game_map = self.cur_node.game_map = m
        self.show_tree()

    def up(self):
        self.level -= 1
        up = self.game_map.up
        self.game_map = self.game_map.up.game_map
        self.event_handler.game_map = self.game_map
        self.player.loc = up.above_loc
        self.cur_node = self.cur_node.parent
        self.show_tree()

    def handle_enemy_turns(self):
        for e in self.game_map.entities.copy():
            if not isinstance(e, entity.Living):
                continue
            if e.levitating:
                e.levitating -= 1
                if not e.levitating:
                    e.vloc = 0
                    self.messages.add(f'{e} floats down')

            if e.asleep > 0:
                e.asleep -= 1
                if not e.asleep:
                    self.messages.add(f'{e} wakes up')

            if e.blinded > 0:
                e.blinded -= 1
                if not e.blinded:
                    self.messages.add(f'{e} can see again')

            if e.paralized > 0:
                e.paralized -= 1
                if not e.paralized:
                    self.messages.add(f'{e} can move again')

            if e.poisoned > 0:
                e.poisoned -= 1
                dmg = randint(2,6)
                e.fighter.take_damage(dmg)
                self.messages.add(f'{e} takes {dmg}hp damage from poison')
                if random()>0.999:
                    self.messages.add(f'{e} dies of poison')
                    e.fighter.die()
                if not e.poisoned and e.is_alive:
                    self.messages.add(f'{e} feels better')

            if e.turning_to_stone > 0:
                e.turning_to_stone -= 1
                if e.turning_to_stone:
                    self.messages.add(f'{e} is turning to stone ...')
                else:
                    self.messages.add(f'{e} is now STONE ...')
                    e.fighter.die()

        for e in self.game_map.entities - {self.player}:
            if e.is_hostile and e.asleep==0 and e.paralized==0:
                a = e.attack(self.player)
                if a:
                    try:
                        a.perform()
                    except Impossible:
                        pass

    def update_fov(self):
        """Recompute the visible area based on the players point of view."""
        loc = self.player.loc
        self.game_map.visible[:] = compute_fov(self.game_map.tiles["transparent"], loc, radius=8, algorithm=libtcodpy.FOV_SYMMETRIC_SHADOWCAST)
        self.game_map.explored |= self.game_map.visible

    def render(self, console=None, context=None):
        console = console or self.console
        context = context or self.context
        if self.game_map:
            self.game_map.render(self, console)
        self.event_handler.on_render(console)
        context.present(console)
        console.clear()

    def print(self, x, y, text, color):
        console = self.console
        context = self.context
        if self.game_map:
            self.game_map.render(self, console)
        console.print(x,y,text,fg=color)
        context.present(console)
        console.clear()

    def save_as(self, filename, maps_filename):
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)
        d = {}
        for n, map in self.custom_maps.items():
            d[n] = map.serialize()
        with open(maps_filename, "w") as f:
            f.write(json.dumps(d))

    def load_custom_maps(self, data):
        d = {}
        for n, jdata in data.items():
            d[n] = GameMap.load(jdata)
        return d


def start():
    tileset = tcod.tileset.load_tilesheet( "dejavu10x10_gs_tc.png", 32, 8, tcod.tileset.CHARMAP_TCOD)
    player = entity.Player(None, int(screen_width / 2), int(screen_height / 2))
    engine = Engine(player=player)
    MainMenu(engine)
    return engine, screen_width, screen_height, tileset

def new_game(maps_filename):
    """Return a brand new game session as an Engine instance."""
    tileset = tcod.tileset.load_tilesheet( "dejavu10x10_gs_tc.png", 32, 8, tcod.tileset.CHARMAP_TCOD)
    player = entity.Player(None, int(screen_width / 2), int(screen_height / 2))
    engine = Engine(player=player)
    game_map = new_map(engine, player)
    engine.game_map = game_map
    engine.cur_node.game_map = engine.root_map = game_map
    player.add_engine(engine)
    player.inventory.add(entity.FireballScroll(engine))
    player.inventory.add(entity.EyeOfIceScroll(engine))
    player.inventory.add(entity.Sword(engine, entity=player))
    player.inventory.add(entity.LeatherArmor(engine, entity=player))
    player.inventory.add(entity.Abacus(engine, entity=player))
    player.inventory.add(entity.Key(engine, entity=player))
    player.inventory.add(entity.LightningScroll(engine))
    player.inventory.add(entity.LevitationScroll(engine))
    player.inventory.add(entity.AuspiciousRoomScroll(engine))
    player.inventory.add(entity.MagicMissileScroll(engine))
    player.inventory.add(entity.Pickaxe(engine, entity=player))
    player.inventory.add(entity.SwordOfRingingBell(engine, entity=player))
    EventHandler(engine)
    engine.update_fov()
    with open(maps_filename, 'r') as f:
        engine.custom_maps = engine.load_custom_maps(json.loads(f.read()))
    return engine, screen_width, screen_height, tileset

def new_map(engine, player, up_map=None):
    map_width = 80
    map_height = screen_height - 5
    room_max_size = 10
    room_min_size = 6
    max_rooms = 5
    level = engine.level + 1
    special_levels = entity.special_data.levels.get(level) or ()
    if special_levels:
        shuffle(special_levels)
    special = False
    for special_level in special_levels:
        if special_level.id not in engine.specials:
            dungeon = generate_special_dungeon(max_rooms, room_min_size, room_max_size, map_width, map_height, player, engine, up_map, special_level)
            engine.specials[special_level.id] = dungeon
            special = True
            break
    if not special:
        dungeon = generate_dungeon(max_rooms, room_min_size, room_max_size, map_width, map_height, player, engine, up_map)
    return dungeon

def load_game(filename, maps_filename):
    with open(filename, 'rb') as f:
        engine = pickle.loads(lzma.decompress(f.read()))
    assert isinstance(engine, Engine)
    with open(maps_filename, 'r') as f:
        engine.custom_maps = engine.load_custom_maps(json.loads(f.read()))
        print("engine.custom_maps", list(engine.custom_maps))
    # engine.player.blinded = 3
    p = engine.player
    p.inventory.add(entity.RingOfFreeAction(engine, entity=p))
    return engine
