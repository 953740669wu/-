# UBSan 私有依赖来源

目标 C2 登录环境为 Kylin V10 SP4 Jasmine HPC AArch64，GCC 包为 `gcc-10.3.1-66.p02.ky10p.aarch64`，glibc 包为 `glibc-2.34-167.ky10p.aarch64`。GCC 自带的 `libubsan.so` 链接指向缺失的 `/usr/lib64/libubsan.so.1.0.0`。站点本地 repo 配置与部分缓存的权限为 root 限制。

发行版来源为 openEuler 22.03 LTS SP4 官方仓库。使用同 GCC 上游版本和发布号的 AArch64 `libubsan-10.3.1-66.oe2203sp4.aarch64.rpm`。C2 登录端不能解析官网域名，因此在本地通过官方 HTTPS 下载 RPM 和发行版签名公钥，再 SCP 到本轮私有目录。

- RPM SHA256 `380e65f1c04516660c3626890b69f828d839814b4250268d9842503a3e8919eb`
- 签名公钥 SHA256 `006e79d37c10e74c24df6d07c4efc4176515cec009daa5ed493b06f5b6ef39c1`
- RPM RSA/SHA256 签名 key ID `b675600b`，私有 RPM 数据库验签通过，头部及负载摘要通过
- 解包后 AArch64 `libubsan.so.1.0.0` SHA256 `a454036c69151e55228ec086ccc870aca4dc3e64d9a7bcbd1cfd26878c8a106a`
- SONAME `libubsan.so.1`，最高 glibc 符号需求 GLIBC_2.34，登录端依赖可解析。计算端使用明确的私有 `-L` 与 RUNPATH，原正负控和 C50 检查实际加载路径与兼容性。

验签只在私有 RPM 数据库导入公钥。用 `rpm2cpio` 与 `cpio` 提取单个 .so。未执行包脚本或系统安装。全局默认 RPM 数据库查询 RPM 元数据时给出 NOKEY 提示，签名结论来自显式私有数据库的 `rpmkeys --checksig`。

[openEuler 官方 RPM 索引](https://repo.openeuler.org/openEuler-22.03-LTS-SP4/update/aarch64/Packages/) · [openEuler 官方签名公钥说明](https://docs.openeuler.org/en/docs/22.03_LTS_SP4/server/administration/administrator/configuring_the_repo_server.html)