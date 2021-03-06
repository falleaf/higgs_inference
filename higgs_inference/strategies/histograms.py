################################################################################
# Imports
################################################################################

from __future__ import absolute_import, division, print_function

import logging
import time
import numpy as np

from carl.learning.calibration import NDHistogramCalibrator

from higgs_inference import settings
from higgs_inference.various.utils import calculate_mean_squared_error, r_from_s


def histo_inference(indices_X=None,
                    binning='adaptive',
                    use_smearing=False,
                    denominator=0,
                    do_neyman=False,
                    options=''):
    """
    Likelihood ratio estimation through histograms of standard kinematic observables.

    :param indices_X: Defines which of the features to histogram. If None, a default selection of two variables is used.
    :param binning: Binning of the histogram. If 'optimized', use a fixed binning (only supported for jet pT and delta
                    phi). If 'adaptive' (the default), the binning is chosen based on percentiles of the data.
    :param use_smearing: Whether to use the training and evaluation sample with (simplified) detector simulation.
    :param denominator: Which of five predefined denominator (reference) hypotheses to use.
    :param do_neyman: Whether to evaluate the estimator on the Neyman construction samples.
    :param options: Further options in a list of strings or string. Possible options are 'roughbinning', 'finebinning',
                    'superbinning', 'asymmetricbinning', all of which change the number of bins in the 'adaptive' and
                    'optimal' binning modes; 'new' for different samples, and 'neyman2' and 'neyman3' for different
                    Neyman construction samples.
    """

    logging.info('Starting histogram-based inference')

    ################################################################################
    # Settings
    ################################################################################

    rough_binning_mode = ('roughbinning' in options)
    fine_binning_mode = ('finebinning' in options)
    superfine_binning_mode = ('superbinning' in options)
    asymmetric_binning_mode = ('asymmetricbinning' in options)
    new_sample_mode = ('new' in options)
    neyman2_mode = ('neyman2' in options)
    neyman3_mode = ('neyman3' in options)

    if indices_X is None:
        indices_X = [1, 41]  # pT(j1), delta_phi(jj)

    histogram_dimensionality = len(indices_X)

    filename_addition = '_' + str(histogram_dimensionality) + 'd'

    bins = binning

    # Manually chosen histogram binning
    if binning == 'optimized' or binning == 'adaptive':

        # 200 bins
        bins_pt = np.array(
            [0., 48., 58., 67., 75., 83., 91., 100., 109., 119., 130., 141., 155., 172., 193., 221., 260., 325., 462.,
             14000.])  # 20 bins
        bins_deltaphi = np.linspace(0., np.pi, 11)  # 10 bins

        if superfine_binning_mode:  # 1200 bins
            bins_pt = np.array([0., 35., 40., 44., 47., 50., 53., 55., 58.,
                                60., 62., 64., 66., 68., 70., 72., 74., 76.,
                                78., 80., 82., 84., 86., 88., 90., 92., 94.,
                                95., 97., 100., 102., 104., 106., 108., 110., 113.,
                                115., 118., 120., 123., 125., 128., 131., 134., 137.,
                                139., 142., 145., 149., 152., 156., 159., 163., 167.,
                                172., 176., 181., 186., 192., 197., 203., 210., 218.,
                                225., 235., 244., 255., 266., 280., 294., 311., 331.,
                                355., 385., 424., 470., 539., 657., 872., 14000.])  # 80 bins
            bins_deltaphi = np.linspace(0., np.pi, 16)  # 15 bins

        elif fine_binning_mode:  # 480 bins
            bins_pt = np.array([0., 40., 47., 53., 58., 62., 67., 70., 74.,
                                78., 82., 86., 90., 94., 98., 103., 107., 111.,
                                116., 122., 127., 132., 138., 144., 151., 158., 166.,
                                174., 184., 196., 209., 224., 242., 264., 292., 329.,
                                382., 468., 654., 14000.])  # 40 bins
            bins_deltaphi = np.linspace(0., np.pi, 13)  # 12 bins

        elif rough_binning_mode:  # 60 bins overall
            bins_pt = np.array([0., 59., 77., 94., 113., 136., 166., 213., 315., 14000.])  # 10 bins
            bins_deltaphi = np.linspace(0., np.pi, 7)  # 6 bins

        if histogram_dimensionality == 2 and indices_X == [1, 41]:
            bins = (bins_pt, bins_deltaphi)

        elif histogram_dimensionality == 2 and indices_X == [41, 1]:
            bins = (bins_deltaphi, bins_pt)

        elif histogram_dimensionality == 1 and indices_X == [1]:
            bins_pt = np.array([0., 40., 47., 53., 58., 62., 67., 70., 74.,
                                78., 82., 86., 90., 94., 98., 103., 107., 111.,
                                116., 122., 127., 132., 138., 144., 151., 158., 166.,
                                174., 184., 196., 209., 224., 242., 264., 292., 329.,
                                382., 468., 654., 14000.])  # 40 bins
            bins = (bins_pt,)
            filename_addition = '_ptj'

        elif histogram_dimensionality == 1 and indices_X == [41]:
            bins_deltaphi = np.linspace(0., np.pi, 21)
            bins = (bins_deltaphi,)
            filename_addition = '_deltaphi'

        else:
            raise ValueError(indices_X)

    if asymmetric_binning_mode:
        filename_addition += '_asymmetricbinning'
    elif superfine_binning_mode:
        filename_addition += '_superfinebinning'
    elif fine_binning_mode:
        filename_addition += '_finebinning'
    elif rough_binning_mode:
        filename_addition += '_roughbinning'

    input_X_prefix = ''
    if use_smearing:
        input_X_prefix = 'smeared_'
        filename_addition += '_smeared'

    input_filename_addition = ''
    if denominator > 0:
        input_filename_addition = '_denom' + str(denominator)
        filename_addition += '_denom' + str(denominator)

    if new_sample_mode:
        filename_addition += '_new'

    n_expected_events_neyman = settings.n_expected_events_neyman
    neyman_filename = 'neyman'
    if neyman2_mode:
        neyman_filename = 'neyman2'
        n_expected_events_neyman = settings.n_expected_events_neyman2
    if neyman3_mode:
        neyman_filename = 'neyman3'
        n_expected_events_neyman = settings.n_expected_events_neyman3

    results_dir = settings.base_dir + '/results/histo'
    neyman_dir = settings.neyman_dir + '/histo'

    logging.info('Settings:')
    logging.info('  Statistics:              x %s', indices_X)
    logging.info('  Binning:                 %s', bins)

    ################################################################################
    # Data
    ################################################################################

    X_test = np.load(
        settings.unweighted_events_dir + '/' + input_X_prefix + 'X_test' + input_filename_addition + '.npy')
    r_test = np.load(settings.unweighted_events_dir + '/r_test' + input_filename_addition + '.npy')

    X_illustration = np.load(
        settings.unweighted_events_dir + '/' + input_X_prefix + 'X_illustration' + input_filename_addition + '.npy')

    if do_neyman:
        X_neyman_alternate = np.load(
            settings.unweighted_events_dir + '/neyman/' + input_X_prefix + 'X_' + neyman_filename + '_alternate.npy')
    n_events_test = X_test.shape[0]

    ################################################################################
    # Loop over theta
    ################################################################################

    expected_llr = []
    mse_log_r = []
    trimmed_mse_log_r = []
    mse_log_r_train = []
    cross_entropies_train = []
    eval_times = []

    # Loop over the hypothesis thetas
    # for i, t in enumerate(settings.extended_pbp_training_thetas):
    for t, theta in enumerate(settings.thetas):

        if (t + 1) % 100 == 0:
            logging.info('Starting theta %s / %s', t + 1, settings.n_thetas)

        # logging.info('Starting theta %s/%s: number %s (%s)',
        #             i + 1, len(settings.extended_pbp_training_thetas), t, settings.thetas[t])

        # Load data
        new_sample_prefix = '_new' if new_sample_mode else ''
        X_train = np.load(
            settings.unweighted_events_dir + '/point_by_point/' + input_X_prefix + 'X_train_point_by_point_' + str(
                t) + input_filename_addition + new_sample_prefix + '.npy')
        y_train = np.load(
            settings.unweighted_events_dir + '/point_by_point/y_train_point_by_point_' + str(
                t) + input_filename_addition + new_sample_prefix + '.npy')
        r_train = np.load(
            settings.unweighted_events_dir + '/point_by_point/r_train_point_by_point_' + str(
                t) + input_filename_addition + new_sample_prefix + '.npy')

        # Construct summary statistics
        summary_statistics_train = X_train[:, indices_X]
        summary_statistics_test = X_test[:, indices_X]
        summary_statistics_illustration = X_illustration[:, indices_X]

        ################################################################################
        # Adaptive binning
        ################################################################################

        if binning == 'adaptive':

            if histogram_dimensionality == 2 and indices_X == [1, 41]:

                n_bins_pt = 20
                n_bins_deltaphi = 10
                if rough_binning_mode:
                    n_bins_pt = 10
                    n_bins_deltaphi = 5
                elif fine_binning_mode:
                    n_bins_pt = 30
                    n_bins_deltaphi = 15
                elif superfine_binning_mode:
                    n_bins_pt = 50
                    n_bins_deltaphi = 20
                elif asymmetric_binning_mode:
                    n_bins_pt = 50
                    n_bins_deltaphi = 5

                bins_pt = np.percentile(summary_statistics_train[:, 0], np.linspace(0., 100., n_bins_pt))
                bins_pt[0] = 0.
                bins_pt[-1] = 14000.

                bins_deltaphi = np.percentile(summary_statistics_train[:, 1], np.linspace(0., 100., n_bins_deltaphi))
                bins_deltaphi[0] = -.1
                bins_deltaphi[-1] = np.pi + 0.1

                bins = (bins_pt, bins_deltaphi)

            elif histogram_dimensionality == 1 and indices_X == [1]:
                n_bins_pt = 80

                bins_pt = np.percentile(summary_statistics_train[:, 0], np.linspace(0., 100., n_bins_pt))
                bins_pt[0] = 0.
                bins_pt[-1] = 14000.
                bins = (bins_pt,)

            elif histogram_dimensionality == 1 and indices_X == [41]:
                n_bins_deltaphi = 20

                bins_deltaphi = np.percentile(summary_statistics_train[:, 0], np.linspace(0., 100., n_bins_deltaphi))
                bins_deltaphi[0] = -.1
                bins_deltaphi[-1] = np.pi + 0.1
                bins = (bins_deltaphi,)

            else:
                raise ValueError

        ################################################################################
        # "Training"
        ################################################################################

        histogram = NDHistogramCalibrator(bins=bins, range=None)

        histogram.fit(summary_statistics_train,
                      y_train)

        ################################################################################
        # Evaluation
        ################################################################################

        # Evaluation
        time_before = time.time()
        s_hat_test = histogram.predict(summary_statistics_test)
        eval_times.append(time.time() - time_before)
        log_r_hat_test = np.log(r_from_s(s_hat_test))
        s_hat_train = histogram.predict(summary_statistics_train)
        log_r_hat_train = np.log(r_from_s(s_hat_train))

        # Extract numbers of interest
        expected_llr.append(- 2. * settings.n_expected_events / n_events_test * np.sum(log_r_hat_test))
        mse_log_r.append(calculate_mean_squared_error(np.log(r_test[t]), log_r_hat_test, 0.))
        trimmed_mse_log_r.append(calculate_mean_squared_error(np.log(r_test[t]), log_r_hat_test, 'auto'))

        # For some benchmark thetas, save r for each phase-space point
        if t == settings.theta_benchmark_nottrained:
            np.save(results_dir + '/r_nottrained_histo' + filename_addition + '.npy', np.exp(log_r_hat_test))
        elif t == settings.theta_benchmark_trained:
            np.save(results_dir + '/r_trained_histo' + filename_addition + '.npy', np.exp(log_r_hat_test))

        # Calculate cross-entropy
        mse_log_r_train.append(calculate_mean_squared_error(np.log(r_train), log_r_hat_train, 0.))
        cross_entropy_train = - (y_train * np.log(s_hat_train)
                                 + (1. - y_train) * np.log(1. - s_hat_train)).astype(np.float128)
        cross_entropy_train = np.mean(cross_entropy_train)
        cross_entropies_train.append(cross_entropy_train)

        ################################################################################
        # Illustration
        ################################################################################

        if t == settings.theta_benchmark_illustration:
            r_hat_illustration = r_from_s(histogram.predict(summary_statistics_illustration))
            np.save(results_dir + '/r_illustration_histo' + filename_addition + '.npy', r_hat_illustration)

        ################################################################################
        # Neyman construction toys
        ################################################################################

        if do_neyman:
            # Neyman construction: prepare alternate data and construct summary statistics
            summary_statistics_neyman_alternate = X_neyman_alternate.reshape((-1, X_neyman_alternate.shape[2]))
            summary_statistics_neyman_alternate = summary_statistics_neyman_alternate[:, indices_X]

            # Neyman construction: evaluate alternate sample
            s_hat_neyman_alternate = histogram.predict(summary_statistics_neyman_alternate)
            log_r_hat_neyman_alternate = np.log(r_from_s(s_hat_neyman_alternate))
            log_r_hat_neyman_alternate = log_r_hat_neyman_alternate.reshape((-1, n_expected_events_neyman))

            llr_neyman_alternate = -2. * np.sum(log_r_hat_neyman_alternate, axis=1)
            np.save(
                neyman_dir + '/' + neyman_filename + '_llr_alternate_' + str(t) + '_histo' + filename_addition + '.npy',
                llr_neyman_alternate)

            # Neyman construction: null
            X_neyman_null = np.load(
                settings.unweighted_events_dir + '/neyman/' + input_X_prefix + 'X_' + neyman_filename + '_null_' + str(
                    t) + '.npy')
            summary_statistics_neyman_null = X_neyman_null.reshape(
                (-1, X_neyman_null.shape[2]))[:, indices_X]

            # Evaluation
            s_hat_neyman_null = histogram.predict(summary_statistics_neyman_null)
            log_r_hat_neyman_null = np.log(r_from_s(s_hat_neyman_null))
            log_r_hat_neyman_null = log_r_hat_neyman_null.reshape((-1, n_expected_events_neyman))
            llr_neyman_null = -2. * np.sum(log_r_hat_neyman_null, axis=1)
            np.save(neyman_dir + '/' + neyman_filename + '_llr_null_' + str(
                t) + '_histo' + filename_addition + '.npy',
                    llr_neyman_null)

            # Neyman construction: null evaluated at alternative
            if t == settings.theta_observed:
                # for tt in settings.extended_pbp_training_thetas:
                for tt in range(settings.n_thetas):
                    X_neyman_null = np.load(
                        settings.unweighted_events_dir + '/neyman/' + input_X_prefix + 'X_' + neyman_filename + '_null_' + str(
                            tt) + '.npy')
                    summary_statistics_neyman_null = X_neyman_null.reshape(
                        (-1, X_neyman_null.shape[2]))[:, indices_X]

                    # Evaluation
                    s_hat_neyman_null = histogram.predict(summary_statistics_neyman_null)
                    log_r_hat_neyman_null = np.log(r_from_s(s_hat_neyman_null))
                    log_r_hat_neyman_null = log_r_hat_neyman_null.reshape((-1, n_expected_events_neyman))
                    llr_neyman_null = -2. * np.sum(log_r_hat_neyman_null, axis=1)
                    np.save(neyman_dir + '/' + neyman_filename + '_llr_nullatalternate_' + str(
                        tt) + '_histo' + filename_addition + '.npy',
                            llr_neyman_null)

    # Evaluation times
    logging.info('Evaluation timing: median %s s, mean %s s', np.median(eval_times), np.mean(eval_times))

    # Interpolate and save evaluation results
    expected_llr = np.asarray(expected_llr)
    mse_log_r = np.asarray(mse_log_r)
    trimmed_mse_log_r = np.asarray(trimmed_mse_log_r)
    mse_log_r_train = np.asarray(mse_log_r_train)
    cross_entropies_train = np.asarray(cross_entropies_train)

    np.save(results_dir + '/llr_histo' + filename_addition + '.npy', expected_llr)
    np.save(results_dir + '/mse_logr_histo' + filename_addition + '.npy', mse_log_r)
    np.save(results_dir + '/trimmed_mse_logr_histo' + filename_addition + '.npy', trimmed_mse_log_r)
    np.save(results_dir + '/mse_logr_train_histo' + filename_addition + '.npy',
            mse_log_r_train)
    np.save(results_dir + '/cross_entropy_train_histo' + filename_addition + '.npy',
            cross_entropies_train)

    logging.info('Mean training cross-entropy: %s', np.mean(cross_entropies_train))
    logging.info('Mean training log r: %s', np.mean(mse_log_r_train))
