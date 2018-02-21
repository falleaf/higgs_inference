#! /usr/bin/env python

################################################################################
# Imports
################################################################################

from __future__ import absolute_import, division, print_function

import argparse
import logging
from os import sys, path

base_dir = path.abspath(path.join(path.dirname(__file__), '..'))

try:
    from higgs_inference import settings
except ImportError:
    if base_dir in sys.path:
        raise
    sys.path.append(base_dir)
    from higgs_inference import settings

from higgs_inference.various.p_values import calculate_all_CL
from higgs_inference.strategies.truth import truth_inference
from higgs_inference.strategies.local_model import local_model_truth_inference
from higgs_inference.strategies.afc import afc_inference
from higgs_inference.strategies.histograms import histo_inference

try:
    from higgs_inference.strategies.parameterized import parameterized_inference
    from higgs_inference.strategies.point_by_point import point_by_point_inference
    from higgs_inference.strategies.score_regression import score_regression_inference

    loaded_ml_strategies = True

except ImportError:
    loaded_ml_strategies = False

################################################################################
# Set up logging and parse arguments
################################################################################

settings.base_dir = base_dir

# Set up logging
logging.basicConfig(format='%(asctime)s %(levelname)s    %(message)s', level=logging.DEBUG, datefmt='%d.%m.%Y %H:%M:%S')
logging.info('Hi! How are you today?')

# Parse arguments
parser = argparse.ArgumentParser(description='Inference experiments for Higgs EFT measurements')

parser.add_argument('algorithm', help='Algorithm type. Options are "p" or "cl" for the calculation of p values '
                                      + 'through the Neyman construction; "truth", "localmodel", '
                                      + '"afc", "histo", "carl", "score" (in the carl setup), '
                                      + '"combined" (carl + score), "regression", "combinedregression" '
                                      + '(regression + score), or "scoreregression" (regresses on the score and '
                                      + 'performs density estimation on theta times score.')
parser.add_argument("-pbp", "--pointbypoint", action="store_true",
                    help="Point-by-point rather than parameterized setup.")
parser.add_argument("-a", "--aware", action="store_true",
                    help="Physics-aware parameterized setup.")
parser.add_argument("-s", "--smearing", action='store_true', help='Train and evaluate on smeared observables.')
parser.add_argument("-t", "--training", default='baseline', help='Training sample: "baseline", "basis", or "random".')
parser.add_argument("-x", "--xindices", type=int, nargs='+', default=[1, 38, 39, 40, 41],
                    help='X components to be used for histograms and AFC.')
parser.add_argument("--alpha", type=float, default=None, help='Factor scaling the score regression loss in the'
                                                              + ' parameterized combined approaches.')
parser.add_argument("-e", "--epsilon", type=float, default=None, help='Epsilon for AFC')
parser.add_argument("-n", "--neyman", action='store_true',
                    help='Calculate toy experiments for the Neyman construction.')
parser.add_argument("-o", "--options", nargs='+', default='', help="Further options to be passed on to the algorithm.")

args = parser.parse_args()

logging.info('Startup options:')
logging.info('  Algorithm:                     %s', args.algorithm)
logging.info('  Point by point:                %s', args.pointbypoint)
logging.info('  Morphing-aware mode:           %s', args.aware)
logging.info('  Smeared data:                  %s', args.smearing)
logging.info('  Training sample:               %s', args.training)
logging.info('  Histogram / AFC X indices:     %s', args.xindices)
logging.info('  alpha:                         %s', args.alpha)
logging.info('  AFC epsilon:                   %s', args.epsilon)
logging.info('  Neyman construction toys:      %s', args.neyman)
logging.info('  Other options:                 %s', args.options)
logging.info('  Base directory:                %s', settings.base_dir)
logging.info('  ML-based strategies available: %s', loaded_ml_strategies)

# Sanity checks
assert args.algorithm in ['p', 'cl', 'pvalues',
                          'truth', 'localmodel', 'histo', 'afc',
                          'carl', 'score', 'combined', 'regression', 'combinedregression',
                          'scoreregression']
assert args.training in ['baseline', 'basis', 'random']

################################################################################
# Do something
################################################################################

# Start calculation
if args.algorithm in ['p', 'cl', 'pvalues']:
    calculate_all_CL()

elif args.algorithm == 'truth':
    truth_inference(do_neyman=args.neyman,
                    options=args.options)

elif args.algorithm == 'localmodel':
    local_model_truth_inference(do_neyman=args.neyman,
                                options=args.options)

elif args.algorithm == 'histo':
    histo_inference(indices_X=args.xindices,
                    use_smearing=args.smearing,
                    do_neyman=args.neyman,
                    options=args.options)

elif args.algorithm == 'afc':
    afc_inference(indices_X=args.xindices,
                  epsilon=args.epsilon,
                  use_smearing=args.smearing,
                  do_neyman=args.neyman,
                  options=args.options)

elif args.algorithm == 'scoreregression':
    assert loaded_ml_strategies
    score_regression_inference(use_smearing=args.smearing,
                               do_neyman=args.neyman,
                               options=args.options)

elif args.pointbypoint:
    assert loaded_ml_strategies
    point_by_point_inference(algorithm=args.algorithm,
                             use_smearing=args.smearing,
                             do_neyman=args.neyman,
                             options=args.options)

else:
    assert loaded_ml_strategies
    parameterized_inference(algorithm=args.algorithm,
                            morphing_aware=args.aware,
                            use_smearing=args.smearing,
                            training_sample=args.training,
                            alpha=args.alpha,
                            do_neyman=args.neyman,
                            options=args.options)

logging.info("That's it -- have a great day!")
