LEAPTOOLS = PYTHONPATH=../../:$PYTHONPATH python3 -m leaptools

leapmic-passthrough.bin: topology.conf leap_firmware.leapfrog
	ALSA_CONFIG_TPLG=. alsatplg -c $< -o $@

leap_firmware.leapfrog: leap_firmware.py
	$(LEAPTOOLS) -p 'compile_dsl "leap_firmware.py"; image_write "leap_firmware.leapfrog"'

clean:
	rm leap_firmware.leapfrog leapmic-*.bin
