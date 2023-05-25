LEAPTOOLS = PYTHONPATH=../../:$PYTHONPATH python3 -m leaptools
LEAPTOOLS_IMG = PYTHONPATH=../../:$PYTHONPATH python3 -m leaptools.image

T8103_MODELS = j293 j313 j456 j457
T6000_MODELS = j314 j316
T8112_MODELS = j493 j413
T6020_MODELS = j414 j416

ALL_MODELS = $(T8103_MODELS) $(T8112_MODELS) $(T6000_MODELS) $(T6020_MODELS)

build_all: $(foreach target, $(ALL_MODELS), build/$(FWNAME)-$(target).bin)

$(foreach target, $(T8103_MODELS), build/$(FWNAME)-$(target).bin): build/$(FWNAME)-t8103-t6000.bin
	ln -s $(FWNAME)-t8103-t6000.bin $@

$(foreach target, $(T8112_MODELS), build/$(FWNAME)-$(target).bin): build/$(FWNAME)-t8112.bin
	ln -s $(FWNAME)-t8112.bin $@

$(foreach target, $(T6000_MODELS), build/$(FWNAME)-$(target).bin): build/$(FWNAME)-t8103-t6000.bin
	ln -s $(FWNAME)-t8103-t6000.bin $@

$(foreach target, $(T6020_MODELS), build/$(FWNAME)-$(target).bin): build/$(FWNAME)-t6020.bin
	ln -s $(FWNAME)-t6020.bin $@

build/leap_firmware-%.leapfrog: leap_firmware.py build_dir
	TARGET_SOC=$* \
		$(LEAPTOOLS) -p 'compile_dsl "$<"; image_write "$@.tmp"'
	echo "000000: 0000 0000" | \
			xxd -r | $(LEAPTOOLS_IMG) -s $@.tmp $@.tmp -a 0x30100 -l 98
	echo "000000: c900 0000 c900 0000 c900 0000 c900 0000" | \
			xxd -r | $(LEAPTOOLS_IMG) -s $@.tmp $@.tmp -a 0x30101 -l 0
	echo "000000: c900 0000 c900 0000 c900 0000 c900 0000" | \
			xxd -r | $(LEAPTOOLS_IMG) -s $@.tmp $@.tmp -a 0x30101 -l 4
	echo "000000: c900 0000 c900 0000" | \
			xxd -r | $(LEAPTOOLS_IMG) -s $@.tmp $@.tmp -a 0x30101 -l 8
	$(LEAPTOOLS_IMG) -s $@.tmp $@.tmp --imprint "$(FWNAME) `git describe --tags --always --dirty`"
	cp $@.tmp $@
	rm $@.tmp

build/$(FWNAME)-%.bin: topology-%.conf build/leap_firmware-%.leapfrog
	ALSA_CONFIG_DIR=$(shell pwd) ALSA_CONFIG_TPLG=. alsatplg -c $< -o $@

clean:
	rm -f build/*

build_dir:
	mkdir -p build
