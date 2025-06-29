Roguelike tutorial

This tutorial is to some degree based on the excellent tcod-tutorial (TStand90), it has the same functionality at the
end of that tutorial and the goal is to push it further.

Some notable differences:

 - The structure of classes and inheritance is simplified.

 - fast-travel is added with `g`-direction command.

 - I prefer tunnels that do not cross and do not start at corners of rooms, so there is some logic that generates
     tunnels in a less random, more constrained way.

 - The levels branch out in a tree-like way.

 - `m` commands shows the map of levels.
