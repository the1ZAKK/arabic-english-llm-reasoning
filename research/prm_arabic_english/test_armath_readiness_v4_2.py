"""Source-bound math checks and synthetic local inventories; no live model I/O."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import armath_references_v4_2 as refs
import armath_inspect_v4_2 as inventory


class ReferenceTests(unittest.TestCase):
    def test_eleven_technical_keys_one_conditional_zero_human(self):
        d=refs.verified()
        self.assertEqual((d['technical_endpoint_keys'],d['conditional_excluded'],d['independent_human_validations']),(11,1,0))
        self.assertEqual(len(d['rows']),12)
        for row in d['rows']:
            self.assertEqual(row['independent_human_judgments'],[])
            self.assertFalse(row['benchmark_eligible'])

    def test_seven_independent_derivations_and_dimensions(self):
        rows={r['problem_id'].split(':',2)[2]:r for r in refs.verified()['rows']}
        for key,answer in {'fold0:0078':'60','fold0:0832':'20','fold1:0152':'38400','fold2:0622':'35',
                           'fold2:0798':'3/5','fold2:0836':'1','fold4:0735':'1521/4'}.items():
            self.assertEqual(rows[key]['computed_value_exact'],answer)
            self.assertEqual(rows[key]['method'],'case_specific_AI_question_derivation')
        self.assertIn('مربع',rows['fold4:0735']['requested_unit'])
        self.assertIn('غير المسماة',rows['fold2:0622']['requested_unit'])
        self.assertIn('لتر',rows['fold2:0798']['requested_unit'])

    def test_equal_sharing_is_not_silently_assumed(self):
        boat=refs.verified()['rows'][0]
        self.assertTrue(boat['uncertainties']);self.assertIsNone(boat['automatic_endpoint_key'])
        self.assertEqual(boat['decision'],'conditional_excluded')

    def test_source_change_or_reference_record_edit_rejected(self):
        original=refs.old.source_originals(); before=deepcopy(original)
        original[refs.old.identity('fold0:0832')]['question']+=' تغيير'
        with patch.object(refs.old,'source_originals',return_value=original):
            with self.assertRaisesRegex(ValueError,'Source identity'):refs.decisions()
        self.assertEqual(before,refs.old.source_originals())
        expected=refs.verified();wrong=deepcopy(expected);wrong['technical_endpoint_keys']=12
        with patch.object(Path,'read_bytes',return_value=json.dumps(wrong).encode()):
            with patch.object(refs,'decisions',return_value=expected):
                with self.assertRaises(ValueError):refs.verified()


class InventoryTests(unittest.TestCase):
    def test_artifact_hashes_actual_bytes_and_detects_change(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'adapter.safetensors').write_bytes(b'SYNTHETIC weights')
            a=inventory.artifact(p);self.assertEqual(a['status'],'present')
            self.assertEqual(a['files'][0]['sha256'],hashlib.sha256(b'SYNTHETIC weights').hexdigest())
            (p/'adapter.safetensors').write_bytes(b'SYNTHETIC changed')
            self.assertNotEqual(a['sha256'],inventory.artifact(p)['sha256'])

    def test_missing_artifacts_are_not_invented(self):
        self.assertEqual(inventory.artifact(None)['status'],'missing')
        self.assertIsNone(inventory.artifact(None)['sha256'])

    def test_existing_original_checkpoint_is_hashed_readonly_without_migration(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);clean=p/'arabic-english-llm-reasoning-development';original=p/'arabic-english-llm-reasoning'
            clean.mkdir();original.mkdir();path=original/'checkpoints/head.pt';path.parent.mkdir();path.write_bytes(b'SYNTHETIC old checkpoint')
            value=inventory.project_artifact(clean,'checkpoints/head.pt')
            self.assertEqual(value['path'],str(path.resolve()))
            self.assertEqual(path.read_bytes(),b'SYNTHETIC old checkpoint');self.assertFalse((clean/'checkpoints').exists())
            q=clean/'checkpoints/head.pt';q.parent.mkdir();q.write_bytes(b'SYNTHETIC other checkpoint')
            self.assertEqual(inventory.project_artifact(clean,'checkpoints/head.pt')['status'],'ambiguous_multiple_paths')
            self.assertEqual(inventory.project_artifact(clean,'checkpoints/head.pt',path)['path'],str(path.resolve()))

    def test_only_allowlisted_metadata_routes(self):
        with patch.object(inventory.http.client,'HTTPConnection') as c:
            for route in ('/api/generate','/api/chat','/api/pull','/api/create'):
                with self.assertRaises(ValueError):inventory.metadata('POST',route,{'model':inventory.MODEL})
            with self.assertRaises(ValueError):inventory.metadata('POST','/api/show',{'model':'wrong'})
            c.assert_not_called()
            response=c.return_value.getresponse.return_value;response.status=302
            with self.assertRaises(ValueError):inventory.metadata('GET','/api/tags')

    def test_exact_digest_is_observed_not_inferred_from_name(self):
        def call(method,path,body):
            return {'/api/tags':{'models':[{'name':inventory.MODEL,'digest':inventory.DIGEST}]},
                    '/api/version':{'version':'SYNTHETIC-version'},'/api/ps':{'models':[]},'/api/show':{}}[path]
        self.assertTrue(inventory.ollama(call)['exact_digest_match'])
        def wrong(method,path,body):
            if path=='/api/tags':return {'models':[{'name':inventory.MODEL,'digest':'0'*64}]}
            return call(method,path,body)
        self.assertFalse(inventory.ollama(wrong)['exact_digest_match'])

    def test_cloud_or_missing_local_runtime_does_not_become_ready(self):
        with tempfile.TemporaryDirectory() as td, patch.object(inventory,'default_base',return_value=None), \
             patch.object(inventory,'ollama',return_value={'exact_digest_match':False}), \
             patch.object(inventory,'package_versions',return_value=dict.fromkeys(inventory.PACKAGES,None)):
            d=inventory.inspect(td,probe=False)
            self.assertFalse(d['nf4_prerequisites_observed']);self.assertFalse(d['prm_forward_fit_verified'])
            self.assertEqual(d['status'],'runtime_attention_required')
            self.assertEqual((d['generation_requests'],d['scoring_operations'],d['model_loads']),(0,0,0))

    def test_capability_probe_never_loads_or_scores_models(self):
        with patch.object(inventory.subprocess,'run') as run:
            run.return_value.returncode=0
            run.return_value.stdout='ARABICPRM_CAPABILITIES={"cuda_available":false}\n'
            inventory.capabilities()
            args=run.call_args.args[0];code=args[-1]
            for text in ('from_pretrained','torch.load','generate(','tensor(','forward('):self.assertNotIn(text,code)
            self.assertEqual(run.call_args.kwargs['env']['HF_HUB_OFFLINE'],'1')

    def test_cmd_embeds_exact_hash_verified_helper_and_no_installer(self):
        root=Path(__file__).parent;cmd=root/'inspect_armath_runtime_windows_v4_2.cmd'
        raw=cmd.read_bytes();expected=cmd.with_suffix('.cmd.sha256').read_text(encoding='ascii').split()[0]
        self.assertEqual(hashlib.sha256(raw).hexdigest(),expected)
        blocks=re.findall(rb'^rem ARABICPRM-ARMATH-INSPECT-PAYLOAD ([A-Za-z0-9+/=]+)\r?$',raw,re.M)
        helper=base64.b64decode(b''.join(blocks),validate=True)
        self.assertEqual(helper,(root/'armath_inspect_v4_2.py').read_bytes())
        self.assertIn(hashlib.sha256(helper).hexdigest().encode(),raw)
        self.assertNotIn(b'Invoke-WebRequest',raw);self.assertNotIn(b' -S ',raw)
        self.assertEqual(raw.count(b'\n'),raw.count(b'\r\n'))


if __name__=='__main__':unittest.main()
