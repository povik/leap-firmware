LEAPTOOLS = PYTHONPATH=../../:$PYTHONPATH python3 -m leaptools
LEAPTOOLS_IMG = PYTHONPATH=../../:$PYTHONPATH python3 -m leaptools.image

leapmic-passthrough.bin: topology.conf leap_firmware.leapfrog
	ALSA_CONFIG_TPLG=. alsatplg -c $< -o $@

leap_firmware_pre.leapfrog: leap_firmware.py
	$(LEAPTOOLS) -p 'compile_dsl "leap_firmware.py"; image_write "leap_firmware_pre.leapfrog"'

leap_firmware.leapfrog: leap_firmware_pre.leapfrog Makefile
	echo "000000: c900 0000 c900 0000 0000 0000 c900 0000" | \
			xxd -r | $(LEAPTOOLS_IMG) -s $@.tmp $< -a 0x30101 -l 6
	$(LEAPTOOLS_IMG) -s $@.tmp $@.tmp --imprint "leapmic-passthrough `git describe --tags --always --dirty`"
	cp $@.tmp $@
	rm $@.tmp

clean:
	rm leap_firmware.leapfrog leapmic-*.bin
