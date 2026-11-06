# S00简短状态

- 更新/轮次：2026-11-05；REALDATA_SOURCE_AUDIT_20261105；由S00维护，真实数据小训练优先，05/07探针后置。
- 状态：DATA_NOT_READY；只读来源/正式划分核对完成，本轮0新job/0节点秒，未读NPZ、未下载或选择训练单元。
- 当前队列：14:25:58UTC/login05仅用户其它2042679/gllm5-stale-inbox-fix、16节点RUNNING；无活动S00 job。S00根23项/46份提交记录已核，无新真实训练提交；不操作/借用该任务，不把旧2015576沿作当前状态。
- 语料身份：/home/share/songzhenlong/eitfm/corpus_shape_20261102/manifest.csv现3399057bytes、14300单元/1430000对/143case，SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032；两次只读SHA一致。
- 冻结差异：与声明11900/1190000/119case、SHA=db6b84e5481bc256ab03ae939d3d96125765f1c62ecf5cb0ab6b3264b0666f75不同；原cases.txt仍119条且全在manifest，另24个a前缀case/2400单元。未自动接受新版本或生成过滤替代manifest。
- 代码/记录：当前冻结s2/s3/s6全文SHA与原来源一致；全manifest仍d8b2be8d1f/b1049eac1a，无split/subject/fold列。finite=True/status=done仅生产记录，不是本轮样本数值验收；143case不能直接当143受试者。
- 正式划分：在限定共享项目splits/configs/training/opt/code/data及corpus metadata/既有引用内未找到权威split；cases/shards不是split，val.sh是正演核验。subject语义、case映射、fold/来源SHA缺失，train/val/test重叠未检查，不能称无泄漏。
- 子集/入口：PILOT_SUBSET_DESCRIPTOR.json明确不可训练、train/val均未选，已有val是否存在未知，不用test补位。所查s4_models.py等仍frames.npz demo计时入口，路径/当前SHA/配置行证据已交；02需准备已核真实入口。
- 交付：S00/REALDATA_SOURCE_AUDIT.json为02读取总入口；realdata_source_audit_20261105/{REALDATA_SOURCE_AUDIT.json,PILOT_SUBSET_DESCRIPTOR.json,REPORT.md,evidence/remote_metadata.json,evidence/remote_followup.json}。原始证据/新描述逐文件SHA见SHA256_INDEX.json。
- 保留/边界：原05部署包、07部署/失败、s6及02配对helper保护SHA不变；未改共享数据、split、候选/阈值、其它任务或Git暂存区。已知22job/1196节点秒无增量，05/07仍待后置具体核验。
- 下一步：协调/数据维护方明确准确冻结manifest及已有正式split路径/版本/SHA、subject映射；之后核无重叠、按seed2026只选正式train<=2人/各8单元及已有val<=1人/4单元。数据与02具体包经协调核验后，优先唯一38/36核、24GiB同limit、900秒真实小训练；不另造划分或重复请求训练方向授权。
