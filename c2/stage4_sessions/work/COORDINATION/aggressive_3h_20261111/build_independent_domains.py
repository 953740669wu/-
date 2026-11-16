"""Let each allocated domain finish its own strict test and paired timing."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent=HERE/'R13_FOUR_DOMAIN_TAIL';binding=json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'));original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items());source=dict(original)
    code=source['payload/worker.py'].decode()
    for a,b in [('planned = 5 if strict else 25','planned = 5 if strict else 15'),
                ('not strict and step == 6','not strict and step == 4'),
                ('sampled=not strict and step >= 6','sampled=not strict and step >= 4'),
                ('barrier(args, 26)','barrier(args, 16)'),('"PASS_PERF25"','"PASS_PERF15"')]:code=change(code,a,b)
    source['payload/worker.py']=code.encode()
    code=source['launch.py'].decode()
    for a,b in [('(5 if name == "strict" else 26)','(5 if name == "strict" else 16)'),
                ('(6 if name == "strict" else 27)','(6 if name == "strict" else 17)'),
                ('("PASS_PERF25",25)','("PASS_PERF15",15)'),
                ('10*count + 50*count*binding["pairs"]','10*count + 30*count*binding["pairs"]')]:code=change(code,a,b)
    start=code.index('        for variant in ("baseline","candidate"):',code.index('def main(pin):'))
    finish=code.index('        outcome["status"] = "PASS_FULL_NODE_COMPLETED_PHASES"',start)+len('        outcome["status"] = "PASS_FULL_NODE_COMPLETED_PHASES"')
    code=code[:start]+'''        placements = prepare_hbm(ROOT, EVIDENCE, contracts, dict(binding, **selections["baseline"]), end, "baseline")
        parent_evidence = EVIDENCE
        children, codes = {}, {}

        def run_domain(node):
            global EVIDENCE
            EVIDENCE = parent_evidence/"domains"/f"node{node}"
            EVIDENCE.mkdir(parents=True)
            shutil.copyfile(parent_evidence/f"node{node}.allocation.json", EVIDENCE/f"node{node}.allocation.json")
            local_owner = Owned(os.getpid())
            local_placements = {node: placements[node]}
            report = dict(status="FAIL_STOP", node=node, started=time.monotonic())
            try:
                need(libc.prctl(36,1,0,0,0) == 0, "domain subreaper failed")
                for variant in ("baseline","candidate"):
                    report["active_phase"] = "strict_"+variant
                    phase("strict", variant, {node:contracts[node]}, local_owner, binding, end, local_placements)
                    verify_return(local_placements, "strict_"+variant)
                dispose_snapshots()
                for variant in ("candidate","baseline"):
                    report["active_phase"] = "perf_"+variant
                    phase("perf", variant, {node:contracts[node]}, local_owner, binding, end, local_placements, 1)
                    verify_return(local_placements, "perf_"+variant)
                report.update(status="PASS_STRICT5_AND_PERF15", active_phase=None)
            except BaseException as exc:
                report.update(error=repr(exc), traceback=traceback.format_exc())
            finally:
                for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, signal.SIG_IGN)
                try:
                    receipt = cleanup(local_owner, min(deadline,time.monotonic()+25))
                    save(EVIDENCE/"cleanup.json", receipt)
                    need(receipt["all_reaped"], "domain cleanup incomplete")
                    dispose_snapshots()
                    verify_return(local_placements, "terminal")
                    report["hbm_pool_restored"] = True
                except BaseException as exc:
                    report.update(status="FAIL_STOP", cleanup_error=repr(exc))
                report["finished"] = time.monotonic()
                save(EVIDENCE/"DOMAIN_SUMMARY.json", report)
            os._exit(0 if report["status"] == "PASS_STRICT5_AND_PERF15" else 2)

        for node in contracts:
            pid = os.fork()
            if pid == 0: run_domain(node)
            children[node] = pid
        save(EVIDENCE/"DOMAIN_CHILDREN.json", children)
        while len(codes) < len(children):
            owner.update(process_table())
            for node, pid in children.items():
                if node in codes: continue
                done, status = os.waitpid(pid, os.WNOHANG)
                if done: codes[node] = os.waitstatus_to_exitcode(status)
            if time.monotonic() >= end: raise TimeoutError("independent domain deadline")
            time.sleep(.2)
        outcome["domain_exit_codes"] = codes
        outcome["domain_summaries"] = {n:read(parent_evidence/"domains"/f"node{n}"/"DOMAIN_SUMMARY.json") for n in contracts}
        need(all(c == 0 for c in codes.values()), "one or more domains failed; preserve partial valid results")
        verify(ROOT, pin)
        outcome["status"] = "PASS_FULL_NODE_COMPLETED_PHASES"'''+code[finish:]
    source['launch.py']=code.encode();out=HERE/'R15_INDEPENDENT_DOMAINS';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(parent/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,feature_version=(3,9))
        if raw!=original[n]:diffs.extend(unified_diff(original[n].decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8');write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote=old.replace(parent.name,out.name)
    binding['native_argv']=[a.replace(old,remote) if a!='1200' else '720' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version=out.name,remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   submission_ordinal=17,wall_seconds=720,max_model_updates=160,diff_base=parent.name,
                   performance_steps=15,performance_warmup=3,performance_samples=12,domain_schedule='independent_strict_and_performance_lifecycles',
                   retry_reason='Single active domain1 also slow; let each of four domains complete its own full strict5 and one perf15 pair without waiting for another domain. Preserve failed domains and partial acceptance boundaries. No relaxed numerical thresholds.',
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding);print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
