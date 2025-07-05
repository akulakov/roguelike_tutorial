Tutorial: Fragment of a fallen shrine

* main game loop:

https://github.com/akulakov/roguelike_tutorial/blob/42b0cf21138fe83cc69753de61b31c14a9e356b1/main.py#L11

The main loop does the following:

    * gets the action from the event handler and tries to perform it
    * handle enemy turns - see entity.Hostile.attack()
    * heal the player (todo - monsters should also self-heal)

It's good to look at input_handlers.EventHandler which has all the player commands.

* dungeon generator - procgen.py

https://github.com/akulakov/roguelike_tutorial/blob/42b0cf21138fe83cc69753de61b31c14a9e356b1/procgen.py#L212

generator does the following (it's getting too big and should be refactored into more functions?):

    * create an instance of GameMap (contains the array of dungeon level tiles, entities, etc.)
    * generate random rooms. Rooms are roughly located at 6 points evenly spread on the level but then their locations
    are randomized near those points. This is explained a bit more in README.
    * there's some complicated code that tries to make nice-looking tunnels and restarts from beginning if it fails.
    d places items and monsters in the new room
    * places stairs - up to two down-stairs and one up-stairs (this will be covered in a separate section)

    * creates a hidden room - this can currently be found with the 'Search' command but in the future it will be part
    of quests or special abilities or items to make it easier to find hidden rooms. Hidden room uses special logic to
    generate the tunnel that connects to either another tunnel or a room; it's probably better to reuse to same tunnel
    logic used for regular rooms.

    This is a good example of placing hidden_passage tile and then replacing it with a regular floor tile when
    (S)earched. Similar logic can be used for things like traps and doors and locked doors.
