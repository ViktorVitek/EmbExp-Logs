#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))

import argparse
import logging
import shutil

import experiment
from helpers import *

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("exp_id",             help="id of experiment: arm8/exps2/exp_cache_multiw/{EXPERIMENT_HASH}")
parser.add_argument("input_index",        help="input index to choose from exp_id", type=int, choices=range(1, 3))
parser.add_argument("exp_new_name",       help="id of experiment: arm8/exps2/exp_cache_multiw/{EXPERIMENT_HASH}")

parser.add_argument("-exec", "--execute",    help="run the experiment afterwards", action="store_true")
parser.add_argument("-ra", "--remove_after", help="remove experiment afterwards", action="store_true")

parser.add_argument("-v", "--verbose",    help="increase output verbosity", action="store_true")
args = parser.parse_args()

# set log level
if args.verbose:
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
else:
	logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

exp_id = args.exp_id
exp = experiment.Experiment(exp_id)

input_index = args.input_index
exp_new_name = args.exp_new_name
execute = args.execute
remove_after = args.remove_after

if remove_after and not execute:
	raise Exception("inconsistent parameters selected: won't remove without execute")

# can only handle exps2
exp_type = exp.get_exp_type()
assert exp_type == "exps2"

exp_new_id = f"{exp.get_exp_arch()}/exps1/{exp.get_exp_params_id()}/{exp_new_name}"

files = []
with open(exp.get_path("code.hash", True), "rb") as f:
	files.append(("code.hash", f.read()))
with open(exp.get_path(f"input{input_index}.json", True), "rb") as f:
	files.append(("input1.json", f.read()))

exp_new = experiment.Experiment.create(exp_new_id, files)

if not remove_after:
	print(f"exp_new_id = {exp_new_id}")

if execute:
	try:
		subprocess.call([get_logs_path("scripts/run_experiment.py"), exp_new_id])
	finally:
		if remove_after:
			exp_new_path = os.path.abspath(exp_new.get_path("."))
			shutil.rmtree(exp_new_path)
			print(f"successfully removed experiment directory {exp_new_path}")

