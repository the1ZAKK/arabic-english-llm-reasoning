"""Later separately authorized library-import/CUDA-metadata probe, never a model test.

This file is copied with exact legacy wrapper sources into a NEW private report
folder by runtime_setup_v4_5 after receipt/hash/approval/confirmation checks. It
must be invoked using the installed isolated interpreter and -I -B.
"""
import importlib.metadata
import inspect
import json
import os
import platform
import struct
from pathlib import Path
import sys


def audit(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
        raise RuntimeError('Network blocked during non-model qualification')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        name = os.fsdecode(args[0]).lower()
        if name.endswith(('.safetensors', '.pt', '.pth.tar', '.ckpt', '.bin', '.gguf')):
            raise RuntimeError('Model/checkpoint access blocked during dependency qualification')


def main():
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        raise SystemExit('Real library imports/CUDA qualification are blocked in CI')
    if os.environ.get('ARABICPRM_NON_MODEL_QUALIFICATION') != 'approved_by_parent':
        raise SystemExit('Use the separately gated setup tool; do not invoke this probe directly')
    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
    here = Path(__file__).resolve().parent
    # Only the verified legacy source capsule, not a project checkout or weights.
    sys.path.insert(0, str(here))
    report = {'schema': 'arabicprm-library-qualification-v4.5', 'status': 'not_qualified',
              'model_operations': 0, 'model_fit_demonstrated': False, 'experiment_authorized': False,
              'python': {'version': platform.python_version(), 'implementation': sys.implementation.name,
                         'bits': struct.calcsize('P')*8, 'platform': sys.platform}}
    try:
        import torch
        import bitsandbytes
        from bitsandbytes.cextension import lib
        import transformers
        import peft
        from accelerate import PartialState
        from huggingface_hub.utils import (EntryNotFoundError, HFValidationError,
                                           LocalEntryNotFoundError, RepositoryNotFoundError)
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, PreTrainedModel
        from transformers.integrations.deepspeed import is_deepspeed_zero3_enabled
        from peft import PeftModel, get_peft_model_state_dict
        from safetensors.torch import load_file
        from model_utils.prm_model import PRM_MODEL
        from model_utils.io_utils import prepare_input, derive_step_rewards
        # No class is instantiated; no tokenizer/model/checkpoint is loaded.
        report['versions'] = {name: importlib.metadata.version(name) for name in
                              ('torch', 'bitsandbytes', 'transformers', 'peft', 'accelerate',
                               'huggingface-hub', 'safetensors', 'tokenizers', 'numpy', 'packaging')}
        report['torch_build'] = torch.__version__
        report['torch_cuda_build'] = torch.version.cuda
        report['cuda_available'] = torch.cuda.is_available()
        report['bnb_compiled_with_cuda'] = getattr(lib, 'compiled_with_cuda', False) is True
        report['bnb_library_path'] = str(getattr(getattr(lib, '_lib', None), '_name', ''))
        report['legacy_signatures'] = {name: str(inspect.signature(obj)) for name, obj in
                                        [('PRM_MODEL.forward', PRM_MODEL.forward),
                                         ('prepare_input', prepare_input), ('derive_step_rewards', derive_step_rewards),
                                         ('PeftModel.from_pretrained', PeftModel.from_pretrained),
                                         ('get_peft_model_state_dict', get_peft_model_state_dict),
                                         ('BitsAndBytesConfig', BitsAndBytesConfig)]}
        report['lora_config_fields'] = sorted(peft.LoraConfig.__dataclass_fields__)
        if torch.__version__ != '2.8.0+cu126' or torch.version.cuda != '12.6':
            raise RuntimeError('Expected exact CUDA Torch build not observed')
        if not report['cuda_available'] or not report['bnb_compiled_with_cuda']:
            raise RuntimeError('CUDA availability or bnb native CUDA library failed')
        prop = torch.cuda.get_device_properties(0)
        report['device'] = {'name': prop.name, 'total_memory_bytes': prop.total_memory,
                            'compute_capability': [prop.major, prop.minor]}
        report['torch_arch_list'] = torch.cuda.get_arch_list()
        if (prop.major, prop.minor) < (7, 5) or 'sm_75' not in report['torch_arch_list']:
            raise RuntimeError('Expected Turing-capable device/build not demonstrated')
        if not report['bnb_library_path'].lower().endswith('libbitsandbytes_cuda126.dll'):
            raise RuntimeError('Unexpected bitsandbytes native library')
        report['status'] = 'libraries_cuda_metadata_qualified_no_model_fit'
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        report['error'] = str(exc)
    print('ARABICPRM_QUALIFICATION_JSON ' + json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'libraries_cuda_metadata_qualified_no_model_fit' else 1


if __name__ == '__main__':
    raise SystemExit(main())
