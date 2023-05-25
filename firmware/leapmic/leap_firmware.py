from leaptools.program import Register
from leaptools.iir import *

Fbase = 2400000 // 5

def convolve(aa, bb):
	acc = 0.0
	for a_, b_ in zip(aa, bb):
		acc = b.FMULTACC(acc, a_, b_)
	return acc

w_c = 22000 / Fbase * 2 * math.pi
filt1 = butter(3)(Rational([-1.0, 1.0], [1.0, 1.0]) / math.tan(w_c / 2))

save1, save2, save3, save4 = \
	Global(init=0.0), Global(init=0.0), Global(init=0.0), Global(init=0.0)

pdm_save = Global(init=0.0)
dc_block_save = Global(init=0.0)

with b.Routine(waitempty_ports=[0x61], waitfull_ports=[0x26, 0x27, 0x29]):
	pdm_samples = [b.TAKE(port << 24) for port in [0x26, 0x27, 0x29]]

	input_select = b.PEEK(0x62 << 24)
	pdm_selected = b.MUX(
		b.MUX(pdm_samples[0], pdm_samples[1], b.ROT(input_select)),
		pdm_samples[2], input_select
	)

	pdm1 = b.F32_FMT(10 << 22, b.PDM6(0x40000000, pdm_selected))
	pdm2 = b.F32_FMT(10 << 22, b.PDM6(0x00000000, pdm_selected))

	dc_block1 = b.FSUB(pdm_save, pdm1)
	dc_block2 = b.FSUB(pdm1, pdm2)
	b.update(pdm_save, pdm2)

	pdm1_dc_blocked = b.FMULTACC(dc_block1, dc_block_save, 0.9996)
	pdm2_dc_blocked = b.FMULTACC(dc_block2, pdm1_dc_blocked, 0.9996)

	b.update(dc_block_save, pdm2_dc_blocked)

	hist1 = [
		save1,
		save2,
		save3,
		save4,
	]

	samp1 = b.FMULT(b.FSUB(
		convolve(reversed(hist1), reversed(filt1.q.coeffs[:-1])),
		pdm1_dc_blocked,
	), 1/filt1.q.coeffs[-1])
	
	hist1.pop(0); hist1.append(samp1)

	samp2 = b.FMULT(b.FSUB(
		convolve(reversed(hist1), reversed(filt1.q.coeffs[:-1])),
		pdm2_dc_blocked,
	), 1/filt1.q.coeffs[-1])

	hist1.pop(0); hist1.append(samp2)

	b.PUT(convolve(hist1, filt1.p.coeffs), 0x61 << 24)

	b.update(save1, save3)
	b.update(save2, save4)
	b.update(save3, samp1)
	b.update(save4, samp2)

w_c = 24000 / (Fbase // 2) * 2 * math.pi
filt2 = butter(4)(Rational([-1.0, 1.0], [1.0, 1.0]) / math.tan(w_c / 2))

save1, save2, save3, save4, save5 = \
	Global(init=0.0), Global(init=0.0), Global(init=0.0), Global(init=0.0), Global(init=0.0)

decimation = Global(init=0)

with b.Routine(waitempty_ports=[0x4f], waitfull_ports=[0x61]):
	hist2 = [
		save1,
		save2,
		save3,
		save4,
		save5
	]

	samp = b.FMULT(b.FSUB(
		convolve(reversed(hist2), reversed(filt2.q.coeffs[:-1])),
		b.TAKE(0x61 << 24)
	), 1/filt2.q.coeffs[-1])

	b.PUTC(convolve(hist2, filt2.p.coeffs), decimation, 0x4f << 24)

	b.update(decimation, 
		b.MUX(b.ADD_UNS(decimation, 0x80000010 // 4), 0, decimation)
	)

	b.update(save1, save2)
	b.update(save2, save3)
	b.update(save3, save4)
	b.update(save4, save5)
	b.update(save5, samp)
