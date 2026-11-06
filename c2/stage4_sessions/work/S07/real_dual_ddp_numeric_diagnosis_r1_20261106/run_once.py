"""Bounded, single-use R1 controller. No retries, elevation, installs or jobs."""
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'real_dual_ddp_20261106'


def write(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes((json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
    os.replace(temporary,path)


def meta(path):
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def finish(states,reason,started):
    analysis_path=ROOT/'evidence/FULL_VS_SEQUENCE.json'
    analysis=json.loads(analysis_path.read_text()) if analysis_path.exists() else None
    control_path=ROOT/'evidence/FLOAT64_CONTROL.json'
    control=json.loads(control_path.read_text()) if control_path.exists() else None
    ddp_path=ROOT/'evidence/DDP_COMPARISONS.json'
    ddp=json.loads(ddp_path.read_text()) if ddp_path.exists() else None
    before=json.loads((ROOT/'SOURCE_INPUTS.json').read_text())
    unchanged=all(Path(row['path']).stat().st_size==row['bytes'] and
                  hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
                  for row in before['files'])
    counts={name:int((ROOT/('RUN_'+name+'.json')).exists()) for name in ('full','sequence','ddp','fp64')}
    hypotheses=dict(
        forward_sharding='UNKNOWN' if analysis is None else ('EXCLUDED_IN_CURRENT_FULL_VS_SEQUENCE' if
                          analysis['first_forward_bit_difference'] is None else 'OBSERVED_DIFFERENCE_SEE_METRICS'),
        denominator_and_scaling='Full/sequential denominators4/16384, objective1x; DDP source backward2x/default averaging, input divide2. Runtime DDP verification requires completed path.',
        accumulation='SUPPORTED_IDENTICAL_OPERANDS_DIFFERENT_FP32_WEIGHT_CONTRACTION' if analysis and analysis['float64_eligible']
                     else 'UNDETERMINED',
        ddp_additional_effect='UNKNOWN_NEW_DDP_NOT_COMPLETED' if ddp is None else
            ('NO_OBSERVED_EXTRA_DIFFERENCE' if all(row.get('exact') is True for row in ddp['sequence_vs_ddp']['metrics'])
             else 'OBSERVED_DIFFERENCE_SEE_FULL_METRICS'),
        historical_environment='Original actual thread counts, initial tensor digest and intermediate tensors not retained; exact historical comparability remains limited.')
    diagnosis=dict(task='S07_NUMERIC_DIAGNOSIS_R1',status=reason,source_inputs_unchanged=unchanged,
        paths=states,run_counts=counts,local_wall_seconds=time.monotonic()-started,
        limits=dict(per_path_seconds=60,cleanup_seconds=15,total_seconds=300),
        fixed_configuration=dict(seed=7,TinyEncoder='read-only original AST',local_batch=32,global_batch=64,
                                 mask_positions=[0,6656,6657,6658],masked=4,coarse=16384,
                                 optimizer_updates=0,thread_changes=0,backend_switches=0,retries=0,elevation=False),
        full_vs_sequence=analysis,float64_cause_control=control,new_ddp_comparisons=ddp,
        original_failed_metrics=json.loads((OLD/'evidence/tiny_ddp_192181562000000/strict_pair_metrics.json').read_text()),
        hypotheses=hypotheses,exact_native_kernel_root_cause='UNDETERMINED_NO_INSTRUCTION_OR_KERNEL_TRACE',
        frozen_training='UNCHANGED_FAIL',C2_training='NOT_RUN',training_pass=False,
        implementation_defect='No defect conclusion without evidence; do not edit frozen package.',
        specific_question_for_S02=None,
        raw_tensor_indices=[meta(p) for p in sorted((ROOT/'raw').glob('*.pt'))],
        next_action='S01 independent evidence review; no rerun, threshold waiver, reference substitution or training release.')
    write(ROOT/'DIAGNOSIS.json',diagnosis)
    first='UNKNOWN'
    if analysis:
        row=analysis['first_parameter_failure_by_backward_dependency']
        first='NONE' if row is None else row['name']
    report=(
        '# S07 本地数值诊断R1\n\n'
        '状态：'+reason+'。冻结训练包和原FAIL保持；本轮无训练PASS、无集群job。\n\n'
        '运行次数：'+json.dumps(counts)+'；总本地壁钟'+str(round(time.monotonic()-started,3))+'秒。'
        '每路径60秒/清理最多15秒/总300秒，首次路径前独占标记；没有重试、安装、提权或切换后端。\n\n'
        '先读HYPOTHESES_AND_CHECKS.md。只读抽取原TinyEncoder类、原training_graph及02原compare；'
        'seed7、输入、初值、mask与原门槛固定。完整B64为参考，顺序32+32只定位，不替换正式参考。'
        '浮点误差统计使用原compare的float64 norm；可选float64原因对照另计一次，不产生新模型forward/backward。\n\n'
        '回传依赖顺序上最早参数越阈值：'+first+'。前向/adjoint首次逐位差异与首次原阈值失败、'
        '全部输出/两loss/11参数梯度/两输入梯度指标见DIAGNOSIS.json。最早参数分支不是实际GPU/CPU指令trace，'
        '不得据此指定某个系统库内部指令为根因。\n\n'
        '假设结论：'+json.dumps(hypotheses,ensure_ascii=False,indent=2)+'\n\n'
        '若DDP权限或通信失败，则该路径立即停止并回收本任务Popen进程，后续不再数值计算。'
        '此时旧DDP13标量指标可核，但没有原中间张量，不能排除DDP额外误差。'
        '本轮是否复现同样13项标量误差及float64原因对照由JSON原件判定，不把未运行部分补为PASS。\n\n'
        '未定位实现缺陷，暂不建议热改。最小下一动作是01核操作数/归约对照与证据缺口；'
        '任何后续候选须另定版本，保留原完整B64、原阈值、全部13失败检查及默认DDP缩放。'
        '回归至少应覆盖相同固定样本完整B64/分片/DDP的全部输出、loss、参数/输入梯度，'
        '并保留初始化/分母/原名与原比较器覆盖；本轮不继续运行这些回归。\n\n'
        '需要02回答的具体接口/数学疑点：无。若仍有DDP中间量缺口，这是通信/权限停点，'
        '不能转嫁为02重做参考。17来源bytes/SHA末次未变：'+str(unchanged)+'。\n\n'
        'raw/仅保存诊断激活/adjoint/梯度，无模型初值权重或真实语料；归档清单排除raw张量、环境、数据和权重。'
        'JSON指标及脚本/原日志可直接交01。\n')
    (ROOT/'REPORT.md').write_bytes(report.encode())
    allfiles=sorted(p for p in ROOT.rglob('*') if p.is_file())
    exclusions=[p for p in allfiles if 'raw' in p.relative_to(ROOT).parts]
    future=[ROOT/n for n in ('ARCHIVE_SCOPE.json','EVIDENCE_MANIFEST.json','DIAGNOSIS_READY.json')]
    archive=dict(git_candidate_paths=[str(p.resolve()) for p in allfiles if p not in exclusions]+[str(p) for p in future]
                 +[str(ROOT.parent/'SESSION_STATUS.md'),str(ROOT.parent/'ROUND_DELTA.md')],
                 excluded_raw_tensor_paths=[str(p) for p in exclusions],
                 excluded='No environment, actual data, model weights, ZIP or raw tensor files in archive/Git. No Git operations performed.')
    write(ROOT/'ARCHIVE_SCOPE.json',archive)
    write(ROOT/'EVIDENCE_MANIFEST.json',dict(files=[meta(p) for p in allfiles],scope='R1 local diagnostic, not training acceptance'))
    ready=dict(task='S07_NUMERIC_DIAGNOSIS_R1',status=reason,diagnosis=meta(ROOT/'DIAGNOSIS.json'),
               report=meta(ROOT/'REPORT.md'),source_inputs=meta(ROOT/'SOURCE_INPUTS.json'),
               hypotheses=meta(ROOT/'HYPOTHESES_AND_CHECKS.md'),
               scripts=[meta(ROOT/name) for name in ('run_once.py','diagnostic_worker.py')],
               evidence_manifest=meta(ROOT/'EVIDENCE_MANIFEST.json'),archive_scope=meta(ROOT/'ARCHIVE_SCOPE.json'),
               original_inputs_unchanged=unchanged,run_counts=counts,all_owned_children_reaped=all(
                   value.get('all_reaped',True) for value in states.values()),
               local_wall_seconds=time.monotonic()-started,specific_question_for_S02=None,
               no_training_release=True,new_jobs=0,computed_after_communication_failure=False)
    write(ROOT/'DIAGNOSIS_READY.json',ready)
    write(ROOT/'PROGRESS.json',dict(status=reason,run_counts=counts,active_owned_pids=[]))
    print(reason,str(ROOT/'DIAGNOSIS_READY.json'),flush=True)


def main():
    marker=ROOT/'RUN_ONCE.json'
    with marker.open('x') as stream:
        json.dump(dict(pid=os.getpid(),started_ns=time.monotonic_ns()),stream)
    for path in (ROOT/'run_once.py',ROOT/'diagnostic_worker.py'):
        ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,9))
    for row in json.loads((ROOT/'SOURCE_INPUTS.json').read_text())['files']:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('source changed before any path: '+row['path'])
    python=json.loads((OLD/'evidence/API_ACTUAL_LOCAL.json').read_text())['python']
    if not Path(python).is_file():
        raise ValueError('original interpreter unavailable')
    write(ROOT/'evidence/RUN_SOURCES.json',dict(scripts=[meta(ROOT/name) for name in ('run_once.py','diagnostic_worker.py')],
           interpreter=meta(Path(python))))
    started=time.monotonic();end=started+300;states={}

    def run(name,commands):
        with (ROOT/('RUN_'+name+'.json')).open('x') as stream:
            json.dump(dict(start_monotonic=time.monotonic(),commands=commands),stream)
        stage_start=time.monotonic();deadline=min(stage_start+60,end-15)
        processes=[];logs=[];reason='COMPLETED';permission=False
        try:
            for rank,command in enumerate(commands):
                path=ROOT/'evidence'/(name+str(rank)+'.log')
                log=path.open('xb');logs.append(log)
                processes.append(subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                                    start_new_session=os.name=='posix'))
            while True:
                codes=[p.poll() for p in processes]
                if name=='ddp':
                    text=''.join((ROOT/'evidence'/(name+str(rank)+'.log')).read_text(errors='replace')
                                 for rank in range(len(processes)))
                    if '10013' in text or 'PermissionError' in text or 'Permission denied' in text:
                        permission=True;reason='STOPPED_DDP_PERMISSION_FAILURE';break
                if any(code is not None and code!=0 for code in codes):
                    reason='STOPPED_DDP_COMMUNICATION_OR_PROCESS_FAILURE' if name=='ddp' else 'STOPPED_PATH_FAILURE';break
                if all(code==0 for code in codes):break
                if time.monotonic()>=deadline:
                    reason='STOPPED_PATH_TIMEOUT';break
                time.sleep(.05)
        except (OSError,ValueError) as exc:
            reason='STOPPED_LAUNCH_OR_PERMISSION_FAILURE'
            write(ROOT/'evidence'/(name+'_launch_error.json'),dict(error=str(exc)))
        finally:
            cleanup_start=time.monotonic();cleanup_deadline=min(cleanup_start+15,end)
            for process in processes:
                if process.poll() is None:
                    if os.name=='posix':os.killpg(process.pid,signal.SIGTERM)
                    else:process.terminate()
            grace=min(cleanup_deadline,time.monotonic()+2)
            while any(p.poll() is None for p in processes) and time.monotonic()<grace:time.sleep(.01)
            for process in processes:
                if process.poll() is None:
                    if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
                    else:process.kill()
            while any(p.poll() is None for p in processes) and time.monotonic()<cleanup_deadline:time.sleep(.01)
            for process in processes:
                if process.poll() is not None:process.wait(timeout=0)
            for log in logs:log.close()
        state=dict(status=reason,pids=[p.pid for p in processes],exit_codes=[p.returncode for p in processes],
                   all_reaped=all(p.returncode is not None for p in processes),
                   seconds=time.monotonic()-stage_start,cleanup_seconds=time.monotonic()-cleanup_start)
        states[name]=state;write(ROOT/'evidence'/(name+'_supervision.json'),state)
        print(name,state,flush=True)
        return reason=='COMPLETED' and state['all_reaped']

    def command(mode,extra=()):return [python,'-B',str(ROOT/'diagnostic_worker.py'),'--mode',mode]+list(extra)
    for name in ('full','sequence'):
        if not run(name,[command(name)]):
            finish(states,states[name]['status'],started);return 1
    analysis=json.loads((ROOT/'evidence/FULL_VS_SEQUENCE.json').read_text())
    if analysis['float64_eligible']:
        write(ROOT/'FLOAT64_PURPOSE.json',dict(purpose='One contraction-only control of identical recorded operands for original failed val/pos/tf weights; no new model forward/backward',
             supporting_evidence=meta(ROOT/'evidence/FULL_VS_SEQUENCE.json'),no_fp32_acceptance=True))
        if not run('fp64',[command('fp64')]):
            finish(states,states['fp64']['status'],started);return 1
    else:
        write(ROOT/'FLOAT64_NOT_RUN.json',dict(status='NOT_RUN_PRECONDITION_NOT_ESTABLISHED'))
    # One original Windows localhost TCP path; no backend switching or elevation.
    try:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    except OSError as exc:
        states['ddp']=dict(status='STOPPED_DDP_BIND_PERMISSION_FAILURE',error=str(exc),all_reaped=True,pids=[])
        write(ROOT/'RUN_ddp.json',dict(status='ATTEMPT_CONSUMED_BIND_FAILED',error=str(exc)))
        finish(states,states['ddp']['status'],started);return 1
    init=f'tcp://127.0.0.1:{port}'
    if not run('ddp',[command('ddp',('--rank',str(rank),'--init-method',init)) for rank in range(2)]):
        finish(states,states['ddp']['status'],started);return 1
    if not run('merge',[command('merge')]):
        finish(states,states['merge']['status'],started);return 1
    finish(states,'DIAGNOSIS_COMPLETED_NOT_FP32_TRAINING_PASS',started)
    return 0


if __name__=='__main__':
    sys.exit(main())
