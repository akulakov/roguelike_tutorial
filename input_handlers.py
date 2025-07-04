import traceback
import tcod.event
from tcod import libtcodpy

from actions import BumpAction, WaitAction, MovementAction, PickupAction, Impossible, DropItem
from util import Loc
from game_map import Color
import tile_types

dir_keys = dict(
    y=(-1,-1), u=(1,-1), b=(-1,1), n=(1,1),
    h=(-1,0), j=(0,1), k=(0,-1), l=(1,0))


from itertools import compress
class EventHandler(tcod.event.EventDispatch):
    go = False

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

        for k in dir_keys:
            if key==getattr(keys, k):
                mod = Loc(*dir_keys[k])
                if self.go:
                    mod = self.fast_go(mod)
                action = BumpAction(mod)
        self.go = False
        Modifier = tcod.event.Modifier
        Shift = event.mod & tcod.event.Modifier.SHIFT
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
        elif key == keys.s and Shift:
            for l in self.player.loc.adj():
                if self.game_map.tiles[l] == tile_types.hidden_passage:
                    self.game_map.tiles[l] = tile_types.floor
            else:
                engine.messages.add('You do not find anything hidden.')

        elif key == keys.PERIOD:
            action = WaitAction()
        elif key == keys.v:
            self.engine.event_handler = HistoryViewer(self.engine)
        elif key == keys.m:
            self.engine.event_handler = MapViewer(self.engine)
        elif key == keys.c:
            self.engine.event_handler = CharacterScreenEventHandler(self.engine)
        elif key == keys.i:
            self.engine.event_handler = InventoryActivateHandler(self.engine)
        elif key == keys.SLASH:
            self.engine.event_handler = LookHandler(self.engine)
        elif key == keys.COMMA:
            action = PickupAction()
        elif key == keys.d:
            self.engine.event_handler = InventoryDropHandler(self.engine)
        elif key == keys.r and Shift:
            self.game_map.reveal = not self.game_map.reveal

        if action:
            action.init(engine, self.player)

        if key == keys.ESCAPE:
            engine.context = None  # tcod context cannot be pickled
            self.save_game('game.sav')
            raise SystemExit()

        if self.player.level.requires_level_up:
            engine.event_handler = LevelUpEventHandler(engine)

        return action

    def save_game(self, filename):
        self.engine.save_as(filename)
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
            elif ok and sum(locs_e)==2:
                # open area, stop
                break

            self.engine.handle_enemy_turns()
            self.engine.update_fov()
            self.engine.render()
        return mod

    def on_render(self, console):
        pass

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

    def on_render(self, console):
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        if self.engine.player.loc.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.title) + 25

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=self.title,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord('a') + i)
                is_equipped = self.engine.player.equipment.item_is_equipped(item)
                is_equipped = ' (E)' if is_equipped else ''
                console.print(x + 1, y + i + 1, f'({item_key}) {item}{is_equipped}')
        else:
            console.print(x + 1, y + 1, '(Empty)')

    def ev_keydown(self, event):
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.KeySym.a

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.messages.add('Invalid entry.', Color.invalid)
                return
            try:
                return self.on_item_selected(selected_item)
            except Impossible as e:
                self.engine.messages.add(e.args[0], Color.impossible)
        return super().ev_keydown(event)

class InventoryActivateHandler(InventoryEventHandler):
   title = 'Select an item to use'
   def on_item_selected(self, item):
       item.activate()


class InventoryDropHandler(InventoryEventHandler):
   title = 'Select an item to drop'
   def on_item_selected(self, item):
       a = DropItem()
       a.init(self.engine, self.engine.player, item=item)
       return a

CONFIRM_KEYS = {
   tcod.event.KeySym.RETURN,
   tcod.event.KeySym.KP_ENTER,
}

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
        if event.sym in (tcod.event.KeySym.q, tcod.event.KeySym.ESCAPE):
            raise SystemExit()
        elif event.sym == tcod.event.KeySym.c:
            try:
                engine = load_game('game.sav')
                engine.context = self.engine.context
                return EventHandler(engine)
            except FileNotFoundError:
                return PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()
                self.engine.event_handler = PopupMessage(self, f"Failed to load save:\n{exc}")
        elif event.sym == tcod.event.KeySym.n:
            return EventHandler(new_game()[0])

class PopupMessage(EventHandler):
    def __init__(self, parent_handler, text, *a, **kw):
        self.parent = parent_handler
        self.text = text
        super().__init__(*a, **kw)

    def on_render(self, console):
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(console)
        console.rgb["fg"] //= 8
        console.rgb["bg"] //= 8

        console.print(console.width // 2, console.height // 2, self.text, fg=Color.white,
            bg=Color.black, alignment=libtcodpy.CENTER)

    def ev_keydown(self, event):
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

        console.print(x=x + 1, y=4, string=f"a) Constitution (+20 HP, from {self.engine.player.fighter.max_hp})")
        console.print(x=x + 1, y=5, string=f"b) Strength (+1 attack, from {self.engine.player.fighter._power})")
        console.print(x=x + 1, y=6, string=f"c) Agility (+1 defense, from {self.engine.player.fighter._defense})")

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
        console.draw_frame( x=x, y=y, width=width, height=7, title=self.title, clear=True, fg=(255, 255, 255), bg=(0, 0, 0),)
        p = self.engine.player
        console.print( x=x + 1, y=y + 1, string=f"Level: {p.level.level}")
        console.print( x=x + 1, y=y + 2, string=f"XP: {p.level.current_xp}")
        console.print( x=x + 1, y=y + 3, string=f"XP for next Level: {p.level.experience_to_next_level}")
        console.print( x=x + 1, y=y + 4, string=f"Attack: {p.fighter._power}")
        console.print( x=x + 1, y=y + 5, string=f"Defense: {p.fighter._defense}")
