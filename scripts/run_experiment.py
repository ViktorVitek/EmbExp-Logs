#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))

import argparse
import logging

import logsdb as ldb
import experiment
import progplatform
import exp_runner

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("exp_id", help="id of experiment in database", type=int)
parser.add_argument("-bt", "--board_type", help="broad_type", choices=["rpi3", "rpi4", "genesys_2__cva6"], default="rpi3")

parser.add_argument("-br", "--branchname", help="branch of ProgPlatform, default is 'scamv_{board_type}'")

parser.add_argument("-is", "--input_state", help="run as single experiment with given input state name")

parser.add_argument("-ep", "--embexp_path", help="path to embexp repositories")
parser.add_argument("-cm", "--conn_mode", help="connection mode: try (default), run, reset. 'try' for trying an active connection, otherwise do ad-hoc connect (runlog_try, default). 'reset' for connect with reset (runlog_reset). 'run' for simply using an active connection (runlog).", choices=["try", "run", "reset"])

# pre-cleanup of progplatform
parser.add_argument("-fca", "--force_cleanup_all",     help="force full cleanup before running", action="store_true")
parser.add_argument("-fci", "--force_cleanup_ignored", help="force cleanup of all gitignored files before running", action="store_true")
# post-cleanup of progplatform
parser.add_argument("-npc", "--no_post_clean",    help="do not cleanup after running", action="store_true")

parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
args = parser.parse_args()

# set log level
if args.verbose:
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
else:
	logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

if args.force_cleanup_all and args.force_cleanup_ignored:
	raise Exception("inconsistent parameters: not --force_cleanup_all and --force_cleanup_ignored at the same time")

if args.force_cleanup_all:
	force_cleanup = "all"
elif args.force_cleanup_ignored:
	force_cleanup = "ignored"
else:
	force_cleanup = None

# create prog platform object
progplat = progplatform.get_embexp_ProgPlatform(args.embexp_path)

# db connection
print("opening db...")
print()
with ldb.LogsDB() as db:
	exp = experiment.Experiment(db, int(args.exp_id))
	exp_runner.run_experiment(exp, progplat, args.board_type, args.branchname, args.conn_mode, force_cleanup, args.no_post_clean, True, run_input_state=args.input_state)
