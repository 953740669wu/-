#!/bin/bash
# Which C/C++ toolchains a node has (PETSc+SuiteSparse need a C++ compiler; compute nodes lack g++).
hostname; uname -m; lscpu | grep -i -E "model name|flags" | cut -c1-300
ls /usr/libexec/gcc/aarch64-linux-gnu/10.3.1/ 2>&1 | tr '\n' ' '; echo
ls /usr/include/c++ 2>&1
find /opt -maxdepth 5 \( -name "clang++" -o -name "g++*" -o -name "clang" -o -name "armclang*" \) 2>/dev/null | head
ls /opt/HPCKit 2>&1; ls /opt/HPCKit/* 2>/dev/null | head -40
