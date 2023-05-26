# LEAP firmware

This repository holds open-source LEAP firmware, required for microphone input on Apple Silicon Macs.

## Build Instructions

Requirements:

 * `alsa-utils` (for `alsatplg` compiler of ASoC topology firmware)
 * `xxd`
 * Python 3 with `construct` and `pycosat`

Commands:

```shell
$ make -C firmware/leapmic
```

The built firmware is found in `firmware/leapmic/build/`.

## LEAP tools

In addition to firmware sources themselves, this repository contains tools for analyzing and producing firmware for the LEAP signal processors embedded on Apple SoCs.

### Usage of LEAP tools

Provisional: Running `python -m leaptools --help` and `python -m leaptools --list-passes` gives some pointers.

## License

This software is licensed, to anybody obtaining a copy, under the terms of the 3-clause BSD license as spelled out in the [LICENSE](LICENSE) file. Contributors include sign-offs in their changelogs to certify their contribution in the sense of the [Developer Certificate of Origin](https://developercertificate.org/).
