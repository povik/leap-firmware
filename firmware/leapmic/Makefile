FWNAME=leapmic
include ../shared.mk

$(FWNAME).bin: topology.conf leap_firmware.leapfrog
	ALSA_CONFIG_TPLG=. alsatplg -c $< -o $@.tmp

	# Workaround for ALSA topology compiler having no way to set
	# the 'mask' field of the enum control struct
	python -c "b = bytearray(open('$@.tmp', 'rb').read()); \
				idx = b.index(b'Mic 1'); b[idx-8] = 3; open('$@', 'wb').write(b);"
	rm $@.tmp
