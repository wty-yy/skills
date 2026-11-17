"""Verify shared-layer attribution and prevent duplicate Docker accounting.

Quick Start:
    python3 -m unittest -v test_docker_usage
"""

import unittest

from docker_usage import attribute, chain_ids, flatten


class DockerUsageTests(unittest.TestCase):
    """Test physical allocation using an isolated Docker layout fixture."""

    def fixture(self):
        """Build two containers, two shared-base images, and one shared volume."""
        root = "/data/docker"
        containers = [
            {"id": "a", "name": "/alice", "state": "running", "upper_dir": root + "/overlay2/rw-a/diff", "log_path": root + "/containers/a/a-json.log", "image_id": "i-a", "mounts": [{"Name": "shared"}, {"Type": "bind", "Source": "/data/alice", "Destination": "/work"}]},
            {"id": "b", "name": "/bob", "state": "exited", "upper_dir": root + "/overlay2/rw-b/diff", "log_path": root + "/containers/b/local-logs/container.log", "image_id": "i-b", "mounts": [{"Name": "shared"}]},
        ]
        metadata = {"daemon": {"root": root}, "containers": containers,
            "images": [{"id": "i-a", "chain_ids": ["base", "a"]}, {"id": "i-b", "chain_ids": ["base", "b"]}],
            "layer_map": {"base": "base", "a": "a", "b": "b"},
            "volumes": [{"name": "shared", "mountpoint": root + "/volumes/shared/_data"}],
            "started_at": "start", "finished_at": "end", "elapsed_seconds": 1, "cpu_budget": {"threads": 2}}
        usage = {root: 400, root + "/overlay2/base/diff": 100, root + "/overlay2/a/diff": 50, root + "/overlay2/b/diff": 80,
            root + "/overlay2/rw-a/diff": 30, root + "/overlay2/rw-b/diff": 40,
            root + "/containers/a": 11, root + "/containers/a/a-json.log": 5, root + "/containers/a/a-json.log.1": 3,
            root + "/containers/b": 7, root + "/containers/b/local-logs": 5, root + "/volumes/shared/_data": 23}
        return metadata, usage

    def test_shared_layers_logs_and_volumes_are_not_added_twice(self):
        """Separate shared images, container logs, and a multiply mounted volume."""
        metadata, usage = self.fixture()
        report = attribute(metadata, usage)
        self.assertEqual(report["image_layer_union_bytes"], 230)
        self.assertEqual([image["layer_bytes"] for image in report["images"]], [150, 180])
        self.assertEqual([image["unique_layer_bytes"] for image in report["images"]], [50, 80])
        self.assertEqual(report["container_allocated_bytes"], 88)
        self.assertEqual(report["volume_data_bytes"], 23)
        self.assertEqual(report["other_bytes"], 59)
        alice = next(row for row in report["containers"] if row["name"] == "alice")
        self.assertEqual(alice["log_bytes"], 8)
        self.assertEqual(alice["allocated_bytes"], 41)
        self.assertEqual(set(report["volumes"][0]["containers"]), {"alice", "bob"})

    def test_missing_container_is_distinct_from_zero_usage(self):
        """Mark a container removed during the scan as unmeasured."""
        metadata, usage = self.fixture()
        del usage["/data/docker/overlay2/rw-a/diff"]
        report = attribute(metadata, usage)
        alice = next(row for row in report["containers"] if row["name"] == "alice")
        self.assertIsNone(alice["allocated_bytes"])
        self.assertEqual(report["missing_container_measurements"], ["alice"])

    def test_unmapped_layers_are_separate_from_known_images_and_init(self):
        """Expose residual overlay layers without treating init layers as images."""
        metadata, usage = self.fixture()
        usage["/data/docker/overlay2/unknown/diff"] = 20
        usage["/data/docker/overlay2/rw-a-init/diff"] = 3
        report = attribute(metadata, usage)
        self.assertEqual(report["init_layer_bytes"], 3)
        self.assertEqual(report["unmapped_layers"], [{"path": "/data/docker/overlay2/unknown/diff", "bytes": 20}])

    def test_docker_root_mapping(self):
        """Retain the Docker root when flattening mounted scan paths."""
        node = {"name": "/scan", "size": "4096B", "children": [{"name": "/scan/overlay2", "size": "1024B", "children": []}]}
        self.assertEqual(flatten(node, "/data/docker"), {"/data/docker": 4096, "/data/docker/overlay2": 1024})

    def test_chain_ids_keep_first_diff_and_depend_on_order(self):
        """Preserve the first layer digest and distinguish different layer orders."""
        first, second = "sha256:" + "1" * 64, "sha256:" + "2" * 64
        forward = chain_ids([first, second])
        self.assertEqual(forward[0], "1" * 64)
        self.assertNotEqual(forward[1], chain_ids([second, first])[1])
        self.assertEqual(len(forward[1]), 64)


if __name__ == "__main__":
    unittest.main()
