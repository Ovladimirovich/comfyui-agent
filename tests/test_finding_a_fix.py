"""Tests for Finding A fix: Asset creation AFTER verification.

AD-MODEL-BINDING-001 / Production Audit Finding A:
Verify that Assets are NOT created before verification passes.

Key invariant:
  execution -> validation -> Verifier.verify -> AssetStore.ingest -> SUCCESS

On failure at ANY validation phase:
  - Job.state = FAILED
  - store.ingest() is NOT called
  - 0 canonical Assets in store
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
import tempfile
import os

from app.assets.store import AssetStore
from app.engine.engine import WorkflowEngine
from app.engine.job import JobState
from app.engine.verifier import Verifier, VerificationError
from app.engine.plan import ExecutionPlan
from app.registry.workflow import Workflow, OutputSpec


class TestFindingAFix_AssetCreationAfterVerification:
    """Test that Assets are created ONLY after verification passes."""

    def test_byte_validation_failure_prevents_ingest(self):
        """Phase 1 failure (byte validation): NO ingest called."""
        store = AssetStore(root='__test_finding_a_phase1__')
        engine = WorkflowEngine(store)

        provider = MagicMock()
        provider.backend_id = 'local_comfyui'
        # Invalid PNG data - fails byte validation
        provider.view.return_value = b'invalid data'

        manifest = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            required_models=[], required_custom_nodes=[],
            requirements={}
        )

        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='test',
            version='1.0.0',
        )

        executed = {
            '9': {
                'images': [{'filename': 'test.png', 'subfolder': '', 'type': 'output'}]
            }
        }

        ingest_calls = []
        original_ingest = store.ingest
        def tracking_ingest(*args, **kwargs):
            ingest_calls.append(call(*args, **kwargs))
            return original_ingest(*args, **kwargs)

        with patch.object(provider, 'execute', return_value='test-prompt-id'):
            with patch.object(engine.store, 'ingest', side_effect=tracking_ingest):
                with patch('app.engine.engine.ComfyUIWebSocket') as mock_ws:
                    mock_ws_instance = MagicMock()
                    mock_ws.return_value = mock_ws_instance
                    mock_ws_instance.track.return_value = {}

                    with patch.object(engine, '_history_outputs', return_value=executed):
                        with patch.object(engine, '_history_status', return_value='success'):
                            try:
                                job = engine.execute(manifest, plan, provider=provider)
                                pytest.fail('Expected exception on invalid bytes')
                            except Exception:
                                pass  # Expected

        assert len(ingest_calls) == 0, f'Expected 0 ingest calls on Phase 1 failure, got {len(ingest_calls)}'

    def test_verifier_failure_prevents_ingest_real_path(self):
        """Phase 2 failure (Verifier): NO ingest called - uses REAL Verifier.

        This test proves the invariant by making Verifier fail naturally:
        - Byte validation passes (valid PNG)
        - Temp file is created
        - But we patch os.path.exists to return False AFTER file creation
        - Verifier.verify() fails because asset.path doesn't exist
        - ingest() is NEVER called
        """
        store = AssetStore(root='__test_finding_a_phase2__')
        engine = WorkflowEngine(store)

        provider = MagicMock()
        provider.backend_id = 'local_comfyui'
        # Valid PNG data - passes byte validation
        provider.view.return_value = b'\x89PNG\r\n\x1a\n'

        manifest = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            required_models=[], required_custom_nodes=[],
            requirements={}
        )

        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='test',
            version='1.0.0',
        )

        executed = {
            '9': {
                'images': [{'filename': 'test.png', 'subfolder': '', 'type': 'output'}]
            }
        }

        ingest_calls = []
        original_ingest = store.ingest
        def tracking_ingest(*args, **kwargs):
            ingest_calls.append(call(*args, **kwargs))
            return original_ingest(*args, **kwargs)

        # Track temp files created
        temp_files_created = []
        original_named_temp = tempfile.NamedTemporaryFile
        def tracking_named_temp(*args, **kwargs):
            tmp = original_named_temp(*args, **kwargs)
            temp_files_created.append(tmp.name)
            return tmp

        # Patch os.path.exists to return False after Phase 1
        # This makes Verifier fail naturally (asset.path doesn't exist)
        original_exists = os.path.exists
        exists_call_count = [0]
        def fake_exists(path):
            exists_call_count[0] += 1
            # First call is for _validate_output_bytes (should return True for valid data)
            # Subsequent calls are for Verifier (should return False to simulate failure)
            if exists_call_count[0] > 1:
                return False
            return original_exists(path)

        with patch.object(provider, 'execute', return_value='test-prompt-id'):
            with patch.object(engine.store, 'ingest', side_effect=tracking_ingest):
                with patch('tempfile.NamedTemporaryFile', side_effect=tracking_named_temp):
                    with patch('os.path.exists', side_effect=fake_exists):
                        with patch('app.engine.engine.ComfyUIWebSocket') as mock_ws:
                            mock_ws_instance = MagicMock()
                            mock_ws.return_value = mock_ws_instance
                            mock_ws_instance.track.return_value = {}

                            with patch.object(engine, '_history_outputs', return_value=executed):
                                with patch.object(engine, '_history_status', return_value='success'):
                                    try:
                                        job = engine.execute(manifest, plan, provider=provider)
                                        pytest.fail('Expected exception on Verifier failure')
                                    except Exception:
                                        pass  # Expected

        # Verify: NO ingest calls should have been made
        assert len(ingest_calls) == 0, f'Expected 0 ingest calls on Phase 2 failure, got {len(ingest_calls)}'

        # Verify: temp files were cleaned up
        for tmp_path in temp_files_created:
            assert not os.path.exists(tmp_path), f'Temp file not cleaned up: {tmp_path}'

    def test_asset_created_on_verification_success(self):
        """Phase 1+2 success: Asset SHOULD be created in store."""
        store = AssetStore(root='__test_finding_a_success__')
        engine = WorkflowEngine(store)

        provider = MagicMock()
        provider.backend_id = 'local_comfyui'
        provider.view.return_value = b'\x89PNG\r\n\x1a\n'

        manifest = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            required_models=[], required_custom_nodes=[],
            requirements={}
        )

        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='test',
            version='1.0.0',
        )

        executed = {
            '9': {
                'images': [{'filename': 'test.png', 'subfolder': '', 'type': 'output'}]
            }
        }

        ingest_calls = []
        original_ingest = store.ingest
        def tracking_ingest(*args, **kwargs):
            ingest_calls.append(call(*args, **kwargs))
            return original_ingest(*args, **kwargs)

        with patch.object(engine, 'build_prompt', return_value={'9': {'inputs': {'images': ['6', 0]}}}):
            with patch.object(provider, 'execute', return_value='test-prompt-id'):
                with patch.object(engine.store, 'ingest', side_effect=tracking_ingest):
                    with patch('app.engine.engine.ComfyUIWebSocket') as mock_ws:
                        mock_ws_instance = MagicMock()
                        mock_ws.return_value = mock_ws_instance
                        mock_ws_instance.track.return_value = {}

                        with patch.object(engine, '_history_outputs', return_value=executed):
                            with patch.object(engine, '_history_status', return_value='success'):
                                try:
                                    job = engine.execute(manifest, plan, provider=provider)
                                except Exception as e:
                                    pytest.fail(f'Expected success, got exception: {e}')

        # Verify: ingest SHOULD have been called exactly once
        assert len(ingest_calls) == 1, f'Expected 1 ingest call, got {len(ingest_calls)}'

    def test_ingest_failure_results_in_failed_job(self):
        """Phase 3 failure (ingest raises): Job FAILED, no SUCCESS."""
        import tempfile
        import pathlib
        # Create truly isolated store with unique parent for JSONL
        tmpdir = pathlib.Path(tempfile.mkdtemp())
        store_root = tmpdir / "assets"
        store = AssetStore(root=str(store_root))
        engine = WorkflowEngine(store)

        provider = MagicMock()
        provider.backend_id = 'local_comfyui'
        provider.view.return_value = b'\x89PNG\r\n\x1a\n'

        manifest = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            required_models=[], required_custom_nodes=[],
            requirements={}
        )

        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='test',
            version='1.0.0',
        )

        executed = {
            '9': {
                'images': [{'filename': 'test.png', 'subfolder': '', 'type': 'output'}]
            }
        }

        # Make ingest raise an exception
        with patch.object(engine, 'build_prompt', return_value={'9': {'inputs': {'images': ['6', 0]}}}):
            with patch.object(provider, 'execute', return_value='test-prompt-id'):
                with patch.object(store, 'ingest', side_effect=RuntimeError('ingest failed')):
                    with patch('app.engine.engine.ComfyUIWebSocket') as mock_ws:
                        mock_ws_instance = MagicMock()
                        mock_ws.return_value = mock_ws_instance
                        mock_ws_instance.track.return_value = {}

                        with patch.object(engine, '_history_outputs', return_value=executed):
                            with patch.object(engine, '_history_status', return_value='success'):
                                try:
                                    job = engine.execute(manifest, plan, provider=provider)
                                    pytest.fail('Expected exception on ingest failure')
                                except RuntimeError as e:
                                    assert 'ingest failed' in str(e)
                                except Exception as e:
                                    pytest.fail(f'Expected RuntimeError, got {type(e).__name__}: {e}')

        # Verify: No assets were created in THIS test's store
        assert len(list(store._assets.keys())) == 0, 'Expected 0 assets in store'
