#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))

import argparse
import logging

import logsdb as ldb
import exprun
import holbarun
import logslist
import progplatform
import experiment
from helpers import *
from exp_runner import *

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-ai", "--arch_id",       help="architecture id, default: arm8", choices=['arm8', 'rv64imac']) #why not default here?
parser.add_argument("-bt", "--board_type", help="broad_type", choices=['rpi3', 'rpi4', 'genesys_2__cva6'])
parser.add_argument("-rs", "--run_spec", help="spec of run made up of ProgPlatform commit hash and board type, for example: 13700076ab79095f15468f0c489fa587ac225626.rpi3")

parser.add_argument("-ln", "--listname", help="list to use as set of experiments")

parser.add_argument("-ps", "--print_structures",      help="print the holbaruns, and prog/exp lists", action="store_true")

parser.add_argument("-pp", "--print_progs",           help="print the list of programs", action="store_true")

parser.add_argument("-pe", "--print_examples",        help="print the list of validation examples", action="store_true")
parser.add_argument("-pc", "--print_counterexamples", help="print the list of counterexamples", action="store_true")
parser.add_argument("-pi", "--print_inconclusive",    help="print the list of inconclusive examples", action="store_true")
parser.add_argument("-po", "--print_others",          help="print the list of unclear examples", action="store_true")

parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
args = parser.parse_args()

# set log level
if args.verbose:
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
else:
	logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

arch_id = args.arch_id
board_type = args.board_type
# defaults
if arch_id == None:
	arch_id = "arm8" #why use default in parser?
if board_type == None:
	if arch_id == "arm8":
		board_type = "rpi3"

# obtain run_spec
run_spec = args.run_spec
if run_spec == None:
	assert arch_id == "arm8" or arch_id == "rv64imac"
	assert board_type == "rpi3" or board_type == "rpi4" or board_type == "genesys_2__cva6"
	progplat_hash = progplatform.get_embexp_ProgPlatform(None).get_branch_commit_hash(
		progplatform.get_default_branch(board_type))
	run_spec = experiment._mk_run_spec(progplat_hash, board_type)

print(f"run_spec = {run_spec}")
print()

print("opening db...")
print()
db = ldb.LogsDB(read_only=True)
db.connect()

if args.print_structures:
	print("holba runs: ")
	for hbar in holbarun.HolbaRun._get_all(db):
		print(f"- '{hbar.get_name()}'")
	print("experiment lists: ")
	for el in logslist.LogsList._get_all(db, "exp"):
		print(f"- '{el.get_name()}' (cnt={len(el.get_entry_ids())}, '{el.get_description()}')")
	print("program lists: ")
	for el in logslist.LogsList._get_all(db, "prog"):
		print(f"- '{el.get_name()}' (cnt={len(el.get_entry_ids())}, '{el.get_description()}')")
	print("exp runs: ")
	for expr in exprun.ExpRun._get_all(db):
		print(f"- '{expr.get_name()}'")
	print()

listname = args.listname
exps = None
if listname != None:
	exps = logslist.LogsList._get_by_name(db, "exp", listname).get_entries()
	exps = list(map(lambda exp: exp[1], exps))
	print(f"found {len(exps)} experiments in list {listname}")
else:
	exps = experiment.Experiment._get_all(db)
	print(f"found {len(exps)} experiments in the database")
	logging.warning("the output is for all experiments in the database!")

# filter out the valid experiments
exps = list(filter(lambda exp: exp.is_valid_experiment(), exps))

# collect all programs and experiments
print()
logging.info("collecting all programs and experiments")
print(f"n_exps  = {len(exps)}")
print()
print()

# collect statistics
e_notrun       = []
e_incomplete   = []
e_examples     = []
e_cexamples    = []
e_inconclusive = []
e_others       = []
for exp in exps:
	assert exp.get_prog().get_arch() == arch_id
	exp_id = exp.get_exp_id()

	# did it run?
	run_id = exp.get_latest_run_id(run_spec)
	if run_id == None:
		e_notrun.append(exp_id)
		continue

	run_data = exp.get_run_data(run_id)

	# is it complete?
	if not experiment.Experiment.is_complete_run(run_data):
		e_incomplete.append(exp_id)
		continue

	# what's the result?
	result = run_data["result"]
	if result == True:
		e_examples.append(exp_id)
	elif result == False:
		e_cexamples.append(exp_id)
	elif result.startswith("special :::: INCONCLUSIVE: "):
		e_inconclusive.append(exp_id)
	else:
		e_others.append(exp_id)

print(f"n_notrun     = {len(e_notrun)}")
print(f"n_incomplete = {len(e_incomplete)}")
print()

print(f"n_others       = {len(e_others)}")
print(f"n_inconclusive = {len(e_inconclusive)}")
print(f"n_examples     = {len(e_examples)}")
print(f"n_cexamples    = {len(e_cexamples)}")
print()
print()

if args.print_progs:
	print("programs:")
	print("=" * 40)
	for p in progs:
		print(p)
	print()
	print()

if args.print_examples:
	print("validation examples:")
	print("=" * 40)
	for exp_id in e_examples:
		print(exp_id)
	print()
	print()

if args.print_counterexamples:
	print("validation counterexamples:")
	print("=" * 40)
	for exp_id in e_cexamples:
		print(exp_id)
	print()
	print()

if args.print_inconclusive:
	print("inconclusive examples:")
	print("=" * 40)
	for exp_id in e_inconclusive:
		print(exp_id)
	print()
	print()

if args.print_others:
	print("unclear result:")
	print("=" * 40)
	for exp_id in e_others:
		print(exp_id)
	print()
	print()
