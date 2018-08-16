from typing import List, Optional


class Node(object):
    """ A tree node class for the DDos prevention chain.
        Each node has a content of type string,
        a parent of type Node (None if root node)
        and a list of children (type: List[Node])
        Args:
            content: The content of the node
    """

    def __init__(self, content: str):
        self.content: str = content
        self.parent: Node = None
        self.children: List[Node] = []

    def set_parent(self, parent: 'Node'):
        """ Sets the parent of this node, and adds itself to the
            list of children of the parent (if the parent is not None)
            Args:
                parent: The new parent node
        """
        if parent == self.parent:
            return
        self.parent = parent
        if parent is not None:
            self.parent.add_child(self)

    def add_child(self, child: 'Node'):
        """ Adds a child node to the list of children, and sets
            the parent of the new node to self.
            Args:
                child: the new child node
        """
        if child in self.children:
            return
        self.children.append(child)
        child.set_parent(self)

    def __contains__(self, item: str) -> bool:
        """ Checks whether or not a given string is contained
            within the tree.
            Args:
                item: The string to search for
            Returns: True if the string is found, false else
        """
        if self.content == item:
            return True
        for child in self.children:
            return item in child
        return False

    def get_node_by_content(self, content: str) -> Optional['Node']:
        """ Searches a node by finding the given content.
            Args:
                content: the content to search for.
            Returns: The corresponding node if the content was found, None else
        """
        if self.content == content:
            return self
        for child in self.children:
            return child.get_node_by_content(content)
        return None

    def remove_node(self, node: 'Node', cascading: bool):
        """ Removes a node from the tree and handles the descendants accordingly.
            Args:
                node: The node to remove.
                cascading: If true, deletes all descendants of the node,
                            if false, adds all children of the node to the
                            nodes' parents' children.
            Raises a ValueError if the node to be deleted equals the node
            on which the function is called. This prevents deleting the
            root node of a tree
        """
        if self is node:
            raise ValueError("A Node cannot delete itself")
        parent = node.get_parent()
        parent.children.remove(node)
        if not cascading:
            for child in node.get_children():
                child.set_parent(parent)
            node.children = []
        else:
            for descendant in node.get_descendants():
                descendant.parent = None
                descendant.children = []
            node.children = []

    def get_children(self) -> List['Node']:
        """ Returns all direct children of the node
        """
        return self.children

    def get_parent(self) -> 'Node':
        """ Returns the parent node of the node
        """
        return self.parent

    def get_descendants(self) -> List['Node']:
        """ Returns all descendants of the node
        """
        descendants = self.children[:]
        for child in self.children:
            descendants += child.get_descendants()
        return descendants

    def get_ancestors(self) -> List['Node']:
        """ Returns all ancestors of the node
        """
        if self.parent is None:
            return []
        ancestors = [self.parent]
        ancestors += self.parent.get_ancestors()
        return ancestors
