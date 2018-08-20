from utils import Node


class TestNodes(object):
    """ Test class for the functionality of the node class"""

    def setup_method(self):
        self.root_node = Node('Test')

    def test_contains(self):
        result = 'Test' in self.root_node
        assert(result is True)

    def test_add_child(self):
        new_node = Node('test_add_child')
        self.root_node.add_child(new_node)
        assert(new_node in self.root_node.children)
        assert(new_node.parent is self.root_node)

    def test_set_parent(self):
        new_node = Node('test_set_parent')
        new_node.set_parent(self.root_node)
        assert(new_node in self.root_node.children)
        assert(new_node.parent is self.root_node)

    def test_nested_contains(self):
        child = Node('test_nested_contains')
        self.root_node.add_child(child)
        result = 'test_nested_contains' in self.root_node
        assert(result is True)

    def test_get_node_by_content(self):
        child = Node('test_get_node_by_content')
        self.root_node.add_child(child)
        result = self.root_node.get_node_by_content('test_get_node_by_content')
        assert(result is child)

    def test_get_descendants(self):
        child = Node('test_get_descendants_child')
        grand_child = Node('test_get_descendants_grand_child')
        child.add_child(grand_child)
        self.root_node.add_child(child)
        result = self.root_node.get_descendants()
        assert(all(c in result for c in [child, grand_child]))

    def test_get_ancestors(self):
        child = Node('test_get_ancestors_child')
        grand_child = Node('test_get_descendants_grand_child')
        child.add_child(grand_child)
        self.root_node.add_child(child)
        result = grand_child.get_ancestors()
        assert(all(p in result for p in [child, self.root_node]))

    def test_remove_node(self):
        node_to_remove = Node('test_remove_node')
        self.root_node.add_child(node_to_remove)
        self.root_node.remove_node(node_to_remove, False)
        assert(node_to_remove not in self.root_node.children)

    def test_remove_node_cascading(self):
        node_to_remove = Node('test_remove_node')
        self.root_node.add_child(node_to_remove)
        dummy_children = []
        for i in range(5):
            c = Node(str(i))
            dummy_children.append(c)
            node_to_remove.add_child(c)
        self.root_node.remove_node(node_to_remove, True)
        assert(node_to_remove not in self.root_node.children)
        assert(all(c.content not in self.root_node for c in dummy_children))
