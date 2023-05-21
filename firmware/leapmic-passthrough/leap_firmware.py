from leaptools.program import Register

with b.Routine(waitempty_ports=[0x4f], waitfull_ports=[0x26, 0x27, 0x29]):
	pdm_samples = [b.TAKE(port << 24) for port in [0x26, 0x27, 0x29]]

	for i, sample in enumerate(pdm_samples):
		b.PUT(sample, 0x4f_000000)
