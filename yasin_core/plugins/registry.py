class PluginRegistry:

    def __init__(self):
        self.plugins = {}

    def register(self, plugin):
        self.plugins[plugin.name] = plugin

    def get(self, name):
        return self.plugins.get(name)

    def list(self):
        return list(self.plugins.keys())

    def discover(self, plugins_dir: str = "plugins") -> None:
        """Discover and auto-register YasinPlugin classes from a directory."""
        import os
        import sys
        import importlib.util
        from yasin_core.plugins.base import YasinPlugin

        if not os.path.exists(plugins_dir):
            return

        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)

        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            module_name = None

            if os.path.isfile(item_path) and item.endswith(".py") and not item.startswith("_"):
                module_name = item[:-3]
            elif os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                module_name = item

            if module_name:
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name,
                        os.path.join(plugins_dir, item if os.path.isfile(item_path) else f"{item}/__init__.py")
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)

                        # Inspect the module for classes inheriting from YasinPlugin
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, YasinPlugin)
                                and attr is not YasinPlugin
                            ):
                                try:
                                    plugin_instance = attr()
                                    self.register(plugin_instance)
                                except Exception:
                                    # Skip if instantiation fails due to constructor parameters
                                    pass
                except Exception:
                    # Ignore failures of individual plugin files so the system is resilient
                    pass
