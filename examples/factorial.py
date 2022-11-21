from leaptools.program import Register

with b.Routine(waitempty_ports=[0x40], waitfull_ports=[0x41, 0x42]):
	acc = b.PEEK(0x41_000000)
	N = b.PEEK(0x42_000000)

	acc = b.MULT0(acc, N)
	N = b.SUB(1, N)

	b.UPDATE(acc, 0x41_000000)
	b.UPDATE(N, 0x42_000000)
	is_done = b.CMP2(1, N)
	b.TAKEC(is_done, 0x41_000000)
	b.TAKEC(is_done, 0x42_000000)
	b.PUTC(acc, is_done, 0x40_000000)

with b.Routine(waitfull_ports=[0x40]):
	b.TAKE(0x40_000000)
