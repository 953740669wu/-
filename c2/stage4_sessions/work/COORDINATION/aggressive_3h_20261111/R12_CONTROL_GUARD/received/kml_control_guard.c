#include <stdint.h>
uint64_t read_fpcr(void) {
    uint64_t v; __asm__ volatile("mrs %0, fpcr" : "=r"(v)); return v;
}
uint64_t read_svcr(void) {
    uint64_t v; __asm__ volatile("mrs %0, S3_3_C4_C2_2" : "=r"(v)); return v;
}
void restore_fpcr(uint64_t v) {
    __asm__ volatile("msr fpcr, %0; isb" :: "r"(v) : "memory");
}
void stop_streaming(void) {
    __asm__ volatile(".inst 0xd503427f" ::: "memory");
}
