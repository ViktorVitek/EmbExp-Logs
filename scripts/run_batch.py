#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))

import argparse
import logging
import time

import logsdb as ldb
import exprun
import experiment
import logslist
import exp_finder
import progplatform
import exp_runner

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-ln", "--listname",    help="name of experiment list")
parser.add_argument("-bt", "--board_type",  help="broad_type", choices=["rpi3", "rpi4", "genesys_2__cva6"], default="rpi3")

parser.add_argument(       "--run_once",    help="collect experiments in the beginning and run each experiment just once", action="store_true")

parser.add_argument("-ep", "--embexp_path", help="see run_experiment.py.")
parser.add_argument("-cm", "--conn_mode",   help="see run_experiment.py.", choices=["try", "run", "reset"])

parser.add_argument("-v",  "--verbose",     help="increase output verbosity", action="store_true")
args = parser.parse_args()

# set log level
if args.verbose:
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
else:
	logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

listname   = args.listname
board_type = args.board_type
run_once   = args.run_once

# create prog platform object
progplat = progplatform.get_embexp_ProgPlatform(args.embexp_path)

# db connection
print("opening db...")
print()
db = ldb.LogsDB()
db.connect()

# define experiment finding
progplat_hash = progplat.get_branch_commit_hash(progplatform.get_default_branch(board_type))
run_spec = experiment._mk_run_spec(progplat_hash, board_type)

def is_latest_exp_run_not_complete(exp):
	run_id = exp.get_latest_run_id(run_spec)
	if run_id == None:
		return True # no run
	run_data = exp.get_run_data(run_id)
	return not experiment.Experiment.is_complete_run(run_data)

def is_all_true(x):
	return True

def genfun_fromexplist(filterfun, listname):
	exps = logslist.LogsList._get_by_name(db, "exp", listname).get_entries()
	exps = map(lambda x: x[1], exps)
	return list(filter(filterfun, exps))

def genfun_allexps(filterfun):
	exps = experiment.Experiment._get_all(db)
	return list(filter(filterfun, exps))

# select input experiment source
if listname == None:
	genfun  = genfun_allexps
	genargs = {}
else:
	genfun  = genfun_fromexplist
	genargs = {"listname": listname}

# filter for incomplete experiments by default
genargs["filterfun"] = is_latest_exp_run_not_complete

# poll by default
do_poll = True

# if "run_once", we take each experiment from the source into account (exactly once, no polling)
if run_once:
	genargs["filterfun"] = is_all_true
	do_poll = False

# create iterator
if do_poll:
	exp_iter = exp_finder.PollingIterator(genfun, genargs)
else:
	exp_iter = exp_finder.NonPollingListIterator(genfun(**genargs))

# create exp run in db
exprun = exprun.ExpRun._create(db)

# launch the runner script for each experiment in the list
# ======================================
logging.info(f"running all selected experiments")
n_exp_runs = 0
n_exp_runs_success = 0
all_start_time = time.time()
try:
	for exp in exp_iter:
		start_time = time.time()
		def print_runtime():
			print(f"         - took {time.time()-start_time:.2f}s")
		n_exp_runs += 1
		# reload experiment for latest values
		exp = experiment.Experiment(db, exp.get_exp_id())

		(iter_round, iter_idx, iter_size) = exp_iter.get_iterinfo()
		print(f"===>>> [r:{iter_round}, {(iter_idx/iter_size * 100):.2f}% of {iter_size}] {exp}")
		try:
			result_val = exp_runner.run_experiment(exp, progplat, board_type, conn_mode=args.conn_mode, exprun=exprun)
			print_runtime()
			n_exp_runs_success += 1
			if result_val != True:
				print(f"         - Interesting result: {result_val}")
		except KeyboardInterrupt:
			raise
		except:
			print_runtime()
			logging.warning("- unsuccessful")
except KeyboardInterrupt:
	print("-> script was cancelled by keyboard interrupt")

print()
print("="*40)
print("="*40)
all_time = time.time()-all_start_time
print(f"ran for {all_time:.2f}s")
print(f"{n_exp_runs_success} of {n_exp_runs} attempted experiment runs gave a result")
if (n_exp_runs > 0):
	print(f"average execution time {all_time/n_exp_runs:.2f}s")
if (n_exp_runs_success > 0):
	print(f"run_spec = {run_spec}")
print("="*40)
assert(n_exp_runs_success <= n_exp_runs)
successful = n_exp_runs_success == n_exp_runs
if successful:
	print("ALL STARTED EXPERIMENT RUNS COMPLETED")
else:
	print("SOME EXPERIMENT RUNS DID NOT COMPLETE")


sys.exit(0 if successful else 1)
