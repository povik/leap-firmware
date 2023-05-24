import sys
from .types import Opcode
from .program import Routine, Instruction, Operand, Constant

OPCODES = dict([(opcode.name, opcode) for opcode in Opcode])

'''
For some operations we need to adjust the operand mapping to make it
more convenient (and save the user from having to pass in dummy operands
to reach desired operand slots).
'''
OPERAND_SIEVE = {
	Opcode.TAKE:   (False, False, True),
	Opcode.TAKEC:  (False, True, True),
	Opcode.PEEK:   (False, False, True),
	Opcode.PUT:    (True, False, True),
	Opcode.PUTC:   (True, True, True),
	Opcode.UPDATE: (True, False, True),
	Opcode.F32_FMT: (False, True, True),
	Opcode.FMULT:   (False, True, True),
	Opcode.FMULT_NEG: (False, True, True),

	Opcode.MULT0:  (False, True, True)
}

class _EnterRoutineHelper:
	def __init__(self, b, r):
		self.b, self.r = b, r

	def __enter__(self):
		self.b.curr_rout = self.r
		return self

	def __exit__(self, a, b, c):
		self.b.curr_rout = None

class Builder:
	def __init__(self, prg):
		self.prg = prg
		self.curr_rout = None
		self.nroutines = 0
		self.ninstr = 0

	def Routine(self, *args, **kwargs):
		r = Routine(*args, **kwargs)
		self.prg.routines.append(r)
		self.nroutines += 1
		return _EnterRoutineHelper(self, r)

	def special(self, reg):
		self.prg.register_specials.add(reg)

	def update(self, glob, val):
		assim = self._assimilate_val(val)
		glob.cases.append(self.OR(assim, assim))

	@classmethod
	def _assimilate_val(self, val):
		if isinstance(val, Operand):
			return val
		elif type(val) is float:
			return Constant.from_float(val)
		else:
			return Constant(int(val))

	def __getattribute__(self, attrname):
		if attrname not in OPCODES:
			return object.__getattribute__(self, attrname)
		opcode = OPCODES[attrname]
		def opcode_wrapper(*ops):
			assert self.curr_rout is not None
			ops = [self._assimilate_val(op) for op in ops]
			if opcode in OPERAND_SIEVE:
				userops = ops
				sieve = OPERAND_SIEVE[opcode]
				ops = [ userops.pop(0) if alive else None for alive in sieve ]
			inst = Instruction(opcode, None, *ops)
			self.curr_rout.instr.append(inst)
			self.ninstr += 1
			frame = sys._getframe(1)
			inst.src = f"{frame.f_code.co_filename}:{frame.f_lineno}"
			return inst
		return opcode_wrapper
