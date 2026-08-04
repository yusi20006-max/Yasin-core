from typing import Any, Dict, List, Callable, Tuple, Optional
from yasin_core.compatibility.exceptions import MigrationError
from yasin_core.compatibility.version import Version


class SchemaMigrator:
    """
    Handles schema migrations from previous versions to newer versions.
    Allows registering migration functions for specific version jumps and
    automatically resolves a chain of migrations (e.g. 1.0 -> 3.0 via 1.0->2.0->3.0).
    """

    def __init__(self):
        # Maps (from_version, to_version) -> migration_callback
        self._migrations: Dict[Tuple[str, str], Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_migration(
        self,
        from_version: str,
        to_version: str,
        callback: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Register a callback to migrate schema from from_version to to_version."""
        self._migrations[(from_version, to_version)] = callback

    def _find_migration_path(self, start: str, end: str) -> List[Tuple[str, str]]:
        """
        Find a path of version jumps from start to end using a BFS/DFS search.
        """
        if start == end:
            return []

        # Simple adjacency list
        graph: Dict[str, List[str]] = {}
        for (f_ver, t_ver) in self._migrations.keys():
            if f_ver not in graph:
                graph[f_ver] = []
            graph[f_ver].append(t_ver)

        # BFS to find shortest path
        queue = [[start]]
        visited = {start}

        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node == end:
                # Convert list of nodes to list of edges
                return [(path[i], path[i+1]) for i in range(len(path)-1)]

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = list(path) + [neighbor]
                    queue.append(new_path)

        raise MigrationError(f"No migration path found from version '{start}' to '{end}'")

    def migrate(self, data: Dict[str, Any], current_version: str, target_version: str) -> Dict[str, Any]:
        """
        Migrate dictionary/schema from current_version to target_version.
        """
        if current_version == target_version:
            return dict(data)

        path = self._find_migration_path(current_version, target_version)
        migrated_data = dict(data)

        for (f_ver, t_ver) in path:
            callback = self._migrations[(f_ver, t_ver)]
            try:
                migrated_data = callback(migrated_data)
            except Exception as e:
                raise MigrationError(f"Failed migrating schema from '{f_ver}' to '{t_ver}': {e}") from e

        return migrated_data


class ConfigurationMigrator:
    """
    Helper for migrating configurations (Settings YAML/dictionaries) from old formats to new formats.
    """

    @staticmethod
    def migrate_config(
        config_data: Dict[str, Any],
        key_renames: Optional[Dict[str, str]] = None,
        default_injects: Optional[Dict[str, Any]] = None,
        custom_migrator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Migrate config_data using rename mappings, default injections, and custom migrators.
        """
        migrated = dict(config_data)

        # 1. Apply key renames
        if key_renames:
            for old_key, new_key in key_renames.items():
                if old_key in migrated:
                    val = migrated.pop(old_key)
                    # Support nested dictionary setting
                    if "." in new_key:
                        parts = new_key.split(".")
                        current = migrated
                        for part in parts[:-1]:
                            if part not in current or not isinstance(current[part], dict):
                                current[part] = {}
                            current = current[part]
                        current[parts[-1]] = val
                    else:
                        migrated[new_key] = val

        # 2. Inject defaults
        if default_injects:
            for k, val in default_injects.items():
                if "." in k:
                    parts = k.split(".")
                    current = migrated
                    for part in parts[:-1]:
                        if part not in current or not isinstance(current[part], dict):
                            current[part] = {}
                        current = current[part]
                    if parts[-1] not in current:
                        current[parts[-1]] = val
                else:
                    if k not in migrated:
                        migrated[k] = val

        # 3. Apply custom migration lambda / function
        if custom_migrator:
            migrated = custom_migrator(migrated)

        return migrated


class DataMigrator:
    """
    Helper to migrate application data records or storage blocks.
    """

    @staticmethod
    def migrate_records(
        records: List[Dict[str, Any]],
        transformer: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply a transformer function to a list of records to migrate them safely.
        """
        migrated_records = []
        for r in records:
            try:
                migrated_records.append(transformer(dict(r)))
            except Exception as e:
                raise MigrationError(f"Failed to migrate record {r}: {e}") from e
        return migrated_records
