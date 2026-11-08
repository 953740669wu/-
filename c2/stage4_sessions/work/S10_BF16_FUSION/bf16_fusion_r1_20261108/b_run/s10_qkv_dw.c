#include <stdint.h>
#include <kblas.h>

_Static_assert(sizeof(BLASINT) == sizeof(int), "expected LP64 KML integer ABI");
_Static_assert(sizeof(__bf16) == sizeof(uint16_t), "expected 16-bit BF16 operands");

/* The exact-release declaration supplies the ABI. Torch owns the operand storage. */
void s10_qkv_dw(int m, int n, int k, const uint16_t *g, const uint16_t *x, float *out)
{
    cblas_sbgemm(CblasRowMajor, CblasTrans, CblasNoTrans, m, n, k,
                 1.0f, (const __bf16 *)g, m, (const __bf16 *)x, n, 1.0f, out, n);
}

const void *s10_sbgemm_address(void)
{
    return (const void *)cblas_sbgemm;
}
