# LOCAL_FIXTURE support package — preparation blocked

This package contains only standard-library metadata helpers/tests. It is NOT a
model-forensics executable or deployment package. PREPARATION_READY is absent.
Read PREPARATION_BLOCKED.json, CAPABILITY_ASSESSMENT.json and the exact original
SPEC_SNAPSHOT.json first. No real compute/SSH/job command is supplied.

```powershell
python -I -S -B tests/test_contracts.py
python -I -S -B candidate/contracts.py --fixture fixtures/metadata_report.json --report NEW_LOCAL_FIXTURE_REPORT.json
```

The first command runs14 synthetic metadata tests. The second only checks and
atomically copies a LOCAL_FIXTURE report schema. Exit0 means metadata acceptance
only; exit2 rejects scope/spec/missing/stale/corrupt/partial/report claims.
Reports explicitly require actual_autograd/actual_KML/actual_Linux_exit=false.
No Torch, frozen model module, tensor file, process executor or process scan is
imported/called. No optimizer or loss implementation is included. Files written
by tests are local synthetic reports, never real PID/gradient/exit evidence.

candidate/contracts.py exposes only partition/declared-row mapping/scaling,
path counts/deadlines, byte budget, proc-text parser/identity comparison,
exit-event completeness checks and fixture JSON publication. Passing fabricated
metadata cannot certify a real source, PID, owned descendant or Linux cleanup.
The original spec is authoritative; these helpers do not implement its actual
observer. Shape alone cannot distinguish token-major from sample-major; declared
layout requires independent source/runtime proof before any future use.

B01_UNBOUND_INSTALLED_NATIVE_VJP: saved C2 records bind DDP/torch init/library
identity, not the native linear backward nodes/grad-input slots or full attention
layout provenance. Local Windows2.7.1 Node.register_hook docs show a possible
passive mechanism but do not supply that C2 binding. Direct _LinearFn returns
are visible in frozen source; native val/head_coarse coverage remains unproved.
Never substitute shared leaf gradients, hardcode AddmmBackward0/slot1, add a new
view/hook affecting dispatch, or invoke extra autograd/GEMM to fill dX.

After independent review, first seek exact already-saved/offline C2 Node/native
Linear/MHA source or graph-slot provenance. If those records do not exist, report
that need for a new narrow scope; this package grants no acquisition, import or
model execution permission. Further actual diagnostics need a concrete observer,
new preparation/code review and separately explicit user execution approval.
The300s/CPU36/24GiB values are proposed ceilings only.
