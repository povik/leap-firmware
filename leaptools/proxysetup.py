from m1n1.setup import *
from m1n1.loadobjs import *
from m1n1.hw.leap import *

soc_compatible = u.adt["/arm-io"].compatible[0]

if soc_compatible == "arm-io,t8103":
    p.write32(0x23d284030, 0xf) # LEAP_AOPCLK
    p.write32(0x23d2840b8, 0xf) # LEAP
    leap_base = 0x24b000000
elif soc_compatible == "arm-io,t6000":
    p.write32(0x292284000 + 4 * 8, 0xf); # LEAP_CLK
    p.write32(0x292284000 + 16 * 8, 0xf); # LEAP
    leap_base = 0x294000000

l = LEAP(u, leap_base)
lp = LinkedProgram(u)
testcluster = l.clusters[1]
lp.load_inline_c(f'''
    #define LEAP_BASE {testcluster.regs._base:#x}
    ''' + '''
    #include "exception.h"
    #include "utils.h"
    #include "soc.h"

    #define LEAP_BANKSIZE 0x40 // cropped

    #define ROUTINE_CTL       0x80008
    #define PC_LIMITS(ridx)   (0x800ac + (4 * ridx))

    typedef struct {
        u32 bank0[LEAP_BANKSIZE];
        u32 bank1[LEAP_BANKSIZE];
        u32 bank2[LEAP_BANKSIZE];
        u32 bank3[LEAP_BANKSIZE];
    } leap_ctx_t;

    typedef struct {
        u32 a, b, c, d;
    } leap_inst_t;

    typedef struct {
        leap_ctx_t ctx;
        leap_inst_t inst;
    } leap_execinfo_t;

    void load_bank(u64 bankbase, u32 *vals)
    {
        for (int i = 0; i < LEAP_BANKSIZE; i++) {
            write32(bankbase + 8 * i, vals[i]);
            //read32(bankbase + 8 * i);
        }
    }

    void clear_bank(u64 base, int size)
    {
        for (int i = 0; i < size; i++)
            write32(base + 8 * i, 0);
    }

    void clear_ctx(void)
    {
        clear_bank(LEAP_BASE + 0x00000, 4096);
        clear_bank(LEAP_BASE + 0x10000, 3072);
        clear_bank(LEAP_BASE + 0x20000, 3072);
        clear_bank(LEAP_BASE + 0x30000, 3072);
    }

    void load_ctx(leap_ctx_t *ctx)
    {
        load_bank(LEAP_BASE + 0x00000, ctx->bank0);
        load_bank(LEAP_BASE + 0x10000, ctx->bank1);
        load_bank(LEAP_BASE + 0x20000, ctx->bank2);
        load_bank(LEAP_BASE + 0x30000, ctx->bank3);
    }

    void save_bank(u64 bankbase, u32 *vals)
    {
        for (int i = 0; i < LEAP_BANKSIZE; i++)
            vals[i] = read32(bankbase + 8 * i);
    }

    void save_ctx(leap_ctx_t *ctx)
    {
        save_bank(LEAP_BASE + 0x00000, ctx->bank0);
        save_bank(LEAP_BASE + 0x10000, ctx->bank1);
        save_bank(LEAP_BASE + 0x20000, ctx->bank2);
        save_bank(LEAP_BASE + 0x30000, ctx->bank3);
    }

    void single_step(int pos)
    {
        int ridx = 0;
        write32(LEAP_BASE + PC_LIMITS(ridx), (pos + 1) << 16 | pos);
        write32(LEAP_BASE + ROUTINE_CTL,   0x100 << ridx); // reset
        write32(LEAP_BASE + ROUTINE_CTL, 0x10000 << ridx); // set single run-through
        write32(LEAP_BASE + ROUTINE_CTL, 0x10001 << ridx); // kick off
    }

    void run_leap_testcases(int n, leap_execinfo_t *in,
                            leap_ctx_t *out_ctx, int flags)
    {
        write32(LEAP_BASE + 0x40000, 0);
        write32(LEAP_BASE + 0x50000, 0);
        write32(LEAP_BASE + 0x60000, 0);
        write32(LEAP_BASE + 0x70000, 0);

        for (int i = 0; i < n; i++) {
            leap_inst_t *inst = &in[i].inst;
            leap_ctx_t *in_ctx = &in[i].ctx;

            write32(LEAP_BASE + 0x40004, inst->a);
            write32(LEAP_BASE + 0x50004, inst->b);
            write32(LEAP_BASE + 0x60004, inst->c);
            write32(LEAP_BASE + 0x70004, inst->d);

            single_step(0); // flush the pipeline by single-stepping elsewhere

            if (flags & 1) clear_ctx();
            load_ctx(in_ctx);
            single_step(1);
            save_ctx(&out_ctx[i]);
        }
    }
    ''')
