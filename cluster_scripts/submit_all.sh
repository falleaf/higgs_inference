#!/bin/bash

cd /home/jb6504/higgs_inference/cluster_scripts

################################################################################
# Default settings
################################################################################

# sbatch run_truth.sh

# sbatch run_histo.sh
# sbatch run_afc.sh

# sbatch run_scoreregression.sh

# sbatch run_carl_point_by_point.sh
# sbatch run_regression_point_by_point.sh

# sbatch run_carl.sh
# sbatch run_combined.sh
# sbatch run_regression.sh
# sbatch run_combinedregression.sh

# sbatch run_carl_aware.sh
# sbatch run_combined_aware.sh
# sbatch run_regression_aware.sh
# sbatch run_combinedregression_aware.sh


################################################################################
# Diagnostics
################################################################################

# sbatch --array=1-4 run_truth_diagnostics.sh

# sbatch --array=1-4 run_histo_diagnostics.sh
# sbatch --array=1-4 run_scoreregression_diagnostics.sh

# sbatch --array=1-4 run_carl_diagnostics.sh
# sbatch --array=1-4 run_combined_diagnostics.sh
# sbatch --array=1-4 run_regression_diagnostics.sh
# sbatch --array=1-4 run_combinedregression_diagnostics.sh


################################################################################
# Smearing
################################################################################


# sbatch run_scoreregression_smearing.sh
# sbatch run_histo_smearing.sh

# sbatch run_carl_smearing.sh
# sbatch run_combined_smearing.sh
# sbatch run_regression_smearing.sh
# sbatch run_combinedregression_smearing.sh


################################################################################
# Hyperparameter scans
################################################################################

# sbatch run_combined_tuning.sh
# sbatch run_combinedregression_tuning.sh

# sbatch run_histo_tuning.sh

# sbatch run_scoreregression_depth_experiments.sh
# sbatch run_carl_depth_experiments.sh
# sbatch run_combined_depth_experiments.sh
# sbatch run_regression_depth_experiments.sh
# sbatch run_combinedregression_depth_experiments.sh
# sbatch run_carl_learning_experiments.sh
# sbatch run_regression_learning_experiments.sh

################################################################################
# Sample size experiments
################################################################################

# sbatch run_scoreregression_samplesize_experiments.sh
# sbatch run_carl_samplesize_experiments.sh
# sbatch run_combined_samplesize_experiments.sh
# sbatch run_regression_samplesize_experiments.sh
# sbatch run_combinedregression_samplesize_experiments.sh


################################################################################
# Follow-up (ALICE)
################################################################################

# sbatch run_mxe.sh
# sbatch run_combinedmxe.sh

# sbatch run_mxe_smearing.sh
# sbatch run_combinedmxe_smearing.sh

# sbatch run_combinedmxe_tuning.sh
# sbatch run_mxe_depth_experiments.sh
# sbatch run_combinedmxe_depth_experiments.sh

# sbatch run_mxe_samplesize_experiments.sh
# sbatch run_combinedmxe_samplesize_experiments.sh


################################################################################
# Flow experiments
################################################################################

sbatch run_maf.sh
sbatch run_scandal.sh

