# Round 2: pre-implementation acceptance contract

Start from the previous 25-case accepted candidate, SHA256
8ec586c60c97bbcdb437fe848b6d9645ea3cfca850952ff9d94c0d36fdaed35d.
Do not change the previous candidate, test suite, report or accepted evidence.

- Parse HBM_NODE as a complete base-10 value with strtol semantics (leading
  whitespace and a plus sign remain accepted); reject empty/malformed/trailing
  text, conversion overflow, negative values and values >=128. The existing
  two-word mask/maxnode=128 defines that upper bound. Rejection disables the
  arena before page-count I/O or policy calls and preserves DDR fallback.
- Keep the existing free-page cap and 16-page reserve. Reject an unrepresentable
  HBM_MIN_KB shift before it wraps. After applying the page cap, reject an
  unrepresentable MB-to-byte shift before mmap. A very large requested HBM_MB
  that safely caps to 64 MB must still work. No new environment parsing policy
  for other variables is introduced in this round.
- Requests whose header/grain rounding cannot be represented must skip HBM and
  use the existing DDR path. In-arena capacity checks must compare sizes with
  remaining bytes before forming a potentially out-of-bounds pointer. Near-end
  fits, exact grain sizes and exact-size reuse remain valid.
- posix_memalign requires a power-of-two alignment >=sizeof(void *). Invalid
  alignments return EINVAL and leave *out unchanged, without initializing HBM.
  Valid alignments <=64 may use HBM; larger alignments retain DDR allocation.
  DDR failure returns ENOMEM and leaves *out unchanged.
- Check free(NULL), exact-size free/reuse, full-arena DDR fallback, realloc grow
  and shrink data preservation, realloc allocation failure preserving the old
  object, and DDR/free/realloc(NULL) forwarding. Do not rewrite free/realloc
  without a demonstrated scoped failure. Zero-size realloc, invalid pointers,
  double-free, concurrent use and real kernel/HBM behavior are not accepted by
  these checks; no new zero-size realloc contract is imposed.

All new behavior tests directly include the actual C implementation. Page-count
I/O, NUMA syscalls, hugepage mmap and controlled libc allocation failures use
substitutes; ordinary DDR allocations/copies/frees use glibc. The same new suite
will run against the preserved previous candidate and the new candidate on
64-bit Linux/glibc, without repeating the old 25 cases. UBSan is required for
the new pointer/size boundaries. This Windows session cannot execute those C
tests; writing their expected failures is not an observed Linux failure.
