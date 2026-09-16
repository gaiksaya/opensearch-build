# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.

import os
import unittest

import yaml

from manifests.test_manifest import TestManifest


class TestTestManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        self.data_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "data"))
        self.manifest_filename = os.path.join(self.data_path, "opensearch-2.18.0-test.yml")
        self.manifest = TestManifest.from_path(self.manifest_filename)

    def test_component(self) -> None:
        component_as = self.manifest.components["asynchronous-search"]
        self.assertEqual(component_as.name, "asynchronous-search")
        self.assertEqual(component_as.integ_test, {"test-configs": ["with-security", "without-security"]})
        self.assertEqual(component_as.bwc_test, {"test-configs": ["with-security"]})
        component_os = self.manifest.components["opensearch"]
        self.assertEqual(component_os.name, "opensearch")
        self.assertEqual(component_os.smoke_test, {"test-spec": "opensearch.yml"})

    def test_component_with_working_directory(self) -> None:
        component = self.manifest.components["notifications"]
        self.assertEqual(component.name, "notifications")
        self.assertEqual(component.working_directory, "notifications")
        self.assertEqual(component.integ_test, {"test-configs": ["with-security", "without-security"]})
        self.assertEqual(component.bwc_test, {"test-configs": ["with-security"]})

    def test_to_dict(self) -> None:
        data = self.manifest.to_dict()
        with open(self.manifest_filename) as f:
            self.assertEqual(yaml.safe_load(f), data)

    def test_versions(self) -> None:
        self.assertTrue(len(TestManifest.VERSIONS))
        for version in TestManifest.VERSIONS:
            manifest = TestManifest.from_path(os.path.join(self.data_path, "test", f"opensearch-test-schema-version-{version}.yml"))
            self.assertEqual(version, manifest.version)

    def test_integ_test_sharding_field(self) -> None:
        data = {
            "schema-version": "1.1",
            "name": "OpenSearch",
            "components": [
                {
                    "name": "k-NN",
                    "integ-test": {
                        "test-configs": ["with-security", "without-security"],
                        "sharding": True,
                        "topology": [
                            {"cluster_name": "cluster0", "data_nodes": 1},
                            {"cluster_name": "cluster1", "data_nodes": 1},
                        ],
                    },
                }
            ],
        }
        # Should validate against the 1.1 schema and expose the sharding flag on the raw integ_test dict.
        manifest = TestManifest(data)
        component = manifest.components["k-NN"]
        self.assertTrue(component.integ_test.get("sharding"))
        self.assertEqual(len(component.topology.cluster_configs), 2)
