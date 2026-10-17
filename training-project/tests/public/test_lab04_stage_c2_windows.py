"""Windows handle-anchored output tests, runnable without a Windows host."""
import unittest
from pathlib import PureWindowsPath
from unittest.mock import patch

from learning_project import lab04_retrieval as c2
from learning_project.workflow import WorkflowError


class FakeWindowsFiles:
    def __init__(self):
        self.directories = {PureWindowsPath('C:\\'), PureWindowsPath('C:\\reports')}
        self.reparse = set()
        self.files = {}
        self.held = set()
        self.opens = []
        self.attempted_swap = False
        self.swap_on_create = False

    def open_directory(self, path):
        self.opens.append(path)
        if path not in self.directories or path in self.reparse:
            raise OSError('missing or reparse directory')
        handle = ('directory', path)
        self.held.add(handle)
        return handle

    def make_directory(self, path):
        if path in self.directories or path in self.reparse:
            raise FileExistsError(path)
        self.directories.add(path)

    def create_file(self, path):
        if self.swap_on_create:
            self.attempted_swap = True
            if ('directory', path.parent) not in self.held:
                self.directories.remove(path.parent)
                raise AssertionError('unanchored directory replacement')
        if path in self.files:
            raise FileExistsError(path)
        if ('directory', path.parent) not in self.held:
            raise AssertionError('parent not held')
        self.files[path] = bytearray()
        handle = ('file', path)
        self.held.add(handle)
        return handle

    def write(self, handle, data):
        assert handle in self.held
        self.files[handle[1]].extend(data)

    def close(self, handle):
        self.held.remove(handle)


class WindowsCreation(unittest.TestCase):
    def setUp(self):
        self.api = FakeWindowsFiles()
        self.report = PureWindowsPath('C:\\reports')
        self.output = self.report / 'stage-c2' / 'result.json'

    def test_creates_utf8_once_with_all_handles_closed(self):
        c2._write_stage_c2_windows(self.output, 'é\n', self.report, self.api)
        self.assertEqual(bytes(self.api.files[self.output]), 'é\n'.encode())
        self.assertFalse(self.api.held)

    def test_existing_file_is_refused_and_handles_close(self):
        self.api.files[self.output] = bytearray(b'original')
        with self.assertRaises(WorkflowError):
            c2._write_stage_c2_windows(self.output, 'new', self.report, self.api)
        self.assertEqual(self.api.files[self.output], b'original')
        self.assertFalse(self.api.held)

    def test_reparse_component_is_refused(self):
        self.api.reparse.add(self.report)
        with self.assertRaises(WorkflowError):
            c2._write_stage_c2_windows(self.output, 'new', self.report, self.api)
        self.assertFalse(self.api.files)
        self.assertFalse(self.api.held)

    def test_reparse_stage_directory_is_refused(self):
        stage = self.output.parent
        self.api.directories.add(stage)
        self.api.reparse.add(stage)
        with self.assertRaises(WorkflowError):
            c2._write_stage_c2_windows(self.output, 'new', self.report, self.api)
        self.assertFalse(self.api.files)
        self.assertFalse(self.api.held)

    def test_parent_replacement_attempt_cannot_redirect(self):
        self.api.swap_on_create = True
        c2._write_stage_c2_windows(self.output, 'safe', self.report, self.api)
        self.assertTrue(self.api.attempted_swap)
        self.assertEqual(self.api.files[self.output], b'safe')
        self.assertFalse(self.api.held)

    def test_parent_traversal_is_refused_before_open(self):
        report = PureWindowsPath('C:\\reports\\..\\outside')
        with self.assertRaises(WorkflowError):
            c2._write_stage_c2_windows(report / 'stage-c2' / 'result.json', 'unsafe', report, self.api)
        self.assertFalse(self.api.held)
        self.assertFalse(self.api.files)
        self.assertFalse(self.api.opens)

    def test_unc_root_components_remain_held_through_create(self):
        report = PureWindowsPath('\\\\host\\share\\reports')
        output = report / 'stage-c2' / 'result.json'
        self.api.directories = {PureWindowsPath('\\\\host\\share\\'), report}
        c2._write_stage_c2_windows(output, 'safe', report, self.api)
        self.assertEqual(self.api.files[output], b'safe')
        self.assertEqual(self.api.opens[:2], [PureWindowsPath('\\\\host\\share\\'), report])
        self.assertFalse(self.api.held)

    def test_write_failure_closes_every_handle(self):
        class FailingWrite(FakeWindowsFiles):
            def write(self, handle, data):
                raise OSError('disk full')
        api = FailingWrite()
        with self.assertRaises(WorkflowError):
            c2._write_stage_c2_windows(self.output, 'data', self.report, api)
        self.assertFalse(api.held)

    def test_dispatches_windows_route(self):
        with patch.object(c2.os, 'name', 'nt'), patch.object(c2, '_windows_filesystem', return_value=self.api):
            c2._write_stage_c2_output(self.output, 'safe', self.report)
        self.assertEqual(self.api.files[self.output], b'safe')
