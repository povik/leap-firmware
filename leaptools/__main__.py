import traceback
import argparse
import pathlib
import sys
from ast import literal_eval

from .program import *
from .passes import PASSES

def lookup_pass(name):
    if name in PASSES:
        return PASSES[name]

    candidates = [p for n, p in PASSES.items() if n.startswith(name)]
    if not len(candidates):
        avail = ''.join(f"\t{name}\n" for name in PASSES.keys())
        print(f"No pass starting with: {name}\nAvailable passes:\n{avail}", file=sys.stderr)
        sys.exit(1)
    elif len(candidates) > 1:
        matches = ', '.join(p.__name__ for p in candidates)
        print(f"Ambiguous pass name: {name}\nMatches {matches}", file=sys.stderr)
        sys.exit(1)

    return candidates[0]

def run_passes(p, commands):
    for passtext in commands.replace("\n", ";").split(";"):
        if passtext.strip() == "" or passtext.startswith("#"):
            continue
        name, *passargs = passtext.strip().split(" ")

        f = lookup_pass(name)

        try:
            f(p, *[literal_eval(arg) for arg in passargs])
        except:
            print(f"Running of pass {f.__name__.upper()} caused an exception:\n", file=sys.stderr)
            for l in traceback.format_exc().split("\n"):
                print(f"  {l}\n", file=sys.stderr, end="")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Operate on a LEAP program')
    parser.add_argument('-p', '--run-passes', type=str, default="")
    parser.add_argument('-H', '--list-passes', action='store_true')
    parser.add_argument('-s', '--script', type=str, default="")
    parser.add_argument('image', type=pathlib.Path, nargs="?")

    args = parser.parse_args()

    if args.list_passes:
        for name, f in PASSES.items():
            print(name, file=sys.stderr)
            print(f.__doc__, file=sys.stderr)
        sys.exit(0)

    if args.image is not None:
        with args.image.open("rb") as f:
            img = Image.read(f)
        prg = Program.from_image(img)
    else:
        prg = Program()

    if args.script:
        run_passes(prg, open(args.script).read())

    if args.run_passes:
        run_passes(prg, args.run_passes)

if __name__ == "__main__":
    main()
