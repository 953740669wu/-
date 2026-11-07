M23 本地回传校验故障记录

- SCP 下载多文件时对第二个文件再次显示 SSH 密码提示，ZIP 已传完、回执尚未就绪。首次分析返回 FileNotFoundError: bundle_receipt.json。完成同一下载后再分析，未重新提交作业。
- 回执与 ZIP 核验通过后，旧分析器在 summarize_rank 试图把 frame_ids 字典放进 set，返回 TypeError: unhashable type: 'dict'。修订逐帧规范化序列化和序列逐项相等检查，已抽取原件只读逐字节核对。
- 登录端只读查询原始 djob -J 返回相邻两段 JSON，第一版试读产生 JSONDecodeError: Extra data；dnode/dqueue 的 data 是列表，试读产生 AttributeError: 'list' object has no attribute 'get'。远端提交器已按实际多文档输出逐段解析，保留 queue_before_submit.json 原件。
