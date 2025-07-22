import textwrap
import numpy as np  # type: ignore

import tile_types
from util import Loc

class Color:
    white = (0xFF, 0xFF, 0xFF)
    black = (0x0, 0x0, 0x0)
    yellow = (0xFF, 0xFF, 0x0)

    player_atk = (0xE0, 0xE0, 0xE0)
    enemy_atk = (0xFF, 0xC0, 0xC0)

    player_die = (0xFF, 0x30, 0x30)
    enemy_die = (0xFF, 0xA0, 0x30)

    welcome_text = (0x20, 0xA0, 0xFF)

    bar_text = white
    bar_filled = (0x0, 0x60, 0x0)
    bar_empty = (0x40, 0x10, 0x10)

    invalid = (0xFF, 0xFF, 0x00)
    impossible = (0x80, 0x80, 0x80)
    error = (0xFF, 0x40, 0x40)

    health_recovered = (0x0, 0xFF, 0x0)
    red = (0xFF, 0x0, 0x0)

    needs_target = (0x3F, 0xFF, 0xFF)
    status_effect_applied = (0x3F, 0xFF, 0x3F)
    menu_title = (255, 255, 63)
    menu_text = white
    descend = (0x9F, 0x3F, 0xFF)

class Stairs:
    def __init__(self, loc, above_loc=None, down_dir=None, game_map=None):
        self.loc = loc
        self.above_loc = above_loc
        self.down_dir = down_dir
        self.game_map = game_map

    def __repr__(self):
        return f'<{self.game_map}, {self.loc}>'

class GameMap:
    up = None
    left = None
    right = None
    level = None
    rooms = None
    hidden_rooms = None
    reveal = False

    def __init__(self, width, height, entities, level, up_map=None):
        self.level = level
        self.entities = entities
        self.width, self.height = width, height
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")
        self.visible = np.full((width, height), fill_value=False, order="F")
        self.explored = np.full((width, height), fill_value=False, order="F")

    def make_turn(self):
        for r in self.rooms:
            r.auspicious = max(0, r.auspicious-1)

    def auspicious_rooms(self):
        return [r for r in self.rooms if r.auspicious]

    def find_room(self, loc):
        for r in self.rooms:
            p1,p2 = r.p1, r.p2
            if p1.x<=loc.x<=p2.x and p1.y<=loc.y<=p2.y:
                return r

    def get_down_map(self, loc):
        return self.left if self.left and loc==self.left.loc else self.right

    def render_names_at_location(self, console, loc, r_loc):
       if not self.in_bounds(loc) or not self.visible[loc.x, loc.y]:
           return ''

       names = ', '.join( e.name for e in self.entities if e.loc==loc)
       names = names.capitalize()
       console.print(x=r_loc.x, y=r_loc.y, string=names)

    def names_at_loc(self, loc, exclude=()):
       names = ', '.join( e.name for e in self.entities if e.loc==loc and e not in exclude)
       return names.capitalize()

    def place(self, item, loc=None):
        self.entities.add(item)
        if loc:
            item.loc = loc

    def get_blocking_entity_at_loc(self, loc):
        for entity in self.entities:
            if entity.blocking and entity.loc==loc:
                return entity

    def get_entities_at_loc(self, loc):
        return [e for e in self.entities if e.loc==loc]

    def get_living_at_locs(self, locs):
        locs = set(locs)
        l = []
        for entity in self.entities:
            if entity.is_alive and entity.loc in locs:
                l.append(entity)
        return l

    def get_living_at_loc(self, loc):
        for entity in self.entities:
            if entity.is_alive and entity.loc==loc:
                return entity

    def living(self):
        yield from (e for e in self.entities if e.is_alive)

    def items(self, filter=object):
        from entity import Item
        yield from (e for e in self.entities if isinstance(e, Item) and isinstance(e, filter))

    def item(self, loc, filter=object):
        it = self.items(filter)
        # for i in it:
            # print("i.loc", i.loc)
        l = [i for i in it if i.loc==loc]
        if l:
            return l[0]

    def entity(self, loc, filter=object):
        l = [e for e in self.entities if isinstance(e, filter) and e.loc==loc]
        if l:
            return l[0]

    def in_bounds(self, loc):
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= loc.x < self.width and 0 <= loc.y < self.height

    def empty_lst(self, locs):
        return [l for l in locs if self.empty(l)]

    def empty_lst_bool(self, locs):
        return [self.empty(l) for l in locs]

    def walkable(self, loc):
        return self.tiles['walkable'][loc.x, loc.y]

    def empty(self, loc):
        if not self.in_bounds(loc):
            return False
        if not self.tiles['walkable'][loc.x, loc.y]:
            return False
        if self.get_blocking_entity_at_loc(loc):
            return False
        return True

    def render(self, engine, console):
        if self.reveal:
            self.visible = np.full((self.width, self.height), fill_value=True, order='F')
        console.rgb[0:self.width, 0:self.height] = np.select(
            condlist=[self.visible, self.explored],
            choicelist=[self.tiles['light'], self.tiles['dark']],
            default=tile_types.SHROUD
        )

        for entity in sorted( self.entities, key=lambda x: x.render_order):
            loc = entity.loc
            if self.visible[loc.x, loc.y]:
                console.print(x=loc.x, y=loc.y, string=entity.char, fg=entity.color)

        f = engine.player.fighter
        console.print(x=0, y=45, string=f'[{engine.level+1:-2}]', fg=Color.white)
        self.render_bar(console, f.hp, f.max_hp, 20)
        self.render_names_at_location(console, engine.mouse_loc, Loc(21,44))
        engine.messages.render(console, 21, 45, 40, 5)
        console.print( x=1, y=47, string=f'{engine.player.loc}')

    def render_bar(self, console, current_value, maximum_value, total_width):
        bar_width = int(float(current_value) / maximum_value * total_width)

        console.draw_rect(x=0, y=46, width=total_width, height=1, ch=1, bg=Color.bar_empty)

        if bar_width > 0:
            console.draw_rect( x=0, y=46, width=bar_width, height=1, ch=1, bg=Color.bar_filled)

        console.print( x=1, y=46, string=f"HP: {current_value}/{maximum_value}", fg=Color.bar_text)

    def find_walkable(self, loc, dir):
        l = [loc]
        for _ in range(100):
            loc = loc.mod(dir.x, dir.y)
            if not self.in_bounds(loc):
                return
            if self.walkable(loc):
                return l
            l.append(loc)


class Message:
    def __init__(self, text, fg):
        self.plain_text = text
        self.fg = fg
        self.count = 1

    @property
    def full_text(self):
        """The full text of this message, including the count if necessary."""
        if self.count > 1:
            return f"{self.plain_text} (x{self.count})"
        return self.plain_text


class MessageLog:
    def __init__(self):
        self.messages = []

    def add(self, text, fg=Color.white, stack=True, dedupe=False):
        """ If `stack` is True then the message can stack with a previous message of the same text
        `dedupe`=True - do not add if previous msg is the same as current
        """
        if dedupe and self.messages and text == self.messages[-1].plain_text:
            pass
        elif stack and self.messages and text == self.messages[-1].plain_text:
            self.messages[-1].count += 1
        else:
            self.messages.append(Message(text, fg))

    def wrap(self, string, width):
        for line in string.splitlines():
            yield from textwrap.wrap( line, width, expand_tabs=True)

    def render(self, console, x, y, width, height, msgs=None):
        """ `x`, `y`, `width`, `height` is the rectangular region to render onto the `console`."""
        msgs = msgs or self.messages
        self.render_messages(console, x, y, width, height, self.messages)

    def render_messages(self, console, x, y, width, height, messages):
        y_offset = height - 1

        for message in reversed(messages):
            for line in reversed(list(self.wrap(message.full_text, width))):
                console.print(x=x, y=y + y_offset, string=line, fg=message.fg)
                y_offset -= 1
                if y_offset < 0:
                    return
