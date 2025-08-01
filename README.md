Roguelike tutorial

This tutorial is to some degree based on the excellent tcod-tutorial (TStand90), it has the same functionality at the
end of that tutorial and the goal is to push it further.

Installing and running
-----------------------------------------------------------------------------------------------

    * pip3 install -r requirements.txt
    * ./main.py

Some notable differences:

 - The structure of classes and inheritance is simplified.

 - fast-travel is added with `g`-direction command.

 - I prefer tunnels that do not cross and do not start at corners of rooms, so there is some logic that generates
     tunnels in a less random, more constrained way.

 - The levels branch out in a tree-like way.

 - `m` commands shows the map of levels.

Commands
-----------------------------------------------------------------------------------------------

 - <, > : up / down stairs

 - E : map editor
 - W : save current map as a named custom map
 - S : search
 - . : wait
 - Space : talk
 - v : history
 - # break  : break an item
 - m : map view
 - c : character view
 - i : inventory
 - d : drop
 - D : dig
 - o : open box / door
 - / : look
 - Q : quests
 - s : shop / trade with a shopkeeper

 - w : wall
 - x : floor
 - e / ESCAPE : back to normal mode
 - f : fill level with floor
 - F : fill level with walls
 - r : create a room
 - l : create a tunnel





