from leaptools.program import Register
import os

soc = os.getenv("TARGET_SOC") or "t8103"

if soc in ["t8103", "t6000", "t8103-t6000"]:
	pdm_ports = [0x26, 0x27, 0x29]
elif soc in ["t8112"]:
	pdm_ports = [0x22, 0x23, 0x25]
elif soc in ["t6020"]:
	pdm_ports = [0x22, 0x23, 0x29]
else:
	raise ValueError(f"unknown SoC: {soc}")

with b.Routine(waitempty_ports=[0x4f], waitfull_ports=pdm_ports):
	pdm_samples = [b.TAKE(port << 24) for port in pdm_ports]

	for i, sample in enumerate(pdm_samples):
		b.PUT(sample, 0x4f_000000)
