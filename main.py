#!/usr/bin/env python3
from random import random
import tcod
import traceback

from engine import start
from input_handlers import EventHandler
from game_map import Color
from actions import Impossible

def game_loop(engine, console, context):
    while True:
        engine.render(console=console, context=context)

        for event in tcod.event.wait():
            action = engine.event_handler.dispatch(event)
            if isinstance(action, EventHandler):
                engine = action.engine
                engine.context = context
                engine.console = console
                continue

            elif action:
                try:
                    action.perform()
                except Impossible as e:
                    engine.messages.add(e.args[0], Color.impossible)

                engine.handle_enemy_turns()
                if random()>.5:
                    engine.player.fighter.heal(2)

            if engine.game_map:
                engine.update_fov()
                engine.game_map.make_turn()


def main():
    engine, screen_width, screen_height, tileset = start()

    with tcod.context.new_terminal(screen_width, screen_height, tileset=tileset, title="Game21", vsync=True) as context:
        root_console = tcod.console.Console(screen_width, screen_height, order="F")
        engine.context = context
        engine.console = root_console
        try:
            game_loop(engine, root_console, context)
        except Exception:
            traceback.print_exc()
            engine.messages.add(traceback.format_exc(), Color.error)

if __name__ == "__main__":
    main()
