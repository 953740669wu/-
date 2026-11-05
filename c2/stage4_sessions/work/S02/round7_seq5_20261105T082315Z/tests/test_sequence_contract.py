"""Stdlib protocol/metering tests with explicit substitutes, not C2 or RSS data."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import check_sequence5 as checker
import sequence_gate as gate
import sequence_runtime as runtime
import train_sequence5 as memory


class GateTests(unittest.TestCase):
    def setUp(self):
        self.sources = {'sequence_core.py':'source'}
        self.frozen = dict(sha256='case', identity={'weights':'initial'})
        self.data = dict(status='PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY', mode='sequence5_strict',
            completed_steps=5, comparison_failures=0, config=gate.REQUIRED_CONFIG.copy(),
            source_sha256=self.sources, source_manifest_sha256='manifest', case_file_sha256='case',
            case_identity=self.frozen['identity'], runtime=dict(backend='kml'), steps=[], cpu36={})
        for step in range(1, 6):
            lineage = {}
            for index, side in enumerate(('reference','candidate')):
                before = dict(completed_updates=step-1, optimizer_step_min=step-1, optimizer_step_max=step-1,
                    optimizer_states=0 if step==1 else 153, model_id=index+1, optimizer_id=index+10,
                    parameter_gradients_cleared=True, input_gradients_cleared=True)
                after = dict(before, completed_updates=step, optimizer_step_min=step, optimizer_step_max=step,
                             optimizer_states=153)
                lineage[side] = dict(step=step, before=before, after=after,
                    before_digest='initial' if step==1 else side+str(step-1), after_digest=side+str(step))
            metrics = [dict(name=f'{family}.{i}',passed=True) for family,count in gate.FAMILIES.items() for i in range(count)]
            self.data['steps'].append(dict(step=step, comparison_failures=0, failures=[],
                case_file_sha256='case', source_manifest_sha256='manifest', metrics=metrics,
                lineage=lineage, kml_calls=dict(reference=149,candidate=197)))

    def validate(self, data):
        with patch.object(gate.sequence_runtime,'validate') as check:
            gate.validate(data,self.frozen,self.sources,'manifest')
            return check

    def test_complete_five_step_protocol_reaches_cpu_gate(self):
        check=self.validate(self.data); check.assert_called_once_with({},'strict',5)

    def test_old_one_step_pass_cannot_unlock_five_step_memory(self):
        for change in [dict(status='PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'),dict(completed_steps=1),
                       dict(mode='checkpoint_strict'),dict(steps=self.data['steps'][:1])]:
            with self.subTest(change=list(change)),self.assertRaises(ValueError):
                self.validate(dict(self.data,**change))

    def test_reset_optimizer_parameters_or_instance_is_rejected(self):
        for mutation in ('counter','digest','identity'):
            data=copy.deepcopy(self.data); item=data['steps'][2]['lineage']['candidate']
            if mutation=='counter':item['after']['optimizer_step_min']=1
            elif mutation=='digest':item['before_digest']='initial'
            else:item['before']['optimizer_id']=item['after']['optimizer_id']=999
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(data)

    def test_missing_duplicate_failed_metrics_or_kml_is_rejected(self):
        for mutation in ('missing','duplicate','failed','kml'):
            data=copy.deepcopy(self.data); record=data['steps'][3]
            if mutation=='missing':record['metrics'].pop()
            elif mutation=='duplicate':record['metrics'][1]['name']=record['metrics'][0]['name']
            elif mutation=='failed':record['metrics'][1]['passed']=False
            else:record['kml_calls']['candidate']=0
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(data)

    def test_wrong_source_or_fixed_case_is_rejected(self):
        for key in ('source_manifest_sha256','case_file_sha256'):
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(dict(self.data,**{key:'old'}))


class MeteringTests(unittest.TestCase):
    def setUp(self):
        self.events=[]; self.calls=dict(kml_gemm_calls=0)
        events,calls=self.events,self.calls
        class State:
            def begin(self,step):events.append('begin');return {'step':step}
            def update(self):
                events.append('update');calls['kml_gemm_calls']+=149
                class Loss:
                    def item(self):events.append('loss_item');return 1.
                return Loss()
            def validate(self,step):events.append('validate');return {'step':step}
        self.state=State()

    def test_reset_clock_peak_and_validation_order(self):
        def rss():
            index=sum(x.startswith('rss') for x in self.events);self.events.append('rss'+str(index))
            return dict(rss_bytes=1024,peak_rss_bytes=2048,hugetlb_bytes=0)
        def reset():self.events.append('reset');return dict(available=True)
        def clock():self.events.append('clock');return float(self.events.count('clock'))
        record={}
        with patch.object(memory.memory_metrics,'rss',side_effect=rss), \
             patch.object(memory.memory_metrics,'reset_peak',side_effect=reset), \
             patch.object(memory.time,'perf_counter',side_effect=clock):
            memory.measure_step(self.state,1,lambda name:self.events.append(name),self.calls,record)
        self.assertEqual(self.events,['begin','before_training_1','rss0','reset','rss1','clock',
            'update','clock','rss2','validate','loss_item','after_training_1'])
        self.assertEqual(record['training']['elapsed_seconds'],1.)
        self.assertEqual(record['kml_calls'],149)

    def test_reset_failure_stops_before_update(self):
        with patch.object(memory.memory_metrics,'rss',return_value={}), \
             patch.object(memory.memory_metrics,'reset_peak',return_value=dict(available=False)), \
             self.assertRaises(ValueError):
            memory.measure_step(self.state,1,lambda name:None,self.calls,{})
        self.assertNotIn('update',self.events)

    def test_second_step_failure_stops_sequence_and_retains_partial_record(self):
        records=[]
        with patch.object(memory.memory_metrics,'rss',return_value={}), \
             patch.object(memory.memory_metrics,'reset_peak',side_effect=[dict(available=True),dict(available=False)]), \
             self.assertRaises(ValueError):
            for step in range(1,6):
                record={};records.append(record)
                memory.measure_step(self.state,step,lambda name:None,self.calls,record)
        self.assertEqual(len(records),2);self.assertEqual(self.events.count('update'),1)
        self.assertEqual(records[1]['step'],2);self.assertFalse(records[1]['peak_reset']['available'])


class StrictLoopTests(unittest.TestCase):
    def test_numerical_failure_stops_after_full_failing_step(self):
        states=[];calls=dict(kml_gemm_calls=0)
        class State:
            torch=None
            def __init__(self):self.completed=0
            def digest(self):return str(self.completed)
        states=[State(),State()]
        def numerical(state,step):
            before=state.digest();state.completed+=1;calls['kml_gemm_calls']+=1
            return {},dict(before_digest=before,after_digest=state.digest())
        comparisons=[([{}]*1063,[]),([{}]*1063,[dict(name='delta.x',reason='original criterion')])]
        result=dict(case_file_sha256='case',source_manifest_sha256='manifest')
        with patch.object(checker,'numerical_step',side_effect=numerical), \
             patch.object(checker,'compare_step',side_effect=comparisons):
            passed=checker.run_steps(states,result,lambda name:None,calls)
        self.assertFalse(passed);self.assertEqual([s.completed for s in states],[2,2])
        self.assertEqual(len(result['steps']),2);self.assertEqual(result['steps'][-1]['comparison_failures'],1)

    def test_strict_and_memory_cpu_order_include_every_update(self):
        self.assertEqual(len(runtime.checkpoint_names('strict',5)),24)
        self.assertEqual(len(runtime.checkpoint_names('memory',5)),15)
        names=runtime.checkpoint_names('memory',5)
        state=dict(pid=10,errors=[],receipt={},checkpoints=[dict(name=name,pid=10) for name in names])
        with patch.object(runtime.cpu36_guard,'validate_checkpoint') as check:
            runtime.validate(state,'memory',5)
            self.assertEqual(check.call_count,15)
        state['checkpoints'].pop(6)
        with self.assertRaises(ValueError):runtime.validate(state,'memory',5)

    def test_importing_new_entries_does_not_import_frameworks(self):
        self.assertNotIn('torch',sys.modules);self.assertNotIn('numpy',sys.modules)


if __name__=='__main__':unittest.main(verbosity=2)
