import tcod
from random import choice
import input_handlers
import numpy as np
from util import Loc
from actions import WaitAction, MovementAction, MeleeAction, Impossible, BumpAction
from game_map import Color
from entity_components import Equipment, CharLevel, Inventory, Fighter

class Entity:
    is_hostile = False
    game_map = None
    is_alive = False
    render_order = 1
    is_player = False
    blocking = False
    loc = None
    level = None
    name = None
    entity = None
    _inventory = ()

    def __init__(self, engine, x=None, y=None, char=None, color=None, name=None, blocking=False):
        # print("engine", engine)
        if isinstance(engine, int):
            import pdb;pdb.set_trace()
        if x is not None:
            self.loc = Loc(x, y)
        self.char = self.char or char
        self.blocking = self.blocking or blocking
        self.color = self.color or color
        self.name = self.name or name or self.__class__.__name__
        self.engine = engine
        self.inventory = Inventory(engine, self, 20)
        for i in self._inventory:
            self.inventory.add(i(engine))
        self.equipment = Equipment(self)
        self.add_engine(engine)

    def add_engine(self, engine):
        self.engine = engine
        if engine:
            self.game_map = engine.game_map
            if self.level:
                self.level.engine = engine
            if self.inventory:
                self.inventory.engine = engine
                self.inventory.game_map = engine.game_map


    def __repr__(self):
        return self.name

    def move(self, mod):
        self.loc += mod

    def get_path_to(self, loc):
        """Compute and return a path to the target position or empty list."""
        cost = np.array(self.game_map.tiles["walkable"], dtype=np.int8)

        for entity in self.game_map.entities:
            eloc = entity.loc
            if entity.blocking and cost[eloc.x, eloc.y]:
                # Add to the cost of a blocked position.  A lower number means more enemies will crowd behind each other
                # in hallways.  A higher number means enemies will take longer paths in order to surround the player.
                cost[eloc.x, eloc.y] += 10

        # Create a graph from the cost array and pass that graph to a new pathfinder.
        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)

        pathfinder.add_root(self.loc)

        # Compute the path to the destination and remove the starting point.
        path = pathfinder.path_to(loc)[1:].tolist()

        return [Loc(*index) for index in path]

class Blocking(Entity):
    blocking = True

class Item(Entity):
    power_bonus = 0
    defense_bonus = 0
    container = None

class Living(Blocking):
    is_alive = True
    render_order = 3

    def __init__(self, *a, **kw):
        if self.fighter:
            self.fighter = Fighter(self, *self.fighter)
        super().__init__(*a, **kw)
        self.level = CharLevel(self.engine, self)

class Hostile(Living):
    is_hostile = True
    path = None
    confused = None

    def handle_pickup(self):
        pickup = False
        if not self.equipment.fully_equipped():
            items = self.game_map.get_entities_at_loc(self.loc)
            for i in items:
                if isinstance(i, Equippable):
                    if self.equipment.slot_available(i):
                        self.game_map.entities.remove(i)
                        self.inventory.add(i)
                        pickup = True
        return pickup

    def handle_equipment(self):
        inv = self.inventory
        if not self.equipment.fully_equipped() and inv:
            for i in inv:
                if isinstance(i, Equippable):
                    if self.equipment.slot_available(i):
                        self.equipment.equip_to_slot(i)
                        break

    def attack(self, target):
        if self.handle_pickup():
            return
        self.handle_equipment()
        if self.confused:
            mod = Loc(*choice(list(input_handlers.dir_keys.values())))
            a = BumpAction(mod)
            a.init(self.engine, self)
            self.confused -= 1
            if not self.confused:
                self.engine.messages.add(f"The {self} is no longer confused.")
            return a

        if self.game_map.visible[self.loc.x, self.loc.y]:
            if self.loc.dist(target.loc) <= 1:
                a = MeleeAction(self.loc.dir_to(target.loc))
                a.init(self.engine, self)
                return a

            self.path = self.get_path_to(target.loc)

        if self.path:
            loc = self.path.pop(0)
            a = MovementAction(self.loc.dir_to(loc))
            a.init(self.engine, self)
            return a

        return WaitAction()

class HealingItem(Item):
    def activate(self):
        e = self.container.entity
        if e:
            recovered = e.fighter.heal(self.amount)
            self.container.remove(self)

            if recovered > 0:
                self.engine.messages.add( f"{e} consumes the {self.name}, and recovers {recovered} HP!",
                    Color.health_recovered)
            elif e is self.engine.player:
                raise Impossible("Your health is already full.")

class Player(Living):
    char = '@'
    color = 255,255,255
    name = 'Player'
    fighter = 65,12,4
    is_player = True

class Orc(Hostile):
    char = 'o'
    color = 63, 127, 63
    name = 'Orc'
    fighter = 10,1,2

class Troll(Hostile):
    char = 'T'
    color = 0,127,0
    name = 'Troll'
    fighter = 15,2,2

class HealthPotion(HealingItem):
    char = '!'
    color = 127,0,255
    name = 'Health Potion'
    amount = 4

class LightningScroll(Item):
    char = '~'
    color = 127,25,155
    name = 'Lightning Scroll'
    damage = 5
    maximum_range = 5

    def activate(self):
        target = None
        closest_distance = self.maximum_range + 1.0
        e = self.container.entity

        for being in self.engine.game_map.living():
            l = being.loc
            if being is not e and e.game_map.visible[l.x, l.y]:
                distance = e.loc.dist(l)
                if distance < closest_distance:
                    target = being
                    closest_distance = distance

        if target:
            self.engine.messages.add(f'A lighting bolt strikes the {target.name} with a loud thunder, for {self.damage} damage!')
            target.fighter.take_damage(self.damage)
            self.container.remove(self)
        else:
            raise Impossible('No enemy is close enough to strike.')

class ConfusionScroll(Item):
    char = '~'
    color = 127, 100, 100
    name = 'Confusion Scroll'
    duration = 7

    def activate(self):
        self.engine.messages.add( "Select a target location.", Color.needs_target)
        self.engine.event_handler = input_handlers.SingleRangedAttackHandler(self.engine, self)

    def activate2(self, target):
        l = target.loc
        if not self.game_map.visible[l.x, l.y]:
            raise Impossible("You cannot target an area that you cannot see.")
        if not target:
            raise Impossible("You must select an enemy to target.")

        self.engine.messages.add( f"The eyes of the {target.name} look vacant, as it starts to stumble around!",
            Color.status_effect_applied)
        target.confused = self.duration
        self.container.remove(self)

class DoorOnFireScroll(Item):
    char = '~'
    color = 111, 11, 125
    name = 'Door on Fire Scroll'
    damage = 12

    def activate(self):
        e1 = self.container.entity
        loc = e1.loc
        map = self.engine.game_map
        r = map.find_room(loc)
        if not r:
            self.engine.messages.add('This spell requires caster to be in a room.')
            return
        b = map.get_living_at_locs(r.center.adj_locs(include_self=True))
        b = set(b) - {e1}
        for e in b:
            e.fighter.take_damage(self.damage)
        if len(b)==1:
            self.engine.messages.add(f'{b[0]} was struck by {self.name}.')
        elif len(b)==0:
            self.engine.messages.add(f'{self.name} burns empty space.')
        else:
            self.engine.messages.add(f'{len(b)} monsters were struck by {self.name}.')
        self.container.remove(self)


class EyeOfIceScroll(Item):
    char = '~'
    color = 111, 111, 125
    name = 'Eye of Ice Storm Scroll'
    damage = 15

    def activate(self):
        e1 = self.container.entity
        loc = e1.loc
        map = self.engine.game_map
        r = map.find_room(loc)
        if not r:
            self.engine.messages.add('This spell requires caster to be in a room.')
            return
        b = map.get_living_at_locs(r.center.adj_locs(include_self=True))
        b = set(b) - {e1}
        for e in b:
            e.fighter.take_damage(self.damage)
        if len(b)==1:
            self.engine.messages.add(f'{b[0]} was struck by Eye of Ice.' % len(b))
        elif len(b)==0:
            self.engine.messages.add('Eye of Ice freezes empty space.')
        else:
            self.engine.messages.add('%d monsters were struck by Eye of Ice.' % len(b))
        self.container.remove(self)


class FireballScroll(Item):
    char = '~'
    color = 127, 130, 120
    name = 'Fireball Scroll'
    damage = 6
    radius = 5

    def activate(self):
        self.engine.messages.add( 'Select a target location.', Color.needs_target)
        self.engine.event_handler = input_handlers.AreaRangedAttackHandler(self.engine, self)

    def activate2(self, target_xy):
        if not self.game_map.visible[target_xy]:
            raise Impossible('You cannot target an area that you cannot see.')

        targets_hit = False
        for being in self.game_map.living():
            if being.loc.dist(Loc(*target_xy)) <= self.radius:
                self.engine.messages.add( f'The {being} is engulfed in a fiery explosion, taking {self.damage} damage!')
                being.fighter.take_damage(self.damage)
                targets_hit = True

        if not targets_hit:
            raise Impossible('There are no targets in the radius.')
        self.container.remove(self)

class Equippable(Item):
    def __init__(self, *a, power_bonus=0, defense_bonus=0, **kw):
        self.power_bonus = self.power_bonus or power_bonus
        self.defense_bonus = self.defense_bonus or defense_bonus
        super().__init__(*a, **kw)

    def activate(self):
        self.entity.equipment.toggle_equip(self)

class Weapon(Equippable):
    pass
class Armor(Equippable):
    pass
class Tool(Equippable):
    pass

class Broom(Tool):
    char = '['
    color = 0, 95, 225
    power_bonus = 1

class Dagger(Weapon):
    char = '/'
    color = 0, 191, 255
    power_bonus = 2

class Sword(Weapon):
    char = '/'
    color = 0, 91, 255
    power_bonus = 4

class LeatherArmor(Armor):
    char = '['
    color = 0, 1, 255
    defense_bonus = 2

class ChainMail(Armor):
    char = '['
    color = 35, 1, 255
    defense_bonus = 3

class BroomTroll(Hostile):
    char = 'T'
    color = 0,127,50
    name = 'Broom Troll'
    fighter = 20,3,4
    _inventory = [Broom]

