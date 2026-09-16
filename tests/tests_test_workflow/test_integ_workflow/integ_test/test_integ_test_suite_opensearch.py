# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0
#
# The OpenSearch Contributors require contributions made to
# this file be licensed under the Apache-2.0 license or a
# compatible open source license.

import os
import unittest
from pathlib import Path
from typing import Any, Tuple
from unittest.mock import MagicMock, Mock, call, patch

from git.git_repository import GitRepository
from manifests.build_manifest import BuildManifest
from manifests.bundle_manifest import BundleComponent, BundleManifest
from manifests.test_manifest import TestComponent, TestManifest
from test_workflow.integ_test.integ_test_suite_opensearch import IntegTestSuiteOpenSearch, InvalidTestConfigError, ScriptFinder, Topology
from test_workflow.integ_test.topology import ClusterEndpoint, NodeEndpoint


@patch("os.makedirs")
@patch("os.chdir")
@patch.object(GitRepository, "__checkout__")
class TestIntegSuiteOpenSearch(unittest.TestCase):
    DATA = os.path.join(os.path.dirname(__file__), "data")
    BUILD_MANIFEST = os.path.join(DATA, "build_manifest.yml")
    BUNDLE_MANIFEST = os.path.join(DATA, "bundle_manifest.yml")
    TEST_MANIFEST = os.path.join(DATA, "test_manifest.yml")

    def setUp(self) -> None:
        os.chdir(os.path.dirname(__file__))
        self.bundle_manifest = BundleManifest.from_path(self.BUNDLE_MANIFEST)
        self.build_manifest = BuildManifest.from_path(self.BUILD_MANIFEST)
        self.test_manifest = TestManifest.from_path(self.TEST_MANIFEST)
        self.work_dir = Path("test_dir")

    @patch("os.path.exists", return_value=True)
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.IntegTestSuiteOpenSearch.multi_execute_integtest_sh")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.Topology")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_multiple_test_configs(self, mock_test_recorder: Mock, mock_topology: Mock, mock_multi_execute_integtest_sh: Mock, *mock: Any) -> None:
        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        dependency_installer = MagicMock()
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder
        )
        mock_topology.create().__enter__.return_value = [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}]
        mock_multi_execute_integtest_sh.return_value = "success"

        test_results = integ_test_suite.execute_tests()
        self.assertEqual(len(test_results), 2)
        self.assertTrue(test_results.failed)

        mock_multi_execute_integtest_sh.assert_has_calls([
            call([{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}], True, "with-security"),
            call([{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}], False, "without-security")
        ])

    @patch("test_workflow.integ_test.integ_test_suite_opensearch.IntegTestSuiteOpenSearch.multi_execute_integtest_sh")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.Topology")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_build_dependencies(self, mock_test_recorder: Mock, mock_topology: Mock, mock_multi_execute_integtest_sh: Mock, *mock: Any) -> None:
        dependency_installer = MagicMock()
        test_config, component = self.__get_test_config_and_bundle_component("index-management")
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder
        )

        mock_topology.create().__enter__.return_value = [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}]

        mock_multi_execute_integtest_sh.return_value = "success"

        integ_test_suite.execute_tests()
        dependency_installer.install_build_dependencies.assert_called_with(
            {"opensearch-job-scheduler": "1.1.0.0"}, os.path.join(self.work_dir, "index-management", "src", "test", "resources", "job-scheduler")
        )

        mock_multi_execute_integtest_sh.assert_has_calls([call(
            [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}], False, "without-security")]
        )

    @patch("test_workflow.integ_test.integ_test_suite_opensearch.IntegTestSuiteOpenSearch.multi_execute_integtest_sh")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.execute")
    def test_execute_without_build_dependencies(self, mock_execute: Mock, *mock: Any) -> None:
        dependency_installer = MagicMock()
        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        mock_test_recorder = MagicMock()
        mock_test_results_logs = MagicMock()
        mock_test_recorder.test_results_logs.return_value = mock_test_results_logs

        mock_create = MagicMock()
        mock_create.return_value.__enter__.return_value = [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "test", "port": 1234, "transport": 4321}], "cluster_manager_nodes": []}]

        Topology.create = mock_create  # type: ignore

        mock_execute.return_value = ("test_status", "test_stdout", "")

        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder)

        integ_test_suite.execute_tests()

        dependency_installer.install_build_dependencies.assert_not_called()

    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_unsupported_build_dependencies(self, mock_test_recorder: Mock, *mock: Any) -> None:
        dependency_installer = MagicMock()
        test_config, component = self.__get_test_config_and_bundle_component("anomaly-detection")
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder
        )
        with self.assertRaises(InvalidTestConfigError):
            integ_test_suite.execute_tests()
        dependency_installer.install_build_dependencies.assert_not_called()

    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_missing_job_scheduler(self, mock_test_recorder: Mock, mock_install_build_dependencies: Mock, *mock: Any) -> None:
        invalid_build_manifest = BuildManifest.from_path("data/build_manifest_missing_components.yml")
        test_config, component = self.__get_test_config_and_bundle_component("index-management")
        dependency_installer = MagicMock()
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer, component, test_config, self.bundle_manifest, invalid_build_manifest, self.work_dir, mock_test_recorder
        )
        with self.assertRaises(KeyError) as ctx:
            integ_test_suite.execute_tests()

        self.assertEqual(str(ctx.exception), "'job-scheduler'")
        dependency_installer.install_build_dependencies.assert_not_called()

    def __get_test_config_and_bundle_component(self, component_name: str) -> Tuple[TestComponent, BundleComponent]:
        component = self.bundle_manifest.components[component_name]
        test_config = self.test_manifest.components[component.name]
        return test_config, component

    @patch("os.path.exists", return_value=True)
    @patch.object(ScriptFinder, "find_integ_test_script")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.IntegTestSuiteOpenSearch.multi_execute_integtest_sh")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.Topology")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_execute_with_working_directory(self, mock_test_recorder: Mock, mock_topology: Mock, mock_multi_execute_integtest_sh: Mock, mock_script_finder: Mock, *mock: Any) -> None:
        test_config, component = self.__get_test_config_and_bundle_component("dashboards-reports")
        dependency_installer = MagicMock()
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder
        )

        mock_topology.create().__enter__.return_value = [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}]
        mock_script_finder.return_value = "integtest.sh"

        mock_multi_execute_integtest_sh.return_value = "success"

        integ_test_suite.execute_tests()  # type: ignore

        mock_multi_execute_integtest_sh.assert_called_with(
            [{"cluster_name": "cluster1", "data_nodes": [{"endpoint": "localhost", "port": 9200, "transport": 9300}], "cluster_manager_nodes": []}],
            True,
            "with-security"
        )

    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.TestResultData")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.GitRepository.__checkout__")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.execute", return_value=True)
    def test_multi_execute_integtest_sh(self, mock_execute: Mock, mock_git: Mock, mock_test_result_data: Mock,
                                        mock_test_recorder: Mock, mock_makedirs: Mock, mock_path_exists: Mock, *mock: Any) -> None:
        mock_find = MagicMock()
        mock_find.return_value = "./integtest.sh"

        ScriptFinder.find_integ_test_script = mock_find  # type: ignore

        mock_execute.return_value = ("test_status", "test_stdout", "")

        mock_test_result_data_object = MagicMock()
        mock_test_result_data.return_value = mock_test_result_data_object
        mock_path_exists.return_value = True

        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        dependency_installer = MagicMock()
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            mock_test_recorder
        )

        self.assertEqual(integ_test_suite.repo.url, "https://github.com/opensearch-project/job-scheduler.git")
        self.assertEqual(integ_test_suite.repo.ref, "4504dabfc67dd5628c1451e91e9a1c3c4ca71525")
        integ_test_suite.repo.dir = "dir"

        # call the test target
        mock_endpoint = MagicMock()
        mock_data_node = MagicMock()
        mock_data_node.endpoint = "localhost"
        mock_data_node.port = 9200
        mock_data_node.transport = 9300
        mock_endpoint.data_nodes = [mock_data_node]
        status = integ_test_suite.multi_execute_integtest_sh([mock_endpoint], True, "with-security")

        mock_find.assert_called()
        self.assertEqual(status, "test_status")
        mock_execute.assert_called()

        mock_test_result_data.assert_called_once_with(
            "job-scheduler",
            "with-security",
            "test_status",
            "test_stdout",
            "",
            {
                "opensearch-integ-test": os.path.join("dir", "build", "reports", "tests", "integTest")
            }
        )

        assert (mock_test_result_data.return_value in integ_test_suite.result_data)
        self.assertEqual(integ_test_suite.additional_cluster_config, None)

    @patch("os.path.exists", return_value=True)
    @patch("os.walk", return_value=[(os.path.join("/some", "path"), ["build"], ["integTest", "integrationTest", "integTestRemote"])])
    def test_test_artifact_files_default(self, *mocks: Any) -> None:
        dependency_installer = MagicMock()
        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            MagicMock()
        )
        integ_test_suite.repo_work_dir = os.path.join("/some", "path")
        expected_path = {
            "opensearch-integ-test": os.path.join("/some", "path", "build", "reports", "tests", "integTest")
        }
        result = integ_test_suite.test_artifact_files
        self.assertEqual(result, expected_path)

    @patch("os.path.exists", return_value=False)
    @patch("os.walk", return_value=[])
    def test_test_artifact_files_no_default_path(self, *mocks: Any) -> None:
        dependency_installer = MagicMock()
        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        integ_test_suite = IntegTestSuiteOpenSearch(
            dependency_installer,
            component,
            test_config,
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            MagicMock()
        )
        integ_test_suite.repo_work_dir = os.path.join("/some", "path")
        default_path = os.path.join(integ_test_suite.repo_work_dir, "build", "reports", "tests", "integTest")
        expected_path = {"opensearch-integ-test": default_path}
        result = integ_test_suite.test_artifact_files
        self.assertEqual(result, expected_path)

    def test_test_report_dirs(self, *mocks: Any) -> None:
        integ_test_suite = IntegTestSuiteOpenSearch(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            self.bundle_manifest,
            self.build_manifest,
            self.work_dir,
            MagicMock()
        )
        self.assertEqual(integ_test_suite.additional_test_report_dirs, ["integTest", "integrationTest", "integTestRemote"])

    def __make_endpoint(self, host: str, port: int, transport: int) -> Any:
        endpoint = MagicMock()
        data_node = MagicMock()
        data_node.endpoint = host
        data_node.port = port
        data_node.transport = transport
        endpoint.data_nodes = [data_node]
        return endpoint

    @patch("os.path.exists", return_value=True)
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.TestResultData")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.execute")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_multi_execute_integtest_sh_sharded(self, mock_test_recorder: Mock, mock_execute: Mock,
                                                mock_test_result_data: Mock, *mock: Any) -> None:
        """When sharding is enabled and there are multiple clusters, run one invocation per shard with -g/-t."""
        ScriptFinder.find_integ_test_script = MagicMock(return_value="./integtest.sh")  # type: ignore
        mock_execute.return_value = (0, "stdout", "")

        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        integ_test_suite = IntegTestSuiteOpenSearch(
            MagicMock(), component, test_config, self.bundle_manifest, self.build_manifest, self.work_dir, mock_test_recorder
        )
        integ_test_suite.repo.dir = "dir"
        # Force sharded mode via the raw integ_test dict the code reads.
        integ_test_suite.test_config = MagicMock()
        integ_test_suite.test_config.working_directory = None
        integ_test_suite.test_config.integ_test = {"sharding": True}

        endpoints = [
            self.__make_endpoint("host0", 9200, 9300),
            self.__make_endpoint("host1", 9201, 9301),
        ]

        status = integ_test_suite.multi_execute_integtest_sh(endpoints, True, "with-security")

        # Merged status is 0 when all shards pass.
        self.assertEqual(status, 0)
        # Two shard invocations.
        self.assertEqual(mock_execute.call_count, 2)
        issued_cmds = sorted(c.args[0] for c in mock_execute.call_args_list)
        # Shard 0 -> host0, -g 0 -t 2 ; Shard 1 -> host1, -g 1 -t 2
        self.assertTrue(any("-b host0 -p 9200" in c and "-g 0 -t 2" in c for c in issued_cmds))
        self.assertTrue(any("-b host1 -p 9201" in c and "-g 1 -t 2" in c for c in issued_cmds))
        # Per-shard result data recorded for both shards.
        self.assertEqual(mock_test_result_data.call_count, 2)

    @patch("os.path.exists", return_value=True)
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.TestResultData")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.execute")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_multi_execute_integtest_sh_sharded_merge_failure(self, mock_test_recorder: Mock, mock_execute: Mock,
                                                              mock_test_result_data: Mock, *mock: Any) -> None:
        """A single failing shard fails the merged status."""
        ScriptFinder.find_integ_test_script = MagicMock(return_value="./integtest.sh")  # type: ignore
        # First shard passes, second fails.
        mock_execute.side_effect = [(0, "ok", ""), (1, "fail", "err")]

        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        integ_test_suite = IntegTestSuiteOpenSearch(
            MagicMock(), component, test_config, self.bundle_manifest, self.build_manifest, self.work_dir, mock_test_recorder
        )
        integ_test_suite.repo.dir = "dir"
        integ_test_suite.test_config = MagicMock()
        integ_test_suite.test_config.working_directory = None
        integ_test_suite.test_config.integ_test = {"sharding": True}

        endpoints = [
            self.__make_endpoint("host0", 9200, 9300),
            self.__make_endpoint("host1", 9201, 9301),
        ]

        status = integ_test_suite.multi_execute_integtest_sh(endpoints, False, "without-security")
        self.assertEqual(status, 1)

    @patch("os.path.exists", return_value=True)
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.TestResultData")
    @patch("test_workflow.integ_test.integ_test_suite_opensearch.execute")
    @patch("test_workflow.test_recorder.test_recorder.TestRecorder")
    def test_multi_execute_integtest_sh_sharding_off_single_call(self, mock_test_recorder: Mock, mock_execute: Mock,
                                                                 mock_test_result_data: Mock, *mock: Any) -> None:
        """Without the sharding flag, multiple endpoints use the single -e multi-cluster call (no -g/-t)."""
        ScriptFinder.find_integ_test_script = MagicMock(return_value="./integtest.sh")  # type: ignore
        mock_execute.return_value = (0, "stdout", "")

        test_config, component = self.__get_test_config_and_bundle_component("job-scheduler")
        integ_test_suite = IntegTestSuiteOpenSearch(
            MagicMock(), component, test_config, self.bundle_manifest, self.build_manifest, self.work_dir, mock_test_recorder
        )
        integ_test_suite.repo.dir = "dir"
        integ_test_suite.test_config = MagicMock()
        integ_test_suite.test_config.working_directory = None
        integ_test_suite.test_config.integ_test = {}  # sharding not set

        endpoints = [
            ClusterEndpoint("cluster0", [NodeEndpoint("host0", 9200, 9300)], []),
            ClusterEndpoint("cluster1", [NodeEndpoint("host1", 9201, 9301)], []),
        ]

        integ_test_suite.multi_execute_integtest_sh(endpoints, True, "with-security")

        # Exactly one invocation, using -e, and no shard coordinates.
        self.assertEqual(mock_execute.call_count, 1)
        cmd = mock_execute.call_args_list[0].args[0]
        self.assertIn(" -e '", cmd)
        self.assertNotIn("-g ", cmd)
        self.assertNotIn("-t ", cmd)
