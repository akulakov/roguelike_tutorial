from random import random

class Equipment:
    entity = ring1 = ring2 = None

    def __init__(self, entity, weapon=None, armor=None, tool=None, ring1=None, ring2=None):
        self.entity = entity
        self.weapon = weapon
        self.armor = armor
        self.tool = tool
        self.ring1 = ring1
        self.ring2 = ring2

    @property
    def defense_bonus(self):
        bonus = 0
        if self.weapon:
            bonus += self.weapon.defense_bonus
        if self.armor:
            bonus += self.armor.defense_bonus
        if self.tool:
            bonus += self.tool.defense_bonus
        if self.ring1:
            bonus += self.ring1.defense_bonus
        if self.ring2:
            bonus += self.ring2.defense_bonus
        return bonus

    def fully_equipped(self):
        return self.weapon and self.armor and self.tool and self.ring1 and self.ring2

    @property
    def power_bonus(self):
        bonus = 0
        if self.weapon:
            b = self.weapon.power_bonus
            bm = b*self.weapon.damaged_mod
            if b==bm:
                bm-= 1

            bonus += bm
        if self.armor:
            bonus += self.armor.power_bonus
        if self.tool:
            bonus += self.tool.power_bonus
        if self.ring1:
            bonus += self.ring1.power_bonus
        if self.ring2:
            bonus += self.ring2.power_bonus
        return bonus

    def item_is_equipped(self, item):
        return item in (self.weapon, self.armor, self.tool, self.ring1, self.ring2)

    def unequip_message(self, item_name):
        self.entity.engine.messages.add(f'{self.entity} removes the {item_name}.')

    def equip_message(self, item_name):
        self.entity.engine.messages.add( f'{self.entity} equips the {item_name}.')

    def equip_to_slot(self, item, add_message=True, slot=None):
        slot = slot or self.get_slot(item)
        current_item = getattr(self, slot)
        if current_item:
            self.unequip_from_slot(slot, add_message)
        setattr(self, slot, item)

        if add_message:
            self.equip_message(item.name)

    def unequip_from_slot(self, slot, add_message=True):
        current_item = getattr(self, slot)

        if add_message:
            self.unequip_message(current_item.name)

        setattr(self, slot, None)

    def get_slot(self, item):
        from entity import Weapon, Armor, Tool, Ring
        if isinstance(item, Weapon):
            return 'weapon'
        if isinstance(item, Armor):
            return 'armor'
        if isinstance(item, Tool):
            return 'tool'
        if isinstance(item, Ring):
            return 'ring1'

    def slot_available(self, item=None, slot=None):
        slot = slot or self.get_slot(item)
        return not getattr(self, slot)

    def toggle_equip(self, item, add_message=True):
        slot = self.get_slot(item)
        if getattr(self, slot) == item:
            self.unequip_from_slot(slot, add_message)
        else:
            self.equip_to_slot(item, add_message)


class CharLevel:
    being = None

    def __init__(self, engine, being, level=1, current_xp=0, level_up_base=10, level_up_factor=150, xp_given=40):
        self.engine = engine
        self.being = being
        self.level = level
        self.current_xp = current_xp
        self.level_up_base = level_up_base
        self.level_up_factor = level_up_factor
        self.xp_given = xp_given

    @property
    def experience_to_next_level(self):
        return self.level_up_base + self.level * self.level_up_factor

    @property
    def requires_level_up(self):
        return self.current_xp > self.experience_to_next_level

    def add_xp(self, xp):
        if xp == 0 or self.level_up_base == 0:
            return
        self.current_xp += xp
        self.engine.messages.add(f"You gain {xp} experience points.")

        if self.requires_level_up:
            self.engine.messages.add( f"You advance to level {self.level + 1}!")

    def increase_level(self):
        self.current_xp -= self.experience_to_next_level
        self.level += 1

    def increase_max_hp(self, amount=20):
        self.being.fighter.max_hp += amount
        self.being.fighter.hp += amount
        self.engine.messages.add("Your health improves!")
        self.increase_level()

    def increase_power(self, amount=1):
        self.being.fighter._power += amount
        self.engine.messages.add("You feel stronger!")
        self.increase_level()

    def increase_defense(self, amount=1):
        self.being.fighter._defense += amount
        self.engine.messages.add("Your movements are getting swifter!")
        self.increase_level()


class Magic:
    def __init__(self, entity, mana, resistance, power):
        self.entity = entity
        self.max_mana = self._mana = mana
        self.resistance = resistance
        self.power = power

    @property
    def mana(self):
        return self._mana

    @mana.setter
    def mana(self, value):
        self._mana = max(0, min(value, self.max_mana))

class Fighter:
    def __init__(self, entity, hp, defense, power):
        self.entity = entity
        self.max_hp = hp
        self._hp = hp
        self._defense = defense
        self._power = power

    def get_mod(self):
        entity = self.entity
        m = entity.engine.game_map
        for r in m.rooms:
            if r.auspicious and entity.loc in r:
                print('in auspicious room!')
                return 1.05
        return 1

    def defense(self):
        return int(round((self._defense + self.entity.equipment.defense_bonus)*self.get_mod()))

    def power(self):
        return int(round((self._power + self.entity.equipment.power_bonus)*self.get_mod()))

    @property
    def hp(self):
        return self._hp

    @hp.setter
    def hp(self, value):
        old = self._hp
        self._hp = max(0, min(value, self.max_hp))
        if not self._hp:
            self.die()
        if self._hp!=old:
            return True

    def heal(self, amount):
        if self.hp == self.max_hp:
            return 0

        hp = min(self.max_hp, self.hp + amount)
        healed = hp - self.hp
        self.hp = hp
        return healed

    def take_damage(self, amount, type=None):
        self.hp -= amount

    def die(self):
        self.entity.on_death()
        eng = self.entity.engine
        if eng.player is self.entity:
            death_message = 'You died!'
        else:
            death_message = f'{self.entity.name} is dead!'
            eng.player.level.add_xp(self.entity.level.xp_given)
        eng.messages.add(death_message)

        e = self.entity
        e.char = '%'
        e.color = (191, 0, 0)
        e.blocking = False
        e.is_hostile = False
        e.is_alive = False
        e.name = f'remains of {self.entity.name}'
        e.render_order = 1
        for i in e.inventory:
            i.loc = e.loc
            eng.game_map.entities.add(i)
            e.inventory.items = []


class Inventory:
    def __init__(self, engine, entity, capacity):
        self.engine = engine
        self.entity = entity
        self.capacity = capacity
        self.items = []
        if engine:
            self.game_map = engine.game_map

    def __bool__(self):
        return bool(self.items)

    def __iter__(self):
        return iter(self.items)

    def __contains__(self, id):
        for i in self.items:
            if i.id==id:
                return True

    def add(self, item):
        self.items.append(item)
        item.container = self
        item.entity = self.entity

    def drop(self, item):
        self.items.remove(item)
        eng = self.entity.engine
        eng.game_map.place(item, self.entity.loc)
        eng.messages.add(f"{self.entity} dropped the {item}.")

    def remove(self, item):
        self.items.remove(item)

    def get_list(self, cls):
        return [i for i in self if isinstance(i, cls)]

    def get_one(self, cls):
        ls = self.get_list(cls)
        if ls:
            return ls[0]

    def take_damage(self, type):
        from entity import DamageType, Potion, Ring, Wand
        if type == DamageType.cold:
            for p in self.get_list(Potion):
                if random()>.9:
                    self.entity.engine.add(f'Blast of cold breaks {p}')
                    self.remove(p)
