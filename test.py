import binarytree
class Node:
    left = right = val = None
    def __init__(self):
        self.val = randint(1,100)
    def __repr__(self):
        return self.val

from random import randint, choice
root = binarytree.Node(randint(1,100))
root.lev=0
def add(root, lev=0):
    n = choice(('left', 'right'))
    node = getattr(root, n)
    lev += 1
    if node:
        add(node, lev)
    else:
        node = binarytree.Node(randint(1,100))
        node.lev = lev
        setattr(root, n, node)

for _ in range(15):
    add(root)

# print(root)

n = root.left.right
# print("n", n.value, n.lev)

def trav(node, st, st_node, lev):
    if not node:
        return
    if node==st_node:
        st = True
    trav(node.left, st, st_node, lev)
    trav(node.right, st, st_node, lev)
    if st and node.lev==lev:
        print(node.value)

# trav(root, True, n, n.lev)

t = binarytree.tree(height=4, is_perfect=True)
print(t)
