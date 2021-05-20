
import logging
import json

import experiment
import progplatform
from helpers import *

def run_experiment(exp, progplat = None, board_type = None, branchname = None, conn_mode = None, pre_cleanup = None, no_post_cleanup = False, printeval = False, ignoremismatch = False, exprun = None, run_input_state = None):
	logging.info(f"{(exp, progplat, board_type, branchname, conn_mode, pre_cleanup, no_post_cleanup, printeval, ignoremismatch, exprun, run_input_state)}")
	if progplat == None:
		progplat = progplatform.get_embexp_ProgPlatform(None)

	exp_arch = exp.get_prog().get_arch()

	#print(exp_arch);
	# defaults
	if board_type == None:
		if exp_arch == "arm8":
			board_type = "rpi3"

	# can only handle arm8 at the moment, ...
	assert exp_arch == "arm8" or exp_arch == "rv64imac"
	# ... and run on rpi3 or rpi4
	assert board_type == "rpi3" or board_type == "rpi4" or board_type == "genesys_2__cva6"


	# can only handle exps1 and exps2
	exp_type = exp.get_exp_type()
	exp_type = exp_type if run_input_state == None else "exps1"
	assert exp_type == "exps2" or exp_type == "exps1"

	# make sure that progplatform is clean
	# ======================================
	progplat.check_clean(pre_cleanup)

	# change to corresponding branch
	# ======================================
	if branchname == None:
		branchname = progplatform.get_default_branch(board_type)
	progplat.change_branch(branchname)

	try:
		# generate the experiment code
		# ======================================
		logging.info(f"generating experiment code")
		progplat.configure_experiment(board_type, exp, run_input_state=run_input_state)
		run_spec = progplat.get_configured_run_spec()


		# simulation mode
		# ======================================
		simulation_mode = False
		uartlogdata_equal = "Init complete.\nRESULT: EQUAL\nExperiment complete.\n"
		uartlogdata_unequal = "Init complete.\nRESULT: UNEQUAL\nExperiment complete.\n"
		uartlogdata_inconclusive = "Init complete.\nINCONCLUSIVE: 77\nExperiment complete.\n"
		uartlogdata_notfinished = "Init complete.\nRESULT: EQUAL\n"
		uartlogdata_exception = "Init complete.\nException..."
		uartlogdata_noinit = ""
		uartlogdata_options = [uartlogdata_equal, uartlogdata_unequal,
                                       uartlogdata_inconclusive, uartlogdata_notfinished,
                                       uartlogdata_exception, uartlogdata_noinit]
		import random
		uartlogdata_rnd = random.choice(uartlogdata_options)
		uartlogdata_sim = uartlogdata_equal

		# run the experiment
		# ======================================
		logging.info(f"running experiment")
		if simulation_mode:
			logging.error(f"!!! SIMULATION MODE ON !!!!")
			import time
			time.sleep(1)
			uartlogdata = uartlogdata_sim
			print(uartlogdata)
		else:
			uartlogdata = progplat.run_experiment(conn_mode)
		# interpret the experiment result
		uartlogdata_lines = uartlogdata.split("\n")
		if exp_type == "exps2":
			result = eval_uart_pair_cache_experiment(uartlogdata_lines)
		elif exp_type == "exps1":
			result = parse_uart_single_cache_experiment(uartlogdata_lines, board_type)
			# if the result is no board exception
			if not isinstance(result, str):
				# filter sets where at least one line is valid
				sets_valid = list(filter(lambda x: any(l_val["valid"] for l_val in x["lines"]), result))
				# filter valid lines
				sets_clean = list(map(lambda x: {"set": x["set"],"lines": list(filter(lambda l_val: l_val["valid"], x["lines"]))}, sets_valid))
				# remove regs field
				for s_val in sets_clean:
					for l_val in s_val["lines"]:
						for k in list(l_val.keys()):
							if not k in ["line", "valid", "tag"]:
								l_val.pop(k)
				result = sets_clean
		else:
			raise Exception(f"unknown experiment type: {exp_type}")

		# save the outputs and test metadata
		# ======================================
		nomismatches = True
		if exprun != None:
			logging.info(f"saving experiment data")
			run_data = {"output_uart": uartlogdata,
                                    "result":      result}
			nomismatches = exp.write_new_run(exprun, run_spec, run_data)

	finally:
		if not no_post_cleanup:
			# finalize embexp-progplatform
			# ======================================
			logging.info(f"cleaning embexp-progplatform")
			# make progplatform clean to prepare the next round
			progplat.check_clean("ignored" if pre_cleanup == "ignored" else "all")

	if printeval:
		# the last line is a simple result line, that can be interpreted by another program, if exps2
		# ======================================
		if exp_type == "exps2":
			print(f"result = {result}") # don't break this interface!
		elif exp_type == "exps1":
			# if the result is no board exception
			if isinstance(result, str):
				print(f"board_exception = {result}")
			else:
				print("=" * 40)
				for s_val in sets_clean:
					print(f"set {s_val['set']}")
					for l_val in s_val["lines"]:
						print(f"\tline {l_val['line']}, tag: {l_val['tag']}")
				print("=" * 40)
		else:
			raise Exception(f"unknown experiment type: {exp_type}")

	if not nomismatches and not ignoremismatch:
		raise Exception("the output files differ")

	return result
