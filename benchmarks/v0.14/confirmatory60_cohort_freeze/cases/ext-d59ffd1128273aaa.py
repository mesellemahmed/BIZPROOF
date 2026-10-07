def deconstruct_with_lookup(self, lookup):
    path = "wagtail.blocks.StreamBlock"
    args = [
        [
            (name, lookup.add_block(block))
            for name, block in self.child_blocks.items()
        ]
    ]
    kwargs = self._constructor_kwargs
    return (path, args, kwargs)
