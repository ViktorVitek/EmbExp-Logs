
import sys
import os
import logging
import subprocess
import random

# helpers
# ======================================
logs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
def get_logs_path(path):
	return os.path.join(logs_path, path)

def call_cmd_get_output(cmdl, error_msg, show_error = True):
	error_file = None
	if not show_error:
		error_file = subprocess.DEVNULL
	proc = subprocess.Popen(cmdl, stdout=subprocess.PIPE)
	proc.wait()
	res = proc.poll()
	if res != 0:
		raise Exception(f"command {cmdl} not successful: {res} : {error_msg}")
	return proc.stdout.read()

def call_cmd(cmdl, error_msg, show_output = True, show_error = True):
	output_file = None
	if not show_output:
		output_file = subprocess.DEVNULL
	error_file = None
	if not show_error:
		error_file = subprocess.DEVNULL
	res = subprocess.call(cmdl, stdout=output_file, stderr=error_file)
	if res != 0:
		raise Exception(f"command {cmdl} not successful: {res} : {error_msg}")

def comparefile(filename, content, printifdifferent = False):
	if not os.path.exists(filename):
		return True

	with open(filename, "rb") as f:
		file_content = f.read()
	result = file_content == content

	if not result:
		sys.stderr.write("=" * 40 + "\n")
		sys.stderr.write(f"file doesn't match: {filename}\n")
		sys.stderr.write("=" * 40 + "\n")
		sys.stderr.write(content.decode("utf-8", errors="ignore"))
		sys.stderr.write("\n")
		sys.stderr.write("=" * 40 + "\n")
		sys.stderr.flush()

	return result

def writefile_or_compare(forcenew, filename, content, errmsg):
	if forcenew or not os.path.exists(filename):
		with open(filename, "wb+") as f:
			f.write(content)
			return
	if not comparefile(filename, content, True):
		raise Exception(f"file {filename} has unexpected content: {errmsg}")

def reg_gen(regs):
	regx = "x"+str(random.randint(0,31))
	regw = "w"+str(random.randint(0,31))

	if regx not in regs:
		return [regw, regx]
	else:
		return reg_gen(regs)	
		
def gen_input_code_reg(regmap, asm):
	use_constmov = True
	for reg in regmap.keys():
		val = regmap[reg]
		assert val < 2**64
		assert val >= 0
		val_str = val.to_bytes(8, byteorder='big').hex()
		asm_val_l1 = f"\tldr {reg}, =0x{val_str}\n"
		asm_val_lm = ""
		for i in range(4):
			hexstr = val_str[(4-i-1)*2*2:(4-i)*2*2]
			asm_val_lm += f"\tmovk {reg}, #0x{hexstr}, lsl #{16 * i}\n"
		asm_val = asm_val_lm if use_constmov else asm_val_l1
		asm += f"\t// {reg} = 0x{val_str}\n{asm_val}\n"
	return asm
	
def gen_strb_src_reg(regmap):
	asm = ""
	(reg,val) = [(k, v) for k, v in regmap.items()][0]
	val_str = val.to_bytes(8, byteorder='big').hex()
	asm_val = ""
	for i in range(1):
		hexstr = val_str[(4-i-1)*2*2:(4-i)*2*2]
		asm_val += f"\tmovk {reg}, #0x{hexstr}, lsl #{16 * i}\n"
	asm += f"\t// {reg} = 0x{val_str}\n{asm_val}\n"
	return asm

def gen_input_code_mem(memmap, regs, asm):
	for itm in memmap:
		asm += gen_strb_src_reg({regs[0]:itm[2]})
		asm += gen_input_code_reg({regs[1]:itm[0]}, "")
		asm += f"\tstrb {regs[0]}, [{regs[1]}, {str(itm[1])}]\n"
	return asm
	
def mem_parse(memmap):
	flatten  = lambda l: [item for sublist in l for item in sublist]
	def partition(addresses, patterns):
		for pat in patterns:
			yield [a[0] for a in addresses if a[1] == pat]	
       
	adr_mask = 4294967288
	off_mask = 7
	patterns = set(map(lambda x : bin(x & adr_mask), memmap.keys()))
	addr_pat = list(zip (memmap.keys(), list(map(lambda x : bin(x & adr_mask), memmap.keys()))))
	partitioned_based_on_pattern = list(partition(addr_pat, patterns))
	# (address, offset, value)
	address_and_offset_value = list(map(lambda x :
                                       (list(map (lambda y :
                                            (y & adr_mask, y & off_mask, memmap[y]), x))),
                                       partitioned_based_on_pattern))
	return (flatten (address_and_offset_value))
	
def gen_input_code(regmap):
	asm = ""	
	memmap={}

	for k in regmap['mem'].keys():
		memmap[int(k)] = regmap['mem'][k]
	del regmap['mem']

	asm = gen_input_code_reg(regmap, asm)
	regs = reg_gen(regmap.keys())
	mem_parsed = mem_parse(memmap)
	asm += gen_input_code_mem(mem_parsed, regs, "")
	return asm

def gen_readable(regmap):
	s = ""
	for reg in regmap.keys():
		val = regmap[reg]
		assert val < 2**64
		assert val >= 0
		val_str = "0x" + val.to_bytes(8, byteorder='big').hex()
		ts_str  = "0x" + ((val >>  0) & (0xFFFFFFFFFFFFFFFF - 0x3F)).to_bytes(8, byteorder='big').hex()
		s_str   = "0x" + ((val >>  6) & 0x7F).to_bytes(1, byteorder='big').hex()
		o_str   = "0x" + ((val >>  0) & 0x3F).to_bytes(1, byteorder='big').hex()
		s += f"{reg.ljust(5)} = {val_str} ::: (ts={ts_str}, s={s_str}, o={o_str})\n"
	return s

def check_uart_experiment_base(lines):
	initcompleteline = "Init complete."
	exception_prefix = "EXCEPTION: "
	expcompleteline  = "Experiment complete."

	# remove empty lines from the end
	while len(lines) > 0 and lines[-1] == "":
		lines = lines[:-1]

	if len(lines) < 1 or lines[0] != initcompleteline:
		raise Exception(f"unexpected output: init has never been completed, first line is: {lines[0]}")

	if len(lines) < 2:
		raise Exception(f"unexpected output: only the init line present")

	if lines[1].startswith(exception_prefix):
		return f"embexp.board.exception :::: {lines[1][len(exception_prefix):]}"

	if lines[-1] != expcompleteline:
		raise Exception(f"unexpected output: experiment is never completed")

	return lines[1:-1]

def parse_uart_single_cache_experiment(lines):
	lines = check_uart_experiment_base(lines)
	# has it been an exception on the board?
	if isinstance(lines, str):
		return lines

	sepline = "----"
	funcline_full = "print_cache_full"
	funcline_simp = "print_cache_valid"
	inconclusive_pre = "INCONCLUSIVE: "
	assert len(lines) >= 3
	assert lines[0] == sepline
	assert lines[1] == funcline_full or lines[1] == funcline_simp
	is_func_full = lines[1] == funcline_full
	assert lines[2] == sepline
	lines = lines[3:]
	assert len(lines) >= 1
	if lines[-1].startswith(inconclusive_pre):
		logging.error(f"special result >>> {lines[-1]}")
		lines = lines[:-1]
	assert len(lines) >= 1
	assert lines[-1] == sepline
	lines = lines[:-1]

	if is_func_full:
		return parse_uart_single_cache_experiment_full(lines)
	else:
		return parse_uart_single_cache_experiment_simp(lines)

def parse_uart_single_cache_experiment_simp(lines):
	sets = []
	num_sets = 0
	for line in lines:
		parts = line.split("::")
		s = int(parts[0].strip())
		num_sets = max(num_sets, s+1)
	for s in range(0,num_sets):
		sets.append({"set": s, "lines": []})
	for line in lines:
		parts = line.split("::")
		s = int(parts[0].strip())
		l = int(parts[1].strip())
		d = parts[2].split(":")

		field = d[0].strip()
		data  = d[1].strip()
		l_val = {"line": l, "valid": True, field: data}
		sets[s]["lines"].append(l_val)
	return sets

def parse_uart_single_cache_experiment_full(lines):
	s = 0
	sets = []
	while len(lines) > 0:
		assert lines[0] == f"set={s}"
		lines = lines[1:]
		s_val = {"set": s, "lines": []}
		l = 0
		while len(lines) > 0 and not lines[0].startswith("set"):
			assert lines[0] == f"line={l}"
			lines = lines[1:]
			l_val = {"line": l}
			while len(lines) > 0 and not lines[0].startswith("set") and not lines[0].startswith("line"):
				fielddata = lines[0].split(":")
				lines = lines[1:]
				field = fielddata[0].strip()
				data  = fielddata[1].strip()

				if field == "valid":
					assert data == "0" or data == "1"
					data = data == "1"
				assert not field in l_val
				l_val[field] = data
			s_val["lines"].append(l_val)
			l += 1
		sets.append(s_val)
		s += 1

	return sets

def eval_uart_pair_cache_experiment(lines):
	lines = check_uart_experiment_base(lines)
	if isinstance(lines, str):
		return lines

	resultline_true  = "RESULT: EQUAL"
	resultline_false = "RESULT: UNEQUAL"
	resultline_inconclusive_pre = "INCONCLUSIVE: "

	resultline = lines[0]

	if resultline == resultline_true:
		return True
	elif resultline == resultline_false:
		return False
	elif resultline.startswith(resultline_inconclusive_pre):
		logging.error(f"special result >>> {resultline}")
		return f"special :::: {resultline}"
	else:
		raise Exception(f"the result line is not as expected: {lines[0]}")


