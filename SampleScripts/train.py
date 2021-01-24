import os, subprocess, shutil, sys
import argparse
import pandas as pd

script_dirpath = os.path.dirname(os.path.realpath(__file__))

## Location of the processed CSV files generated by MG-CFD's 'aggregate-output-data.py':
parser = argparse.ArgumentParser()
parser.add_argument('--data-dirpath', required=True, help="Dirpath to MG-CFD runs processed output data")
args = parser.parse_args()
processed_performance_data_dirpath = args.data_dirpath

## Location of directory containing 'train_model.R':
model_src_dirpath = os.path.join(script_dirpath, "../Main")


## Now train the model to estimate CPI rates of CPU execution units:
tdir = os.path.join(script_dirpath, "Training")
if not os.path.isdir(tdir):
	os.mkdir(tdir)


for f in ["PAPI.mean.csv", "Times.mean.csv"]:
# for f in ["Times.mean.csv"]:
	src_fp = os.path.join(processed_performance_data_dirpath, f)
	dest_fp = os.path.join(tdir, f)
	## Check if csv needs to be pivoted into old format:
	df = pd.read_csv(src_fp, na_filter=False)
	if "Loop" in df.columns.values:
		## Need to pivot!
		df["MG level"] = df["MG level"].astype(int)
		if "Time" in df.columns.values:
			value_colname = "Time"
		else:
			value_colname = "Count"
		pivot_cols = list(set(df.columns.values).difference(["Loop", "MG level", value_colname]))
		df2 = df.pivot_table(index=pivot_cols, columns=["Loop", "MG level"], values=value_colname)
		df2.columns = [''.join([str(x) for x in col]).strip() for col in df2.columns.values]
		df2.reset_index(inplace=True)
		df2.to_csv(dest_fp, index=False)
	else:
		shutil.copyfile(src_fp, dest_fp)


insn_counts_filename = None
for f in ["instruction-counts.mean.csv", "instruction-counts.csv"]:
	if os.path.isfile(os.path.join(processed_performance_data_dirpath, f)):
		insn_counts_filename = f
		break
if insn_counts_filename is None:
	raise Exception("Cannot find aggregated instruction counts csv")
f = insn_counts_filename
src_fp = os.path.join(processed_performance_data_dirpath, f)
dest_fp = os.path.join(tdir, f)
## Check if csv needs to be pivoted into old format:
df = pd.read_csv(src_fp, na_filter=False)
if "Instruction" in df.columns.values:
	## Need to pivot!
	instructions = list(set(df["Instruction"]))
	pivot_cols = list(set(df.columns.values).difference(["Instruction", "Count"]))
	df2 = df.pivot_table(index=pivot_cols, columns="Instruction", values="Count", fill_value=0)
	df2.reset_index(inplace=True)
	renames = {i:"insn."+i for i in instructions}
	df2.rename(columns=renames, inplace=True)
	df2.rename(columns={"Loop":"kernel"}, inplace=True)
	df2.to_csv(dest_fp, index=False)
else:
	shutil.copyfile(src_fp, dest_fp)


loop_num_iters_filename = None
for f in ["LoopNumIters.mean.csv", "LoopNumIters.csv"]:
	if os.path.isfile(os.path.join(processed_performance_data_dirpath, f)):
		loop_num_iters_filename = f
		break
if loop_num_iters_filename is None:
	raise Exception("Cannot find aggregated LoopNumIters csv")
f = loop_num_iters_filename
src_fp = os.path.join(processed_performance_data_dirpath, f)
dest_fp = os.path.join(tdir, f)
## Check if csv needs to be pivoted into old format:
df = pd.read_csv(src_fp, na_filter=False)
if "Loop" in df.columns.values:
	## Need to pivot!
	pivot_cols = list(set(df.columns.values).difference(["Loop", "MG level", "NumIters"]))
	df2 = df.pivot_table(index=pivot_cols, columns=["Loop", "MG level"], values="NumIters")
	df2.columns = [''.join([str(x) for x in col]).strip() for col in df2.columns.values]
	df2.reset_index(inplace=True)
	df2.rename(columns={"Metric":"counter", "Loop":"kernel"}, inplace=True)
	df2.to_csv(dest_fp, index=False)
else:
	shutil.copyfile(src_fp, dest_fp)


os.chdir(tdir)
subprocess.call(["Rscript", model_src_dirpath+"/train_model.R"])
if not os.path.isfile("cpi_estimates.csv"):
	raise Exception("Training failed")
quit()


os.chdir("../")
pdir="Prediction"
if not os.path.isdir(pdir):
	os.mkdir(pdir)
for f in ["cpi_estimates.csv"]:
	shutil.copyfile(os.path.join("Training", f), os.path.join(pdir, f))

# Prune cpi_estimates:
cpi_estimates = pd.read_csv(os.path.join(pdir, "cpi_estimates.csv"))
if "model_fitting_strategy" in cpi_estimates.columns.values:
	cpi_estimates = cpi_estimates[cpi_estimates["model_fitting_strategy"]=="miniDifferences"]
	if cpi_estimates.shape[0] == 0:
		raise Exception("Filtering cpi_estimates.csv has removed all rows")
if "do_spill_penalty" in cpi_estimates.columns.values:
	cpi_estimates = cpi_estimates[cpi_estimates["do_spill_penalty"]==False]
	if cpi_estimates.shape[0] == 0:
		raise Exception("Filtering cpi_estimates.csv has removed all rows")
cpi_estimates.to_csv(os.path.join(pdir, "cpi_estimates.csv"), index=False)

