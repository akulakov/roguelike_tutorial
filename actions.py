from game_map import Color
from util import Loc

class Action:
    def init(self, engine=None, e1=None, e2=None, item=None):
        """Init common attrs."""
        self.engine = engine
        self.map = None
        if engine:
            self.map = engine.game_map
        self.e1 = e1
        self.e2 = e2
        self.item = item

class WaitAction(Action):
    def perform(self):
        pass

class DirectionAction(Action):
    def __init__(self, mod):
        self.mod = mod

class Impossible(Exception):
    pass

class QuitWithoutSaving(SystemExit):
    pass

class MovementAction(DirectionAction):
    def perform(self, move=True):
        mod = self.mod
        cloc = self.e1.loc
        loc = Loc(cloc.x+mod.x, cloc.y+mod.y)

        if not self.map.in_bounds(loc):
            raise Impossible('Out of range')
        if not self.map.tiles['walkable'][loc.x, loc.y]:
            raise Impossible('Blocked')

        # needed for fast-go
        ent = self.map.get_blocking_entity_at_loc(loc)
        if ent:
            raise Impossible('Blocked')
        if move:
            self.e1.move(self.mod)
            if self.e1.is_player:
                items = self.engine.game_map.names_at_loc(self.e1.loc, {self.e1})
                if items:
                    self.engine.messages.add(f'You see {items}')
                for r in self.map.auspicious_rooms():
                    if loc in r and cloc not in r:
                        self.engine.messages.add('You feel elated')
                        break

        return True

from random import randint, random
class MeleeAction(DirectionAction):
    def perform(self):
        cloc = self.e1.loc
        loc = Loc(cloc.x+self.mod.x, cloc.y+self.mod.y)
        target = self.engine.game_map.get_blocking_entity_at_loc(loc)
        if not target:
            return

        e1 = self.e1
        dmg = randint(1, 5) + e1.fighter.power()
        crit = ''
        if random()>.95:
            crit = ' (critical hit)'
            dmg+= randint(1, 5)
        dfn = 5 / (5+target.fighter.defense())

        damage = int(round(dmg * dfn))
        attack_desc = f"{self.e1.name.capitalize()} attacks {target.name}{crit}"
        col = Color.player_atk if self.e1.is_player else Color.enemy_atk
        if damage > 0:
            self.engine.messages.add(f"{attack_desc} for {damage} hit points.", col)
            target.fighter.hp -= damage
        else:
            self.engine.messages.add(f"{attack_desc} but does no damage.", col)

class BumpAction(DirectionAction):
    def perform(self):
        cloc = self.e1.loc
        mod = self.mod
        loc = Loc(cloc.x+mod.x, cloc.y+mod.y)

        ent = self.engine.game_map.get_blocking_entity_at_loc(loc)
        is_player = self.e1.is_player
        a = None
        if not is_player or is_player and ent and ent.is_hostile:
            a = MeleeAction(mod)
        elif not ent:
            a = MovementAction(mod)
        if a:
            a.init(self.engine, self.e1)
            return a.perform()

class PickupAction(Action):
   def perform(self):
       inv = self.e1.inventory

       for item in self.engine.game_map.items():
           if self.e1.loc==item.loc:
               if len(inv.items) >= inv.capacity:
                   raise Impossible('Your inventory is full.')

               self.engine.game_map.entities.remove(item)
               item.container = self.e1.inventory
               inv.items.append(item)
               self.engine.messages.add(f'You picked up the {item}!')
               item.entity = self.e1
               return

       raise Impossible('There is nothing here to pick up.')

class DropItem(Action):
    def perform(self):
        self.e1.inventory.drop(self.item)
        self.item.container = None
        eq = self.e1.equipment
        if eq.item_is_equipped(self.item):
            eq.toggle_equip(self.item)
        self.item.entity = None
