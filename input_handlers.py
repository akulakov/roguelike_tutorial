from copy import deepcopy
from random import random, randint
from textwrap import wrap
from itertools import compress
import traceback
import tcod.event
from tcod import libtcodpy

import constants
from actions import BumpAction, WaitAction, MovementAction, PickupAction, Impossible, DropItem
from util import Loc
from game_map import Color
import tile_types

dir_keys_cardinal = dict(
    h=(-1,0), j=(0,1), k=(0,-1), l=(1,0)
)

dir_keys = dict(dir_keys_cardinal,
    y=(-1,-1), u=(1,-1), b=(-1,1), n=(1,1),
)

CONFIRM_KEYS = {
   tcod.event.KeySym.RETURN,
   tcod.event.KeySym.KP_ENTER,
}


class EventHandler(tcod.event.EventDispatch):
    go = False
    cursor = None

    def __init__(self, engine, *a, **kw):
        self.engine = engine
        self.player = engine.player
        self.game_map = engine.game_map
        engine.event_handler = self
        super().__init__(*a, **kw)

    def ev_quit(self, event):
        raise SystemExit()

    def ev_keydown(self, event):
        action = None
        key = event.sym
        keys = tcod.event.KeySym
        engine = self.engine
        self.game_map = engine.game_map
        Shift = event.mod & tcod.event.Modifier.SHIFT

        if not Shift:
            for k in dir_keys:
                if key==getattr(keys, k):
                    mod = Loc(*dir_keys[k])
                    if self.go:
                        mod = self.fast_go(mod)
                    action = BumpAction(mod)

        self.go = False
        import entity

        if key == keys.ESCAPE:
            engine.context = None  # tcod context cannot be pickled
            engine.game_map.cursor = None   # EDITOR cursor
            self.save_game('game.sav', 'custom_maps.dat')
            raise SystemExit()

        if not self.player.is_alive:
            return WaitAction()
        if self.player.asleep>0 or self.player.paralized>0:
            engine.messages.add('You are unable to move')
            return WaitAction()

        if key == keys.g:
            self.go = True
        elif key == keys.PERIOD and Shift:
            m = self.game_map
            stairs = tuple(filter(None, (m.left, m.right)))
            if self.player.loc in (s.loc for s in stairs):
                self.engine.down()
        elif key == keys.COMMA and Shift:
            if self.player.loc == self.game_map.up.loc:
                self.engine.up()
        elif key == keys.e and Shift and constants.DEBUG:
            # EDITOR
            self.game_map.cursor = engine.player.loc
            engine.event_handler = MapEditorHandler(self.engine)
        elif key == keys.w and Shift and constants.DEBUG:

            self.write_custom_map()

        elif key == keys.s and Shift:
            for l in self.player.loc.adj():
                if self.game_map.tiles[l] == tile_types.hidden_passage:
                    self.game_map.tiles[l] = tile_types.floor
            else:
                engine.messages.add('You do not find anything hidden.')

        elif key == keys.PERIOD:
            action = WaitAction()

        # TALK
        elif key == keys.SPACE:
            for l in self.player.loc.adj():
                e = self.game_map.get_living_at_loc(l)
                if e:
                    conv = entity.special_data.conversations.get(e.id)
                    quest = engine.quests.get(e.id)
                    if not quest:
                        Q = entity.special_data.quests.get(e.id)
                        if Q:
                            quest = Q(engine, e)
                    if quest:
                        engine.quests[e.id] = quest
                    if conv and conv.condition in self.player.inventory:
                        self.engine.event_handler = ConversationHandler(self, conv, self.engine)
                        break
                    elif quest and quest.condition() and not quest.completed:
                        quest.advance()
                        if quest.conv:
                            self.engine.event_handler = ConversationHandler(self, quest.conv, self.engine, on_yes=quest.start)
                        else:
                            engine.messages.add(f'{quest.entity} ignores you')
                        break
            else:
                engine.messages.add('So boring, no-one to talk to..')

        elif key == keys.v:
            self.engine.event_handler = HistoryViewer(self.engine)

        elif key == keys.N3 and Shift:
            self.engine.event_handler = HashCommandHandler(self.engine)

        elif key == keys.m:
            self.engine.event_handler = MapViewer(self.engine)
        elif key == keys.c:
            self.engine.event_handler = CharacterScreenEventHandler(self.engine)
        elif key == keys.i:
            self.engine.event_handler = InventoryActivateHandler(self.engine)

        elif key == keys.d and Shift:
            p = self.player
            usp = self.game_map.entity(p.loc, entity.UndergroundSpace)
            if not isinstance(p.equipment.tool, entity.Pickaxe):
                self.engine.messages.add('Nothing to dig with!')
            elif not usp:
                self.engine.messages.add('You do not find anything')
            else:
                self.engine.event_handler = UndergroundSpaceHandler(usp, self.engine)

        # OPEN DOORS / BOXES
        elif key == keys.o:
            box = self.game_map.item(self.player.loc, entity.Box)
            if box:
                ok = False
                if box.locked:
                    k = self.player.inventory.get(entity.Key)
                    if k:
                        box.locked = False
                        self.player.inventory.remove(k)
                        ok = True
                    else:
                        self.engine.messages.add('The box is locked.')
                else:
                    ok = True
                if ok:
                    self.engine.event_handler = BoxHandler(box, self.engine)
            else:
                for l in self.player.loc.adj():
                    door = self.game_map.entity(l, entity.Door)
                    if door:
                        if door.locked:
                            k = self.player.inventory.get(entity.Key)
                            if k:
                                door.locked = False
                                self.player.inventory.remove(k)
                            self.engine.messages.add('The door is locked.')

                        door.toggle()
                        break
                else:
                    self.engine.messages.add('Nothing to open here..')

        elif key == keys.SLASH:
            self.engine.event_handler = LookHandler(self.engine)
        elif key == keys.COMMA:
            l = engine.game_map.get_entities_at_loc(self.engine.player.loc)
            l = [i for i in l if isinstance(i, entity.Item)]
            if not l:
                engine.messages.add('Nothing to pick up..')
            elif len(l)==1:
                action = PickupAction()
            else:
                self.engine.event_handler = PickupEventHandler(self.engine)
        elif key == keys.d:
            self.engine.event_handler = InventoryDropHandler(self.engine)
        elif key == keys.q and Shift:
            self.engine.event_handler = QuestsHandler(self.engine)
        elif key == keys.r and Shift and constants.DEBUG:
            self.game_map.reveal = not self.game_map.reveal
        elif key == keys.s:
            for l in self.player.loc.adj():
                e = self.game_map.get_living_at_loc(l)
                if e and e.is_seller:
                    self.engine.event_handler = ShopEventHandler(e, self.engine)

        if action:
            action.init(engine, self.player)

        if self.player.level.requires_level_up:
            engine.event_handler = LevelUpEventHandler(engine)

        return action

    def write_custom_map(self):
        self.engine.event_handler = TextInputHandler(self.engine, callback=self._write_custom_map)

    def _write_custom_map(self, name):
        if not name.strip():
            return
        gm = self.game_map

        ent = gm.entities
        up = gm.up
        if gm.up:
            gm.up.game_map = None
        gm.entities = None
        gm = deepcopy(gm)
        # map.up.game_map = map.up.above_loc = None
        gm.entities = set()
        self.engine.custom_maps[name] = gm

        # restore current map
        gm = self.game_map
        gm.entities = ent
        gm.up = up
        print('custom maps:')
        for n in self.engine.custom_maps:
            print(n)

    def save_game(self, filename, maps_filename):
        self.engine.save_as(filename, maps_filename)
        print("Game saved.")

    def ev_mousemotion(self, event):
        self.engine.context.convert_event(event)
        l = Loc(*event.tile)
        map = self.engine.game_map
        if map and map.in_bounds(l):
            self.engine.mouse_loc = l

    def fast_go(self, mod):
        for _ in range(100):
            a = MovementAction(mod)
            a.init(self.engine, self.player)
            ok = True
            try: a.perform()
            except Impossible:
                ok = False
            loc = self.player.loc
            mods = mod.perpendicular_dirs(mod)
            locs = [loc+m for m in mods]
            locs_e = self.game_map.empty_lst_bool(locs)
            if not ok and sum(locs_e)==1:
                # change direction
                mod = list(compress(mods, locs_e))[0]
            elif not ok or sum(locs_e)==2:
                # open area, stop
                break

            self.engine.handle_enemy_turns()
            self.engine.update_fov()
            self.engine.render()
        return mod

    def on_render(self, console):
        pass

class MapEditorHandler(EventHandler):
    def ev_keydown(self, event):
        key = event.sym
        keys = tcod.event.KeySym
        engine = self.engine
        game_map = self.game_map = engine.game_map
        Shift = event.mod & tcod.event.Modifier.SHIFT
        c = self.game_map.cursor

        if not Shift:
            for k in dir_keys:
                if key==getattr(keys, k):
                    mod = Loc(*dir_keys[k])
                    self.game_map.cursor = self.game_map.cursor.mod(*mod)

        if key==keys.w:
            self.game_map.tiles[c.x,c.y] = tile_types.wall
        elif key==keys.x:
            self.game_map.tiles[c.x,c.y] = tile_types.floor
        elif key==keys.e or key==keys.ESCAPE:
            self.game_map.cursor = None
            self.engine.event_handler = EventHandler(self.engine)
        elif key==keys.f:
            for x in range(80):
                for y in range(45):
                    game_map.tiles[x,y] = tile_types.wall if Shift else tile_types.floor
        elif key==keys.r:
            self.engine.event_handler = TextInputHandler(self.engine, callback=self.make_room, prompt='enter width height > ')
        elif key==keys.l and Shift:
            self.engine.event_handler = TextInputHandler(self.engine, callback=self.make_line, prompt='enter dir[hjkl] length > ')

    def make_room(self, txt):
        c = self.game_map.cursor
        map = self.game_map
        try:
            w,h=txt.split()
            w,h = int(w), int(h)
            for x in range(c.x, c.x+w):
                for y in range(c.y, c.y+h):
                    map.tiles[x,y] = tile_types.floor
        except Exception as e:
            print(e)
            self.engine.messages.add('wrong input..')
        self.engine.event_handler = MapEditorHandler(self.engine)

    def make_line(self, txt):
        c = self.game_map.cursor
        map = self.game_map
        try:
            d,l=txt.split()
            d,l = d, int(l)
            for _ in range(l):
                map.tiles[c.x,c.y] = tile_types.floor
                c = c.mod(*dir_keys_cardinal[d])
        except Exception as e:
            print(e)
            self.engine.messages.add('wrong input..')
        self.engine.event_handler = MapEditorHandler(self.engine)

CURSOR_Y_KEYS = {
    tcod.event.KeySym.UP: -1,
    tcod.event.KeySym.DOWN: 1,
    tcod.event.KeySym.PAGEUP: -10,
    tcod.event.KeySym.PAGEDOWN: 10,
}

class MapViewer(EventHandler):
    def on_render(self, console):
        super().on_render(console)  # Draw the main state as the background.
        lines = self.engine.show_tree()
        con = tcod.console.Console(console.width - 6, console.height - 6)
        con.draw_frame(0, 0, con.width, con.height)
        con.print_box( 0, 0, con.width, 1, "┤MAP├", alignment=libtcodpy.CENTER)
        y = 1
        h = self.engine.game_map.height-1

        if len(lines)>h:
            for n,l in enumerate(lines):
                if '*' in l:
                    break

            st = max(0, n-h//2)
            lines = lines[st:n+h//2]

        for n, l in enumerate(lines):
            l = l[:self.engine.game_map.width-4]
            if '*' in l:
                a,b,c = l.split('*')
                con.print(x=3, y=y+n, string=a + '*')
                con.print(x=3 + len(a)+1, y=y+n, string=b, bg=Color.yellow, fg=Color.black)
                con.print(x=3 + len(a)+len(b)+1, y=y+n, string='*'+c)
            else:
                con.print(x=3, y=y+n, string=l[:self.engine.game_map.width-4])
        con.blit(console, 3, 3)

    def ev_keydown(self, event):
        self.engine.event_handler = EventHandler(self.engine)

class HistoryViewer(EventHandler):
    def __init__(self, engine):
        super().__init__(engine)
        self.log_length = len(engine.messages.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console):
        super().on_render(console)  # Draw the main state as the background.

        log_console = tcod.console.Console(console.width - 6, console.height - 6)

        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box( 0, 0, log_console.width, 1, "┤Message history├", alignment=libtcodpy.CENTER)

        self.engine.messages.render( log_console, 1, 1, log_console.width - 2, log_console.height - 2,
            self.engine.messages.messages[: self.cursor + 1])
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event):
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == tcod.event.KeySym.HOME:
            self.cursor = 0
        elif event.sym == tcod.event.KeySym.END:
            self.cursor = self.log_length - 1
        else:  # Any other key moves back to the main game state.
            self.engine.event_handler = EventHandler(self.engine)

class TextInputHandler(EventHandler):
    def __init__(self, *a, callback=None, prompt='> ', **kw):
        self.cmd = ''
        self.callback = callback
        self.prompt = prompt
        super().__init__(*a, **kw)

    def on_render(self, console):
        console.print(15, 35, self.prompt + self.cmd)
        super().on_render(console)

    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        key = event.sym
        if key==keys.RETURN:
            if self.callback:
                self.callback(self.cmd)
            self.engine.event_handler = EventHandler(self.engine)
            return
        else:
            try:
                self.cmd += chr(key.value)
            except ValueError:
                pass

class HashCommandHandler(EventHandler):
    def __init__(self, *a, **kw):
        self.cmd = ''
        super().__init__(*a, **kw)

    def on_render(self, console):
        console.print(15, 35, '# ' + self.cmd)
        super().on_render(console)

    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        key = event.sym
        # import pdb;pdb.set_trace()
        if key==keys.RETURN:
            if self.cmd == 'break':
                self.engine.event_handler = InventoryBreakHandler(self.engine)
            elif self.cmd == 'kick':
                self.engine.event_handler = KickHandler(self.engine)
            else:
                self.engine.messages.add('Unknown command')
                self.engine.event_handler = EventHandler(self.engine)
        else:
            self.cmd += chr(key.value)

class AskUserEventHandler(EventHandler):
    def handle_action(self, action):
        """Return to the main event handler when a valid action was performed."""
        if super().handle_action(action):
            self.engine.event_handler = EventHandler(self.engine)
            return True
        return False

    def ev_keydown(self, event):
        """By default any key exits this input handler."""
        if event.sym in {
            tcod.event.KeySym.LSHIFT,
            tcod.event.KeySym.RSHIFT,
            tcod.event.KeySym.LCTRL,
            tcod.event.KeySym.RCTRL,
            tcod.event.KeySym.LALT,
            tcod.event.KeySym.RALT,
        }:
            return None
        return self.on_exit()

    def ev_mousebuttondown(self, event):
        """By default any mouse click exits this input handler."""
        return self.on_exit()

    def on_exit(self):
        self.engine.event_handler = EventHandler(self.engine)

class InventoryEventHandler(AskUserEventHandler):
    title = "Inventory"
    is_inventory = True

    def get_items(self):
        return self.engine.player.inventory.items

    def on_render(self, console):
        super().on_render(console)
        num_items = len(self.get_items())
        height = num_items + 2

        if height <= 3:
            height = 3

        if self.engine.player.loc.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        width = len(self.title) + 25
        console.draw_frame(x=x, y=y, width=width, height=height, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))

        if num_items > 0:
            for i, item in enumerate(self.get_items()):
                item_key = chr(ord('a') + i)
                is_equipped = ''
                if self.is_inventory:
                    is_equipped = self.engine.player.equipment.item_is_equipped(item)
                    is_equipped = ' (E)' if is_equipped else ''
                console.print(x + 1, y + i + 1, f'({item_key}) {item}{is_equipped}')
        else:
            console.print(x + 1, y + 1, '(Empty)')

    def ev_keydown(self, event):
        key = event.sym
        index = key - tcod.event.KeySym.a

        if 0 <= index <= 26:
            try:
                selected_item = self.get_items()[index]
            except IndexError:
                self.engine.messages.add('Invalid entry.', Color.invalid)
                return
            try:
                return self.on_item_selected(selected_item)
            except Impossible as e:
                self.engine.messages.add(e.args[0], Color.impossible)
        return super().ev_keydown(event)

class PickupEventHandler(InventoryEventHandler):
    title = 'Ground'
    is_inventory = False

    def get_items(self):
        l = self.engine.game_map.get_entities_at_loc(self.engine.player.loc)
        import entity
        return [i for i in l if isinstance(i, entity.Item)]

    def on_item_selected(self, item):
        self.engine.player.inventory.add(item)
        self.engine.game_map.entities.remove(item)

class TransferBetweenInventoriesHandler(AskUserEventHandler):
    page = 0
    maxpage = 0

    def __init__(self, other, *a, **kw):
        """
        other: shop seller, container, etc
        """
        self.other = other
        super().__init__(*a, **kw)

    def on_render(self, console):
        super().on_render(console)
        pl_inv = self.engine.player.inventory.items
        other_inv = self.other.inventory.items
        other_num = len(other_inv)
        number_of_items_in_inventory = len(pl_inv)

        height = max(other_num, number_of_items_in_inventory) + 5
        size = height - 4
        self.maxpage = max(other_num, number_of_items_in_inventory) % size + 1

        if height <= 3:
            height = 3

        x,y=0,0

        console.draw_frame(x=x, y=y, width=78, height=height, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))

        player = self.engine.player
        y+=1
        p_gold = str(player.gold)
        if self.is_shop:
            console.print(x+1, y, f'${p_gold:35s} ${self.other.gold}')
        y+=1
        eqp = self.engine.player.equipment

        st = self.page * size
        self.pl_inv = pl_inv[st:st+size]

        i = -1
        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.pl_inv):
                if not eqp.item_is_equipped(item):
                    item_key = chr(ord('a') + i)
                    txt = f'({item_key}) {item}'
                    txt = (txt + ' '*30)[:30]
                    if self.is_shop:
                        price = int(round(item.base_price*.9))
                        txt = txt + '{:02}'.format(price)
                    console.print(x + 1, y + i + 1, txt)
        else:
            console.print(x + 1, y + 1, '(Empty)')

        self.other_inv = other_inv[st:st+size]
        last_ind = i+1
        if other_num > 0:
            for i, item in enumerate(self.other_inv):
                item_key = chr(ord('a') + i + last_ind)
                txt = f'({item_key}) {item}'
                txt = (txt + ' '*30)[:30]
                if self.is_shop:
                    price = int(round(item.base_price*1.1))
                    txt = txt + '{:02}'.format(price)
                console.print(x + 36, y + i + 1, txt)
        else:
            console.print(x + 36, y + 1, '(Empty)')

    def ev_keydown(self, event):
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.KeySym.a
        other = self.other
        keys = tcod.event.KeySym

        def check_gold(entity, price):
            gold = getattr(entity, 'gold', 0)
            return not self.is_shop or gold>=price

        def money_transfer(from_, to, amt):
            if self.is_shop:
                from_.gold -= amt
                to.gold += amt

        if key == keys.PAGEUP:
            self.page = max(0, self.page-1)
            return
        elif key == keys.PAGEDOWN:
            self.page = min(self.maxpage, self.page+1)
            return

        elif 0 <= index <= 26:
            try:
                item = (self.pl_inv + self.other_inv)[index]

                if index<len(self.pl_inv):
                    price = int(round(item.base_price*.9))
                    if check_gold(self.other, price):
                        player.inventory.remove(item)
                        other.inventory.add(item)
                        money_transfer(other, player, price)
                else:
                    price = int(round(item.base_price*1.1))
                    if check_gold(self.player, price):
                        player.inventory.add(item)
                        other.inventory.remove(item)
                        money_transfer(player, other, price)

            except IndexError:
                self.engine.messages.add('Invalid entry.', Color.invalid)
                return
            try:
                return
                # return self.on_item_selected(item)
            except Impossible as e:
                self.engine.messages.add(e.args[0], Color.impossible)
        return super().ev_keydown(event)

class ShopEventHandler(TransferBetweenInventoriesHandler):
    title = 'Shop'
    is_shop = True

class BoxHandler(TransferBetweenInventoriesHandler):
    title = 'Box'
    is_shop = False

class UndergroundSpaceHandler(TransferBetweenInventoriesHandler):
    title = 'Underground'
    is_shop = False

class InventoryActivateHandler(InventoryEventHandler):
   title = 'Select an item to use'
   action = 'activate'

   def on_item_selected(self, item):
       m = getattr(item, self.action, None)
       if not m:
           self.engine.messages.add('This action cannot be used on this item')
       else:
           m()
       import entity
       if isinstance(item, entity.Note):
           self.engine.event_handler = PopupMessage(self, item.text, self.engine)

class InventoryBreakHandler(InventoryActivateHandler):
    title = 'Select an item to break'
    action = 'break_'

class InventoryDropHandler(InventoryEventHandler):
   title = 'Select an item to drop'
   def on_item_selected(self, item):
       a = DropItem()
       a.init(self.engine, self.engine.player, item=item)
       return a

class DirectionHandler(EventHandler):
    def __init__(self, *a, callback=None, **kw):
        self.callback = callback
        super().__init__(*a, **kw)

    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        for k in dir_keys_cardinal:
            if event.sym==getattr(keys, k):
                self.callback(dir_keys_cardinal[k])
                self.engine.event_handler = EventHandler(self.engine)
                break
        else:
            if event.sym==keys.ESCAPE:
                self.engine.event_handler = EventHandler(self.engine)
            else:
                self.engine.messages.add('Pick a direction [hjkl]')

class KickHandler(EventHandler):
    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        for k in dir_keys:
            if event.sym==getattr(keys, k):
                loc = self.engine.player.loc.mod(*dir_keys[k])
                from entity import Door, Box
                ent = self.engine.game_map.entity(loc, (Door, Box))
                dmg = 0
                if ent:
                    if random()>.5:
                        self.engine.messages.add(f'{ent.__class__.__name__} holds')

                    elif isinstance(ent, Door):
                        self.engine.messages.add('Door breaks')
                        self.engine.game_map.entities.remove(ent)
                        if random()>.6:
                            dmg = randint(6,25)
                            self.engine.player.fighter.take_damage(dmg)

                    elif isinstance(ent, Box) and ent.locked:
                        self.engine.messages.add('Box lock breaks')
                        ent.locked = False
                        if random()>.6:
                            dmg = randint(6,25)

                if dmg:
                    self.engine.player.fighter.take_damage(dmg)
                    self.engine.messages.add(f'{self.engine.player} takes {dmg} damage.')
                self.engine.event_handler = EventHandler(self.engine)
                break
        else:
            self.engine.messages.add('Choose a direction..')


class SelectIndexHandler(AskUserEventHandler):
    def __init__(self, engine):
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_loc = player.loc

    def on_render(self, console):
        super().on_render(console)
        x, y = self.engine.mouse_loc
        console.rgb["bg"][x, y] = Color.white
        console.rgb["fg"][x, y] = Color.black

    def ev_keydown(self, event):
        key = event.sym
        keys = tcod.event.KeySym
        for k in dir_keys:
            if key==getattr(keys, k):
                modifier = 1
                if event.mod & tcod.event.Modifier.SHIFT:
                    modifier *= 5
                if event.mod & (tcod.event.KeySym.LCTRL | tcod.event.KeySym.RCTRL):
                    modifier *= 10
                if event.mod & (tcod.event.KeySym.LALT | tcod.event.KeySym.RALT):
                    modifier *= 20

                x, y = self.engine.mouse_loc
                dx, dy = dir_keys[k]
                x += dx * modifier
                y += dy * modifier
                x = max(0, min(x, self.game_map.width - 1))
                y = max(0, min(y, self.game_map.height - 1))
                self.engine.mouse_loc = Loc(x, y)
                return None

        if key in CONFIRM_KEYS:
            try:
                self.on_index_selected(*self.engine.mouse_loc)
            except Impossible as e:
                self.engine.messages.add(e.args[0], Color.impossible)
        return super().ev_keydown(event)

    def ev_mousebuttondown(self, event):
        self.engine.context.convert_event(event)
        if self.game_map.in_bounds(Loc(*event.tile)):
            if event.button == 1:   # left click
                return self.on_index_selected(*event.tile)
        return super().ev_mousebuttondown(event)


class LookHandler(SelectIndexHandler):
    """Lets the player look around using the keyboard."""
    def on_index_selected(self, x, y):
        self.engine.event_handler = EventHandler(self.engine)


class SingleRangedAttackHandler(SelectIndexHandler):
   """Handles targeting a single enemy. Only the enemy selected will be affected."""
   def __init__(self, engine, item):
       super().__init__(engine)
       self.item = item

   def on_index_selected(self, x, y):
       being = self.game_map.get_living_at_loc(Loc(x,y))
       self.item.activate2(being)

class AreaRangedAttackHandler(SelectIndexHandler):
   """Handles targeting an area within a given radius. Any entity within the area will be affected."""
   radius = 3

   def __init__(self, engine, item):
       super().__init__(engine)
       self.item = item

   def on_render(self, console):
       """Highlight the tile under the cursor."""
       super().on_render(console)
       x, y = self.engine.mouse_loc
       console.draw_frame(x=x - self.radius - 1, y=y - self.radius - 1,
           width=self.radius ** 2, height=self.radius ** 2,
           fg=Color.red, clear=False)

   def on_index_selected(self, x, y):
       self.item.activate2((x,y))

class MainMenu(EventHandler):
    def on_render(self, console):
        """Render the main menu on a background image."""
        console.print( console.width // 2, console.height // 2 - 4, 'Game 21', fg=Color.menu_title, alignment=libtcodpy.CENTER)

        menu_width = 24
        for i, text in enumerate( ["[N] Play a new game", "[C] Continue last game", "[Q] Quit"]):
            console.print( console.width // 2, console.height // 2 - 2 + i, text.ljust(menu_width),
                fg=Color.menu_text, bg=Color.black, alignment=libtcodpy.CENTER, bg_blend=libtcodpy.BKGND_ALPHA(64))

    def ev_keydown(self, event):
        from engine import load_game, new_game
        custom_maps_fn = 'custom_maps.dat'
        if event.sym in (tcod.event.KeySym.q, tcod.event.KeySym.ESCAPE):
            raise SystemExit()
        elif event.sym == tcod.event.KeySym.c:
            try:
                engine = load_game('game.sav', custom_maps_fn)
                engine.context = self.engine.context
                return EventHandler(engine)
            except FileNotFoundError:
                return PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()
                self.engine.event_handler = PopupMessage(self, f"Failed to load save:\n{exc}")
        elif event.sym == tcod.event.KeySym.n:
            return EventHandler(new_game(custom_maps_fn)[0])

class ConversationHandler(EventHandler):
    def __init__(self, parent_handler, conversation, *a, on_yes=None, **kw):
        self.parent = parent_handler
        self.on_yes = on_yes
        # handle either conversation object or a list of text
        if conversation and not isinstance(conversation, list):
            conversation = conversation.text
        self.conversation = conversation
        self.i = 0
        super().__init__(*a, **kw)

    def on_render(self, console):
        """Render the parent and dim the result, then print conversation on top."""
        self.parent.on_render(console)
        console.rgb["fg"] //= 4
        console.rgb["bg"] //= 4

        text = self.conversation[self.i]
        import entity
        if self.on_yes and isinstance(text, entity.YesNoMessage):
            self.engine.event_handler = PopupMessage(self, text.text, self.engine, yes_no=True, on_yes=self.on_yes)
        else:
            lines = wrap(text, 70)
            for n, l in enumerate(lines):
                console.print(console.width // 2, console.height // 2 + n, l, fg=Color.white, bg=Color.black, alignment=libtcodpy.CENTER)

    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        key = event.sym
        if key in (keys.SPACE, keys.RETURN):
            self.i += 1
        conv = self.conversation
        if self.i >= len(conv):
            self.engine.event_handler = EventHandler(self.engine)

class PopupMessage(EventHandler):
    def __init__(self, parent_handler, text, *a, yes_no=None, on_yes=None, **kw):
        self.parent = parent_handler
        self.yes_no = yes_no
        self.on_yes = on_yes
        self.text = text
        super().__init__(*a, **kw)

    def on_render(self, console):
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(console)
        console.rgb["fg"] //= 8
        console.rgb["bg"] //= 8

        console.print(console.width // 2, console.height // 2, self.text, fg=Color.white, bg=Color.black, alignment=libtcodpy.CENTER)

    def ev_keydown(self, event):
        keys = tcod.event.KeySym
        if self.yes_no and event.sym==keys.y:
            if self.on_yes:
                self.on_yes()
        if not self.yes_no or event.sym in (keys.y, keys.n, keys.ESCAPE):
            self.engine.event_handler = EventHandler(self.engine)

class LevelUpEventHandler(AskUserEventHandler):
    title = "Level Up"
    def on_render(self, console):
        super().on_render(console)
        if self.engine.player.loc.x <= 30:
            x = 40
        else:
            x = 0

        console.draw_frame( x=x, y=0, width=35, height=8, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0))

        console.print(x=x + 1, y=1, string="Congratulations! You level up!")
        console.print(x=x + 1, y=2, string="Select an attribute to increase.")

        console.print(x=x + 1, y=4, string=f"a) HP (+20 HP, from {self.engine.player.fighter.max_hp})")
        console.print(x=x + 1, y=5, string=f"b) Attack (+1 attack, from {self.engine.player.fighter._power})")
        console.print(x=x + 1, y=6, string=f"c) Defense (+1 defense, from {self.engine.player.fighter._defense})")

    def ev_keydown(self, event):
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.KeySym.a

        if 0 <= index <= 2:
            if index == 0:
                player.level.increase_max_hp()
            elif index == 1:
                player.level.increase_power()
            else:
                player.level.increase_defense()
        else:
            self.engine.messages.add("Invalid entry.", Color.invalid)
            return

        return super().ev_keydown(event)

    def ev_mousebuttondown( self, event):
        """ Don't allow the player to click to exit the menu, like normal."""
        return None

class CharacterScreenEventHandler(AskUserEventHandler):
    title = "Character Information"

    def on_render(self, console):
        super().on_render(console)

        if self.engine.player.loc.x <= 30:
            x = 40
        else:
            x = 0
        y = 0
        width = len(self.title) + 4
        console.draw_frame( x=x, y=y, width=width, height=8, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0),)
        p = self.engine.player
        console.print( x=x + 1, y=y + 1, string=f"Level: {p.level.level}")
        console.print( x=x + 1, y=y + 2, string=f"XP: {p.level.current_xp}")
        console.print( x=x + 1, y=y + 3, string=f"XP for next Level: {p.level.experience_to_next_level}")
        console.print( x=x + 1, y=y + 4, string=f"Attack: {p.fighter._power}")
        console.print( x=x + 1, y=y + 5, string=f"Defense: {p.fighter._defense}")
        console.print( x=x + 1, y=y + 6, string=f"Strength: {p.strength}")


class QuestsHandler(AskUserEventHandler):
    title = 'Quests'

    def on_render(self, console):
        super().on_render(console)
        if self.engine.player.loc.x <= 30:
            x = 40
        else:
            x = 0
        y = 0
        width = 40
        console.draw_frame(x=x, y=y, width=width, height=7, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0),)
        for q in self.engine.quests.values():
            c = ' [completed]' if q.completed else ''
            n = (q.name+' '*25)[:25]
            console.print(x=x + 1, y=y + 1, string=f'{n}' + c)
