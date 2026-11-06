"""LOCAL_FIXTURE: atomic residues never replace or invalidate protocol files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rank_report_inventory as reports
import readiness_inventory

class ReportCollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'evidence');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.case=self.root/'payload/checks_current_job/crash';self.case.mkdir(parents=True);(self.root/'job_id.txt').write_text('42\n')
        self.write('manifest.json',dict(job_id='42',run_id='crash'))
        self.write('summary.json',dict(supervisor=dict(pids=[11,12],exit_codes=[-15,17],all_reaped=True)))
        for rank in (0,1):self.write(f'rank{rank}.json',dict(rank=rank,pid=11+rank,run_id='crash',world_size=2,status='FAIL',stage='broadcast' if rank==0 else 'injected_crash',checkpoints=[dict(stage='broadcast' if rank==0 else 'injected_crash')]))

    def write(self,name,value):(self.case/name).write_text(json.dumps(value),encoding='utf-8')

    def test_valid_formal_report_and_partial_residue_remain_separate(self):
        p=self.case/'.rank0.json.abcd.tmp';p.write_bytes(b'{partial');before=(self.case/'rank0.json').read_bytes()
        value=reports.inspect(self.root)['cases']['crash'];self.assertTrue(value['reports']['0']['formal_report_valid']);self.assertEqual(value['reports']['0']['stage'],'broadcast');self.assertEqual(value['residuals'][0]['bytes'],8)
        self.assertEqual((self.case/'rank0.json').read_bytes(),before);self.assertEqual(p.read_bytes(),b'{partial')

    def test_missing_empty_partial_formal_rejected_despite_valid_temp(self):
        for mode in ('missing','empty','partial'):
            self.write('.rank0.json.valid.tmp',dict(stage='injected_crash'));p=self.case/'rank0.json'
            if mode=='missing':p.unlink(missing_ok=True)
            else:p.write_bytes(b'' if mode=='empty' else b'{partial')
            row=reports.inspect(self.root)['cases']['crash']['reports']['0'];self.assertFalse(row['formal_report_valid']);self.assertIsNone(row.get('stage'))

    def test_rank_temp_not_readiness_temp_but_original_ready_residue_retained(self):
        (self.case/'.rank0.json.abcd.tmp').write_bytes(b'{partial')
        first=readiness_inventory.inspect(self.root)['cases']['crash'];self.assertEqual(first['temporary_files'],[])
        (self.case/'ready_rank0.json.tmp').write_bytes(b'{partial')
        second=readiness_inventory.inspect(self.root)['cases']['crash'];self.assertEqual(second['temporary_files'],['ready_rank0.json.tmp']);self.assertFalse(second['complete'])

if __name__=='__main__':unittest.main(verbosity=2)
