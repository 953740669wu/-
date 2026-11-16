"""Check wrapper boundaries without a local training environment."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class ScopeTest(unittest.TestCase):
    def test_ffn_keeps_attention_and_layer_forward(self):
        spec = importlib.util.spec_from_file_location("candidate", Path(__file__).with_name("checkpoint_layers.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []
        def checkpoint(fn, *args, **kwargs):
            calls.append(kwargs.pop("use_reentrant"))
            return fn(*args, **kwargs)
        fake = types.ModuleType("torch.utils.checkpoint")
        fake.checkpoint = checkpoint
        layers = [types.SimpleNamespace(forward=lambda x: x + 1,
                  _ff_block=lambda x, offset=i: x + offset) for i in range(12)]
        original = [layer.forward for layer in layers]
        enc = types.SimpleNamespace(tf=types.SimpleNamespace(layers=layers))
        with patch.dict(sys.modules, {"torch.utils.checkpoint": fake}):
            module.enable_checkpoint(enc, "ffn")
            self.assertEqual([layer._ff_block(10) for layer in layers], list(range(10,22)))
        self.assertEqual([layer.forward for layer in layers], original)
        self.assertEqual(calls, [False] * 12)


if __name__ == "__main__":
    unittest.main()
