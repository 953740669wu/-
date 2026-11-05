"""New cases only; prior candidate expectations fixed before implementation."""


def cases():
    rows = []

    def add(name, args, previous_failure=False, sanitizer_failure=False):
        rows.append(dict(name=name, args=args, previous_failure=previous_failure,
                         sanitizer_failure=sanitizer_failure))

    for name, value in (("negative", "-1"), ("upper", "128"),
                        ("conversion_overflow", "999999999999999999999999999999999"),
                        ("empty", ""), ("text", "HBM"), ("suffix", "16tail"),
                        ("hex", "0x10"), ("trailing_space", "16 ")):
        add("node_" + name, ["node", "invalid", value], True)
    for name, value in (("zero", "0"), ("normal", "16"), ("word_end", "63"),
                        ("word_start", "64"), ("last", "127"),
                        ("plus", "+16"), ("leading_space", " 16")):
        add("node_" + name, ["node", "valid", value])
    for name in ("mb_overflow", "mb_last_safe", "min_overflow", "min_last_safe", "mb_large_capped"):
        add(name, ["config", name], name in ("mb_overflow", "min_overflow"))
    for name in ("sum_max", "sum_first_overflow", "sum_last_safe", "pointer_wrap",
                 "api_sum_max", "last_fit", "short_tail", "grain_below", "grain_exact", "grain_above"):
        bad = name in ("sum_max", "sum_first_overflow", "sum_last_safe", "pointer_wrap", "api_sum_max")
        add(name, ["request", name], bad, name in ("sum_last_safe", "pointer_wrap"))
    for align in (0, 1, 3, 4, 24, 48):
        add("align_invalid_" + str(align), ["align", "invalid", str(align)], True)
    for align in (8, 16, 32, 64, 128, 4096):
        add("align_valid_" + str(align), ["align", "valid", str(align)])
    for name in ("free_null", "free_reuse", "realloc_grow", "realloc_shrink",
                 "realloc_failure", "ddr_forward", "ddr_failure", "full_fallback"):
        add(name, ["api", name])
    return rows
