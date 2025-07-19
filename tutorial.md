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

* special entities (NPCs and unique items)

    https://github.com/akulakov/roguelike_tutorial/blob/9d60ed8e977662720151ce67f25b35c121d4558d/entity.py#L456

    * Special entites have a unique `id` and usually will be `is_hostile=False` and there will
    probably be a handful of ways to tie them to a location, but for now the `_loc` attribute will have level and room
    number to generate the entity.

    * `SpecialLocs` below gathers classes with `_loc` attribute into a data structure to make it easier to place these entities.

* Containers (e.g. boxes)

    * 'o' command opens a container
    * on the left side, player inventory is shown, on the right side - container inventory. Items can be transferred by
        selecting them. PageUp / PageDown used to scroll.
    * the handler logic is the same as buying items from a shop, except that no prices are shown and player gold / box
        gold are not updated when items are transferred. From development POV it would have been easier to first
        implement the Box logic and then enhance it to support shopping from a seller, but instead I did it in reverse
        order, which also meant a lot of variable names had to be updated to be more generalized.
    * equipped items are not shown in the list.

    * https://github.com/akulakov/roguelike_tutorial/blob/0203d5dc5ab902628ed07a5d27035d7740c55d49/input_handlers.py#L366

        * in on_render, a few variables are initialized and the player items are printed on the left side, then
        container items are printed on the left, note the `i` variable is kept after the first loop to continue item
        keys sequentially (e.g. if player items are a,b,c -- container items continue as d,e,f,...).

        * on `ev_keydown`, we first handle PAGEDOWN, PAGEUP, then we get the item by index, and remove from originating
        inventory and add to target inventory.

        * This may be confusing: even for the container, we run `check_gold` validator, but it will always return True
        for containers. Similarly `money_transfer` does not perform any action for containers.
