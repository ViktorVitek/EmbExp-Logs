
import logging
import os

import experiment
from helpers import *

def _autodetect_embexp_path(embexp_arg = None):
	embexp_path = embexp_arg
	if embexp_path == None:
		embexp_path = os.path.expandvars("${HOLBA_EMBEXP_DIR}")
	if not os.path.isdir(embexp_path):
		raise Exception(f"Path to embexp is not an existing directory: {embexp_path}")
	embexp_path = os.path.abspath(embexp_path)
	return embexp_path

def get_embexp_ProgPlatform(embexp_arg):
	const_envnameprogplat = "EMBEXP_PROGPLATFORM"
	if const_envnameprogplat in os.environ:
		progplat_path = os.environ[const_envnameprogplat]
	else:
		embexp_path = _autodetect_embexp_path(embexp_arg)
		progplat_path = os.path.join(embexp_path, "EmbExp-ProgPlatform")
	assert os.path.isdir(progplat_path)
	return ProgPlatform(progplat_path)

def get_default_branch(board_type):
	assert board_type != None
	assert board_type == "rpi3" or board_type == "rpi4" or board_type == "genesys_2__cva6"
	return "scamv_" + board_type

class ProgPlatform:
	def __init__(self, progplat_path):
		self.progplat_path = embexp_path = os.path.abspath(progplat_path)
		assert os.path.isdir(self.progplat_path)
		logging.debug(f"using {self.progplat_path}")

		self.show_outputs = logging.getLogger().level <= logging.DEBUG

		self._writable = False
		self.board_type = None

	def get_commit_hash(self):
		progplat_hash = self._call_git_cmd_get_output(["rev-parse", "HEAD"], "coudln't get commit hash")
		return progplat_hash.decode("ascii").strip()

	def get_branch_commit_hash(self, branchname):
		try:
			progplat_hash = self._call_git_cmd_get_output(["rev-parse", branchname], "coudln't get commit hash")
		except:
			# TODO: fix better handling of this case
			progplat_hash = self._call_git_cmd_get_output(["rev-parse", f"origin/{branchname}"], "coudln't get commit hash")
		return progplat_hash.decode("ascii").strip()

	def get_configured_run_spec(self):
		assert self.board_type != None
		progplat_hash = self.get_commit_hash()
		return experiment._mk_run_spec(progplat_hash, self.board_type)

	def _get_git_call(self):
		return ["git", "--git-dir", f"{self.progplat_path}/.git", "--work-tree", self.progplat_path]

	def _call_git_cmd_get_output(self, gitcmdl, error_msg):
		return call_cmd_get_output(self._get_git_call() + gitcmdl, error_msg, self.show_outputs)

	def _call_git_cmd(self, gitcmdl, error_msg):
		call_cmd(self._get_git_call() + gitcmdl, error_msg, self.show_outputs, self.show_outputs)

	def _call_make_cmd(self, makecmdl, error_msg):
		call_cmd(["make", "-C", self.progplat_path] + makecmdl, error_msg, self.show_outputs, self.show_outputs)

	def check_clean(self, force_cleanup = None):
		if force_cleanup == "ignored":
			logging.debug("cleaning only ignored files/directories in the repository")
			self._call_git_cmd(["clean", "-fdX", self.progplat_path],  "couldn't clean progplatform")
			logging.debug("checking whether there are no ignored files left")
			lines = self._call_git_cmd_get_output(["status", "--ignored", "--porcelain"], "error checking for clean repo").split(b'\n')
			is_clean = all(map(lambda x: not x.startswith(b'!!'), lines))
			if not is_clean:
				raise Exception("something went wrong with cleaning, there are still ignored files left")
			self._writable = True
			return
		elif force_cleanup == "all":
			logging.debug("forcing full reset and cleanup of repository")
			self._call_git_cmd(["checkout", "--", self.progplat_path], "couldn't reset progplatform")
			self._call_git_cmd(["clean", "-fd",   self.progplat_path], "couldn't clean progplatform")
			self._call_git_cmd(["clean", "-fdX",  self.progplat_path], "couldn't clean (ignored) progplatform")
		elif force_cleanup == None:
			logging.debug("no cleanup of repository")
		else:
			raise Exception(f"unknown option for force_cleanup: {force_cleanup}")
		logging.debug("checking whether git repository is clean")
		is_clean = self._call_git_cmd_get_output(["status", "--porcelain"], "error checking for clean repo") == b''
		if not is_clean:
			raise Exception(f"check your working directory \"{self.progplat_path}\". either commit and push your changes or just clean it.")
		self._writable = True

	def change_branch(self, branchname):
		assert self._writable
		self._call_git_cmd(["checkout", branchname], f"couldn't checkout branch {branchname}")
		self._call_git_cmd(["clean", "-fd",  self.progplat_path], "couldn't clean progplatform")
		# this is redundant I guess
		self._call_git_cmd(["clean", "-fdX", self.progplat_path], "couldn't clean (ignored) progplatform")

	def write_experiment_file(self, filename, contents):
		assert self._writable
		with open(os.path.join(self.progplat_path, f"all/inc/experiment/{filename}"), "w+") as f:
			f.write(contents)

	def configure_experiment(self, board_type, exp, num_mul_runs = 10, run_input_state = None):
		assert self._writable
		exp_type = exp.get_exp_type()
		exp_type = exp_type if run_input_state == None else "exps1"
		assert exp_type == "exps2" or exp_type == "exps1"

		self.board_type = board_type

		logging.debug(f"reading input files")
		code_asm = exp.get_prog().get_code()
		train    = exp.get_input_state("input_train")
		input1   = exp.get_input_state("input_1" if run_input_state == None else run_input_state)
		assert input1 != None
		if exp_type == "exps2":
			input2   = exp.get_input_state("input_2")
			assert input2 != None
		else:
			input2 = None

		defmem_train = None if train == None else (train["mem"]["default"])
		defmem_1     = None if input1 == None else (input1["mem"]["default"])
		defmem_2     = None if input2 == None else (input2["mem"]["default"])

		config_text = ""
		config_text += f"PROGPLAT_ARCH         ={exp.get_prog().get_arch()}\n"
		config_text += f"PROGPLAT_TYPE         ={exp_type}\n"
		config_text += f"PROGPLAT_PARAMS       ={exp.get_exp_params()}\n"
		config_text += f"PROGPLAT_BOARD        ={board_type}\n"
		if exp_type == "exps2":
			config_text += f"PROGPLAT_RUN_TIMEOUT  =180\n"
		elif exp_type == "exps1":
			config_text += f"PROGPLAT_RUN_TIMEOUT  =80\n"
		config_text += f"__PROGPLAT_MUL_RUNS__ ={num_mul_runs}\n"
		config_text += "" if defmem_train == None else f"__PROGPLAT_MEM_DEF_TRAIN__  =expmem_byte_to_word({defmem_train})\n"
		config_text += "" if defmem_1 == None     else f"__PROGPLAT_MEM_DEF_1__  =expmem_byte_to_word({defmem_1})\n"
		config_text += "" if defmem_2 == None     else f"__PROGPLAT_MEM_DEF_2__  =expmem_byte_to_word({defmem_2})\n"

		with open(os.path.join(self.progplat_path, f"Makefile.config"), "w+") as f:
			f.write(config_text)

		self.write_experiment_file("asm.h", code_asm)
		if train != None:
			self.write_experiment_file("asm_setup_train.h", gen_input_code(train))
		self.write_experiment_file("asm_setup_1.h", gen_input_code(input1))
		if exp_type == "exps2":
			self.write_experiment_file("asm_setup_2.h", gen_input_code(input2))


	def run_experiment(self, conn_mode = None):
		error_msg = "experiment didn't run successful"
		maketarget = "targetdoesnotexist"
		if conn_mode == "try" or conn_mode == None:
			maketarget = "runlog_try"
		elif conn_mode == "run":
			maketarget = "runlog"
		elif conn_mode == "reset":
			maketarget = "runlog_reset"
		else:
			raise Exception(f"invalid conn_mode: {conn_mode}")
		self._call_make_cmd([maketarget], error_msg)
		# read and return the uart output (binary)
		with open(os.path.join(self.progplat_path, "temp/uart.log"), "r") as f:
				uartlogdata = f.read()
		return uartlogdata
