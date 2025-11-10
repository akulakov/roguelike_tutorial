from collections import defaultdict
import time
from enum import Enum, auto
import tcod
from random import choice, random
import input_handlers
import numpy as np
from util import Loc
from actions import WaitAction, MovementAction, MeleeAction, Impossible, BumpAction
from game_map import Color
from entity_components import Equipment, CharLevel, Inventory, Fighter

YES_NO = 1

class Resistances(Enum):
    poison = auto()
    fire = auto()
    cold = auto()

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
    xp_given = 10
    id = None
    vloc = 0
    vchar = None
    levitating = 0
    asleep = 0
    paralized = 0
    poisoned = 0
    turning_to_stone = 0

    def __init__(self, engine, x=None, y=None, char=None, color=None, name=None, blocking=False):
        # print("engine", engine)
        if isinstance(engine, int):
            import pdb;pdb.set_trace()
        if x is not None:
            self.loc = Loc(x, y)
        self._char = self.char or char
        self._blocking = self.blocking or blocking
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

    def wake_up_entities(self):
        #print('in wake_up_entities')
        lst = self.game_map.entities_within_dist(self.loc, 15)
        # print("lst", lst)
        lst = [e for e in lst if e.asleep]
        # print("lst", lst)
        if lst:
            tmp = ', '.join(str(e) for e in lst)
            self.engine.messages.add(f'Monsters wake up: {tmp}')
        for e in lst:
            e.asleep = 0

# END OF ENTITY

class Blocking(Entity):
    blocking = True

class Item(Entity):
    base_price = 0
    power_bonus = 0
    defense_bonus = 0
    container = None

    def activate(self):
        pass

class Comestible(Item):
    pass

class GhostPepper(Comestible):
    resistance = 0.8, Resistances.fire

class Living(Blocking):
    speed = 1
    is_alive = True
    is_seller = False
    render_order = 3
    gold = 0
    gen_companions = None

    def __init__(self, *a, **kw):
        if self.fighter:
            self.fighter = Fighter(self, *self.fighter)
        super().__init__(*a, **kw)
        self.level = CharLevel(self.engine, self, xp_given=self.xp_given)
        self.resistances = set()

    def hostile_to(self, other):
        return (self.is_hostile and other.is_player) or (self.is_player and other.is_hostile)

    def on_attack(self, entity):
        pass

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

        ls = self.inventory.get(LightningScroll)
        if ls:
            if ls.is_usable(self.engine.player):
                ls.activate()
                self.wake_up_entities()
                return

        if self.game_map.visible[self.loc.x, self.loc.y]:
            if self.loc.dist(target.loc) <= 1:
                target.asleep = 0
                # print(target, "target.asleep", target.asleep)
                a = MeleeAction(self.loc.dir_to(target.loc))
                a.init(self.engine, self)
                self.wake_up_entities()
                self.on_attack(target)
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
    strength  = 10

class Orc(Hostile):
    char = 'o'
    color = 63, 127, 63
    name = 'Orc'
    fighter = 10,1,2

class AcidBlob(Hostile):
    char = 'b'
    color = 63, 63, 63
    name = 'Acid Blob'
    fighter = 10,2,2

    def on_attack(self, entity):
        pass

class Chicatrice(Hostile):
    char = 'c'
    color = 63, 163, 63
    fighter = 12,3,3

    def on_attack(self, entity):
        e = entity
        if random()<.33:
            self.engine.messages.add(f'Chicatrice hisses at {e}')
            if random()>.9:
                e.turning_to_stone = 5

class Troll(Hostile):
    char = 'T'
    color = 0,127,0
    fighter = 15,2,2

class HealthPotion(HealingItem):
    char = '!'
    color = 127,0,255
    name = 'Health Potion'
    amount = 4
    base_price = 10

class AuspiciousRoomScroll(Item):
    char = '~'
    color = 147,45,155
    name = 'Auspicious Room Scroll'
    base_price = 30

    def activate(self):
        r = choice(self.engine.game_map.rooms)
        r.auspicious = 30
        self.container.remove(self)
        self.engine.messages.add('You feel like there is a good place for you somewhere on this level of caves')
        print("r auspicious", r, r.auspicious)


class Scroll(Item):
    char = '~'

class MagicMissileScroll(Scroll):
    color = 247,145,35
    base_price = 30
    damage = 5
    name = 'Magic Missile Scroll'

    def activate(self):
        self.engine.messages.add( 'Select a direction', Color.needs_target)
        self.engine.event_handler = input_handlers.DirectionHandler(self.engine, callback=self.activate2)

    def activate2(self, dir):
        dir = Loc(*dir)
        oloc = loc = self.engine.player.loc
        if dir.x==-1:
            oloc = oloc.mod(-5,0)
        elif dir.y==-1:
            oloc = oloc.mod(0,-5)
        map = self.engine.game_map

        oloc = oloc.mod(*dir)

        for n in range(1, 6):
            loc = loc.mod(*dir)
            if not dir.y:
                l = oloc if dir.is_pos() else loc
                self.engine.print(*l, '-'*n, Color.red)
            else:
                self.engine.print(*loc, '|', Color.red)
            time.sleep(0.1)

            for e in list(map.get_all_living_at_loc(loc)):
                e.fighter.take_damage(self.damage)
                self.engine.messages.add(f'{e} suffers {self.damage} damage')
        self.engine.player.inventory.remove(self)

class LightningScroll(Scroll):
    color = 127,25,155
    name = 'Lightning Scroll'
    damage = 5
    maximum_range = 5
    base_price = 20

    def is_usable(self, target):
        """Determine if can be used by monsters / NPCs."""
        return target == self.calculate_target()

    def calculate_target(self):
        target = None
        closest_distance = self.maximum_range + 1.0
        e = self.container.entity

        for being in self.engine.game_map.living():
            if e.hostile_to(being):
                l = being.loc
                if being is not e and e.game_map.visible[l.x, l.y]:
                    distance = e.loc.dist(l)
                    if distance < closest_distance:
                        target = being
                        closest_distance = distance
        return target

    def activate(self):
        target = self.calculate_target()

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
    base_price = 20

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
    base_price = 30

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
    base_price = 30

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


class LevitationScroll(Scroll):
    color = 127, 190, 130
    name = 'Levitation Scroll'
    duration = 5
    base_price = 40

    def activate(self):
        entity = self.entity
        self.engine.messages.add(f'The {entity} begins to float in the air!')
        entity.levitating = self.duration
        entity.vloc = 1
        self.container.remove(self)

class SleepScroll(Scroll):
    color = 117, 190, 130
    name = 'Sleep Scroll'
    duration = 5
    base_price = 50

    def activate(self):
        entity = self.entity
        self.engine.messages.add(f'The {entity} falls asleep')
        entity.asleep = self.duration
        self.container.remove(self)


class FireballScroll(Scroll):
    color = 127, 130, 120
    name = 'Fireball Scroll'
    damage = 6
    radius = 5
    base_price = 30

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

class IDs(Enum):
    julius_mattius = auto()
    note1 = auto()
    level_a = auto()
    level_b = auto()
    sword_ringing_bell = auto()
    broken_sword_ringing_bell = auto()
    martinella = auto()

class Equippable(Item):
    def __init__(self, *a, power_bonus=0, defense_bonus=0, entity=None, **kw):
        self.entity = entity
        self.power_bonus = self.power_bonus or power_bonus
        self.defense_bonus = self.defense_bonus or defense_bonus
        super().__init__(*a, **kw)

    def activate(self):
        self.entity.equipment.toggle_equip(self)

class Weapon(Equippable):
    char = ')'
    damaged_mod = 1

    def damage(self):
        if not self.damaged_mod:
            self.damaged_mod = 0.8

class Armor(Equippable):
    char = '['
class Tool(Equippable):
    char = ']'
class Ring(Equippable):
    char = '='

class Box(Item):
    char = ']'
    color = 100,100,100
    locked = False

    def __init__(self, engine, *a, **kw):
        self.inventory = Inventory(engine, self, 20)
        self.locked = random()>.05
        super().__init__(engine, *a, **kw)

class RingOfFreeAction(Ring):
    color = 0, 95, 225
    base_price = 100

class Broom(Tool):
    color = 0, 95, 225
    power_bonus = 1
    base_price = 5

class Abacus(Tool):
    color = 0, 50, 100
    base_price = 5

    def activate(self):
        self.engine.messages.add(f'{self.entity} calculates a few numbers.')

class Dagger(Weapon):
    color = 0, 191, 255
    power_bonus = 2
    base_price = 10

class Sword(Weapon):
    color = 0, 91, 255
    power_bonus = 4
    base_price = 25

class SwordOfRingingBell(Sword):
    name = 'Sword of Ringing Bell'
    color = 90, 120, 155
    id = IDs.sword_ringing_bell
    _loc = 2,1

    def break_(self):
        self.container.remove(self)
        item = BrokenSwordOfRingingBell(self.engine, self.container.entity)
        self.container.add(item)
        self.engine.messages.add(f'You break the {self}')

class BrokenSwordOfRingingBell(Item):
    char = ']'
    name = 'Pieces of broken sword of ringing bell'
    color = 90, 120, 155
    id = IDs.broken_sword_ringing_bell

class LeatherArmor(Armor):
    color = 0, 1, 255
    defense_bonus = 2
    base_price = 25

class ChainMail(Armor):
    color = 35, 1, 255
    defense_bonus = 3
    base_price = 35

class BurlyArmor(Armor):
    color = 35,25,75
    defense_bonus = 5
    base_price = 45

class CreakingArmor(Armor):
    """This armor creaks when being hit which dissipates some of the damage."""
    color = 35,105,105
    defense_bonus = 7
    base_price = 70

class BroomTroll(Hostile):
    """These Trolls developed immense strength and toughness by spending years upon years of sweeping the dank,
    dangerous dungeons of dried carcasses of small animals, skulls of adventurers and various decomposing piles of
    unknown origin."""
    char = 'T'
    color = 0,127,50
    name = 'Broom Troll'
    fighter = 20,3,4
    _inventory = [Broom]
    xp_given = 50
    speed = .5

class ThwackingOrc(Orc):
    """These Orcs thwacks, with great force, anyone and anything unfriendly that comes near."""
    color = 0,65,65
    name = 'Thwacking Orc'
    fighter = 22,4,5
    xp_given = 60

class BurningOrc(Orc):
    """These Orcs are a mixed population with some type of fire-breathing creatures. There is on-going research by Mages
    and Sages into this question."""
    color = 150,50,50
    name = 'Burning Orc'
    fighter = 24,6,6
    xp_given = 70

class ResoluteOrc(Orc):
    """These Orcs have unbending will in battle. They do not back down unless they decide to do so for tactical or strategic reasons."""
    color = 50,120,130
    name = 'Resolute Orc'
    fighter = 28,7,8
    xp_given = 80

class KnurledGoblin(Hostile):
    """The hide of these Goblins is thick and knurled, increasing their doughtiness to rarely seen level."""
    char = 'g'
    color = 65,65,95
    name = 'Knurled Goblin'
    fighter = 30,9,9
    xp_given = 90

class MusculousGoblin(Hostile):
    """These Goblins are well known for the strength, muscles and powerful blows they rain on all foes."""
    char = 'g'
    color = 75,95,105
    name = 'Musculous Goblin'
    fighter = 32,10,12
    xp_given = 110

class SatyricGoblin(Hostile):
    """These Goblins were mixed with the feared tribe of Satyrs, giving them impressive sturdiness and power."""
    char = 'g'
    color = 75,65,55
    name = 'Satyric Goblin'
    fighter = 35,13,13
    xp_given = 130

class InsuperableTroll(Troll):
    color = 65,105,105
    name = 'Insuperable Troll'
    fighter = 37,14,15
    xp_given = 160

class GiantAnt(Hostile):
    char = 'a'
    color = 85,105,105
    name = 'Giant Ant'
    fighter = 7,2,2
    gen_companions = 0.5, 2, 4
    xp_given = 25

class FireAnt(Hostile):
    char = 'a'
    color = 185,105,105
    name = 'Fire Ant'
    fighter = 7,3,3
    xp_given = 45

class Note(Item):
    char = '['
    text = None
    color = 35,35,35

class Note1(Note):
    text = ".. my poor eyes [...] violence of sorrow froze his life's blood, and he fell ..."
    id = IDs.note1
    _loc = 0,2

class JuliusMattius(Troll):
    color = 250, 50, 155
    is_seller = True
    name = 'Julius Mattius'
    id = IDs.julius_mattius
    _loc = 1,1  # level 2, room 1
    is_hostile = False
    _inventory = [FireballScroll, Sword, LeatherArmor, Broom]
    gold = 500

class Martinella(Orc):
    color = 25, 25, 205
    name = 'Martinella'
    id = IDs.martinella
    _loc = 0,1
    _inventory = [BurlyArmor]
    gold = 100
    is_hostile = False

class Conversation:
    id = None

class Quest:
    id = None
    step = 1
    started = False
    completed = False
    end_condition = None

    def __init__(self, engine, entity):
        self.engine = engine
        self.entity = entity

    def condition(self):
        return True

    @property
    def conv(self):
        if self.step==1:
            return self.initial
        elif self.step==3:
            return self.end_text

    def start(self):
        self.step = 2
        self.started = True

    def check_end_condition(self):
        return self.end_condition in self.engine.player.inventory

    def end(self):
        self.step = 3
        self.completed = True
        player = self.engine.player
        if self.reward:
            for i in self.reward:
                if isinstance(i, int):
                    player.gold += i
                    self.engine.messages.add(f'You receive ${i}')
                else:
                    item = i(self.engine, entity=player)
                    player.inventory.add(item)
                    self.engine.messages.add(f'You receive {item}!')

    def advance(self):
        if not self.started:
            return
        if self.step==1:
            self.start()
        if self.step==2 and self.check_end_condition():
            self.end()

class ConversationMessage:
    pass

class YesNoMessage(ConversationMessage):
    def __init__(self, text=None):
        text = text or 'Will you help?'
        self.text = text + ' [Y/N]'


class MartinellaQuest(Quest):
    name = 'Martinella Quest'
    id = IDs.martinella
    initial = [
        'Whether by skill or ingenuity, the ringing sword shall be demolished if this part of the caves is to enjoy its rightful peace.',
        'You will have your reward.',
        'I spoke.',
        'Martinella humphps and crosses his arms.',
        YesNoMessage(),
    ]
    end_condition = IDs.broken_sword_ringing_bell
    end_text = [
        'Beauty of the blade so illustrious.. that part of me wishes I could have kept it too myself.',
        'Yet it was wise on my part to have it broken..',
    ]
    reward = (100, BurlyArmor)

class JuliusConversation(Conversation):
    id = IDs.julius_mattius
    condition = IDs.note1
    text = ['Victorious gentle-Troll, I found a mysterious tattered scroll nearby, may you help me find out more as it relates to matters I may be interested in?',
            'Traveler, it seems to be a barely legible pergament, it is surely a figment of some diseased mind of some sorry dweller of this part of the caves.',
            '-- Julius seems worried and slightly descombobulaed. --'
           ]

class SpecialLevel:
    id = None
    level = None
    custom_map = None
    rooms = None

class LevelA(SpecialLevel):
    id = IDs.level_a
    level = 10
    rooms = [(5,5,70,15),]

class LevelB(SpecialLevel):
    id = IDs.level_b
    level = 3
    custom_map = 'a'

class SpecialData:
    """Special NPCs, items, conversations, levels, quests."""
    def __init__(self):
        self.data = {}
        self.conversations = {}
        self.levels = defaultdict(list)
        self.quests = {}
        for obj in globals().values():
            try:
                if issubclass(obj, Entity,) and hasattr(obj,'_loc'):
                    self.data[obj._loc] = obj
                elif issubclass(obj, Conversation) and obj.id:
                    self.conversations[obj.id] = obj()
                elif issubclass(obj, SpecialLevel) and obj.level:
                    self.levels[obj.level].append(obj)
                elif issubclass(obj, Quest) and obj.id:
                    self.quests[obj.id] = obj
            except TypeError:
                pass

    def get(self, k):
        return self.data.get(k)

class Door(Entity):
    closed = True
    color = 205, 25, 205

    def __init__(self, *a, **kw):
        self.locked = random()>.95
        super().__init__(*a, **kw)

    @property
    def char(self):
        return '+' if self.closed else ''

    @property
    def blocking(self):
        return self.closed

    def toggle(self):
        if not self.locked:
            self.closed = not self.closed

class Key(Tool):
    color = 205, 100, 205

class Pickaxe(Tool):
    color = 25, 10, 205

class VerticalSpace(Entity):
    pass

class UndergroundSpace(VerticalSpace):
    vloc = -1
    char = ''
    vchar = 'V'
    color = 205, 100, 205

    def __init__(self, engine, *a, **kw):
        self.inventory = Inventory(engine, self, 20)
        super().__init__(engine, *a, **kw)


special_data = SpecialData()
# print("special_locs.data", special_data.data, special_data.conversations)

class SingingFrog(Living):
    pass
