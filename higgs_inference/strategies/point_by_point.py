################################################################################
# Imports
################################################################################

from __future__ import absolute_import, division, print_function

import logging
import numpy as np

from scipy.interpolate import LinearNDInterpolator
from sklearn.preprocessing import StandardScaler

from keras.wrappers.scikit_learn import KerasRegressor
from keras.callbacks import EarlyStopping

from carl.ratios import ClassifierScoreRatio
from carl.learning import CalibratedClassifierScoreCV

from higgs_inference import settings
from higgs_inference.various.utils import decide_toy_evaluation
from higgs_inference.models.models_point_by_point import make_classifier, make_regressor


def point_by_point_inference(algorithm='carl',
                             options=''):
    """
    Trains and evaluates one of the point-by-point higgs_inference methods.

    :param algorithm: Type of the algorithm used. Currently supported: 'carl' and 'regression'.
    :param options: Further options in a list of strings or string.
    """

    logging.info('Starting point-by-point inference')

    ################################################################################
    # Settings
    ################################################################################

    assert algorithm in ['carl', 'regression']

    denom1_mode = ('denom1' in options)
    debug_mode = ('debug' in options)
    learn_logr_mode = ('learns' not in options)
    short_mode = ('short' in options)
    long_mode = ('long' in options)
    deep_mode = ('deep' in options)
    shallow_mode = ('shallow' in options)

    filename_addition = ''

    if not learn_logr_mode:
        filename_addition += '_learns'

    n_hidden_layers = settings.n_hidden_layers_default
    if shallow_mode:
        n_hidden_layers = settings.n_hidden_layers_shallow
        filename_addition += '_shallow'
    elif deep_mode:
        n_hidden_layers = settings.n_hidden_layers_deep
        filename_addition += '_deep'

    n_epochs = settings.n_epochs_default
    early_stopping = True
    if debug_mode:
        n_epochs = settings.n_epochs_short
        early_stopping = False
        filename_addition += '_debug'
    elif long_mode:
        n_epochs = settings.n_epochs_long
        filename_addition += '_long'
    elif short_mode:
        n_epochs = settings.n_epochs_short
        early_stopping = False
        filename_addition += '_short'

    theta1 = settings.theta1_default
    input_filename_addition = ''
    if denom1_mode:
        input_filename_addition = '_denom1'
        filename_addition += '_denom1'
        theta1 = settings.theta1_alternative

    results_dir = settings.base_dir + '/results/point_by_point'
    neyman_dir = settings.neyman_dir + '/point_by_point'

    logging.info('Main settings:')
    logging.info('  Algorithm:               %s', algorithm)
    logging.info('Options:')
    logging.info('  Number of epochs:        %s', n_epochs)
    logging.info('  Number of hidden layers: %s', n_hidden_layers)

    ################################################################################
    # Data
    ################################################################################

    X_calibration = np.load(settings.unweighted_events_dir + '/X_calibration' + input_filename_addition + '.npy')
    weights_calibration = np.load(
        settings.unweighted_events_dir + '/weights_calibration' + input_filename_addition + '.npy')

    X_test = np.load(settings.unweighted_events_dir + '/X_test' + input_filename_addition + '.npy')
    r_test = np.load(settings.unweighted_events_dir + '/r_test' + input_filename_addition + '.npy')
    X_neyman_observed = np.load(settings.unweighted_events_dir + '/X_neyman_observed.npy')

    n_events_test = X_test.shape[0]
    assert settings.n_thetas == r_test.shape[0]

    ################################################################################
    # Regression
    ################################################################################

    if algorithm == 'regression':

        expected_llr = []

        # Loop over the training thetas
        for i, t in enumerate(settings.pbp_training_thetas):

            logging.info('Starting theta %s/%s: number %s (%s)', i + 1, len(settings.pbp_training_thetas), t,
                         settings.thetas[t])

            # Load data
            X_train = np.load(
                settings.unweighted_events_dir + '/X_train_point_by_point_' + str(t) + input_filename_addition + '.npy')
            r_train = np.load(
                settings.unweighted_events_dir + '/r_train_point_by_point_' + str(t) + input_filename_addition + '.npy')

            assert np.all(np.isfinite(np.log(r_train)))

            # Scale data
            scaler = StandardScaler()
            scaler.fit(np.array(X_train, dtype=np.float64))
            X_train_transformed = scaler.transform(X_train)
            X_test_transformed = scaler.transform(X_test)
            X_neyman_observed_transformed = scaler.transform(
                X_neyman_observed.reshape((-1, X_neyman_observed.shape[2])))

            assert np.all(np.isfinite(X_train_transformed))
            assert np.all(np.isfinite(X_test_transformed))

            regr = KerasRegressor(lambda: make_regressor(n_hidden_layers=n_hidden_layers),
                                  epochs=n_epochs, validation_split=settings.validation_split,
                                  verbose=2)

            # Training
            regr.fit(X_train_transformed, np.log(r_train),
                     callbacks=(
                         [EarlyStopping(verbose=1,
                                        patience=settings.early_stopping_patience)] if early_stopping else None))

            # Evaluation
            prediction = regr.predict(X_test_transformed)
            this_r = np.exp(prediction[:])

            if not np.all(np.isfinite(prediction)):
                logging.warning('Regression output contains NaNs')

            expected_llr.append(- 2. * settings.n_expected_events / n_events_test * np.sum(np.log(this_r)))

            # For some benchmark thetas, save r for each phase-space point
            if t == settings.theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + filename_addition + '.npy', this_r)
            elif t == settings.theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + filename_addition + '.npy', this_r)

            # Only evaluate certain combinations of thetas to save computation time
            if decide_toy_evaluation(settings.theta_observed, t):
                # Neyman construction: evaluate observed sample (raw)
                log_r_neyman_observed = regr.predict(X_neyman_observed_transformed)
                llr_neyman_observed = -2. * np.sum(log_r_neyman_observed.reshape((-1, settings.n_expected_events)),
                                                   axis=1)
                np.save(neyman_dir + '/neyman_llr_observed_' + algorithm + '_' + str(t) + filename_addition + '.npy',
                        llr_neyman_observed)

            # Neyman construction: loop over distribution samples generated from different thetas
            llr_neyman_distributions = []
            for tt in range(settings.n_thetas):

                # Only evaluate certain combinations of thetas to save computation time
                if not decide_toy_evaluation(tt, t):
                    placeholder = np.empty(settings.n_neyman_distribution_experiments)
                    placeholder[:] = np.nan
                    llr_neyman_distributions.append(placeholder)
                    continue

                # Neyman construction: load distribution sample
                X_neyman_distribution = np.load(
                    settings.unweighted_events_dir + '/X_neyman_distribution_' + str(tt) + '.npy')
                X_neyman_distribution_transformed = scaler.transform(
                    X_neyman_distribution.reshape((-1, X_neyman_distribution.shape[2])))

                # Neyman construction: evaluate distribution sample (raw)
                log_r_neyman_distribution = regr.predict(X_neyman_distribution_transformed)
                llr_neyman_distributions.append(
                    -2. * np.sum(log_r_neyman_distribution.reshape((-1, settings.n_expected_events)), axis=1))

            llr_neyman_distributions = np.asarray(llr_neyman_distributions)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_' + str(t) + filename_addition + '.npy',
                    llr_neyman_distributions)

        expected_llr = np.asarray(expected_llr)

        logging.info('Interpolation')

        interpolator = LinearNDInterpolator(settings.thetas[settings.pbp_training_thetas], expected_llr)
        expected_llr_all = interpolator(settings.thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[settings.pbp_training_thetas], expected_llr)
        # expected_llr_all = gp.predict(thetas)
        np.save(results_dir + '/llr_' + algorithm + filename_addition + '.npy', expected_llr_all)

    ################################################################################
    # Carl approaches
    ################################################################################

    else:

        expected_llr = []
        expected_llr_calibrated = []

        # Loop over the 15 thetas
        for i, t in enumerate(settings.pbp_training_thetas):

            logging.info('Starting theta %s/%s: number %s (%s)', i + 1, len(settings.pbp_training_thetas), t,
                         settings.thetas[t])

            # Load data
            X_train = np.load(
                settings.unweighted_events_dir + '/X_train_point_by_point_' + str(t) + input_filename_addition + '.npy')
            y_train = np.load(
                settings.unweighted_events_dir + '/y_train_point_by_point_' + str(t) + input_filename_addition + '.npy')

            # Scale data
            scaler = StandardScaler()
            scaler.fit(np.array(X_train, dtype=np.float64))
            X_train_transformed = scaler.transform(X_train)
            X_test_transformed = scaler.transform(X_test)
            X_calibration_transformed = scaler.transform(X_calibration)
            X_neyman_observed_transformed = scaler.transform(
                X_neyman_observed.reshape((-1, X_neyman_observed.shape[2])))

            clf = KerasRegressor(lambda: make_classifier(n_hidden_layers=n_hidden_layers, learn_log_r=learn_logr_mode),
                                 epochs=n_epochs, validation_split=settings.validation_split,
                                 verbose=2)

            # Training
            clf.fit(X_train_transformed, y_train,
                    callbacks=(
                    [EarlyStopping(verbose=1, patience=settings.early_stopping_patience)] if early_stopping else None))

            # carl wrapper
            ratio = ClassifierScoreRatio(clf, prefit=True)

            # Evaluation
            this_r, _ = ratio.predict(X_test_transformed)

            expected_llr.append(- 2. * settings.n_expected_events / n_events_test * np.sum(np.log(this_r)))

            if t == settings.theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + filename_addition + '.npy', this_r)
            elif t == settings.theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + filename_addition + '.npy', this_r)

            # Calibration
            n_calibration_each = X_calibration_transformed.shape[0]
            X_calibration_both = np.zeros((2 * n_calibration_each, X_calibration_transformed.shape[1]))
            X_calibration_both[:n_calibration_each] = X_calibration_transformed
            X_calibration_both[n_calibration_each:] = X_calibration_transformed
            y_calibration = np.zeros(2 * n_calibration_each)
            y_calibration[n_calibration_each:] = 1.
            w_calibration = np.zeros(2 * n_calibration_each)
            w_calibration[:n_calibration_each] = weights_calibration[t]
            w_calibration[n_calibration_each:] = weights_calibration[theta1]

            ratio_calibrated = ClassifierScoreRatio(
                # CalibratedClassifierScoreCV(clf, cv='prefit', bins=100, independent_binning=False)
                CalibratedClassifierScoreCV(clf, cv='prefit', method='isotonic')
            )
            ratio_calibrated.fit(X_calibration_both, y_calibration, sample_weight=w_calibration)

            # Evaluation of calibrated classifier
            this_r, _ = ratio_calibrated.predict(X_test_transformed)
            expected_llr_calibrated.append(- 2. * settings.n_expected_events / n_events_test * np.sum(np.log(this_r)))

            if t == settings.theta_benchmark_nottrained:
                np.save(results_dir + '/r_nottrained_' + algorithm + '_calibrated' + filename_addition + '.npy', this_r)

                # Save calibration histograms
                np.save(results_dir + '/calvalues_nottrained_' + algorithm + filename_addition + '.npy',
                        ratio_calibrated.classifier_.calibration_sample[:n_calibration_each])
                # np.save(results_dir + '/cal0histo_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.histogram_)
                # np.save(results_dir + '/cal0edges_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.edges_[0])
                # np.save(results_dir + '/cal1histo_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.histogram_)
                # np.save(results_dir + '/cal1edges_nottrained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.edges_[0])

            elif t == settings.theta_benchmark_trained:
                np.save(results_dir + '/r_trained_' + algorithm + '_calibrated' + filename_addition + '.npy', this_r)

                # Save calibration histograms
                np.save(results_dir + '/calvalues_trained_' + algorithm + filename_addition + '.npy',
                        ratio_calibrated.classifier_.calibration_sample[:n_calibration_each])
                # np.save(results_dir + '/cal0histo_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.histogram_)
                # np.save(results_dir + '/cal0edges_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator0.edges_[0])
                # np.save(results_dir + '/cal1histo_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.histogram_)
                # np.save(results_dir + '/cal1edges_trained_' + algorithm + filename_addition + '.npy', ratio_calibrated.classifier_.calibrators_[0].calibrator1.edges_[0])

            # Neyman construction
            # Only evaluate certain combinations of thetas to save computation time
            if decide_toy_evaluation(settings.theta_observed, t):
                # Neyman construction: evaluate observed sample (raw)
                r_neyman_observed, _ = ratio.predict(X_neyman_observed_transformed)
                llr_neyman_observed = -2. * np.sum(np.log(r_neyman_observed).reshape((-1, settings.n_expected_events)),
                                                   axis=1)
                np.save(neyman_dir + '/neyman_llr_observed_' + algorithm + '_' + str(t) + filename_addition + '.npy',
                        llr_neyman_observed)

                # Neyman construction: evaluate observed sample (calibrated)
                r_neyman_observed, _ = ratio_calibrated.predict(X_neyman_observed_transformed)
                llr_neyman_observed = -2. * np.sum(np.log(r_neyman_observed).reshape((-1, settings.n_expected_events)),
                                                   axis=1)
                np.save(
                    neyman_dir + '/neyman_llr_observed_' + algorithm + '_calibrated_' + str(
                        t) + filename_addition + '.npy',
                    llr_neyman_observed)

            # Neyman construction: loop over distribution samples generated from different thetas
            llr_neyman_distributions = []
            llr_neyman_distributions_calibrated = []
            for tt in range(settings.n_thetas):

                # Only evaluate certain combinations of thetas to save computation time
                if not decide_toy_evaluation(tt, t):
                    placeholder = np.empty(settings.n_neyman_distribution_experiments)
                    placeholder[:] = np.nan
                    llr_neyman_distributions.append(placeholder)
                    continue

                # Neyman construction: load distribution sample
                X_neyman_distribution = np.load(
                    settings.unweighted_events_dir + '/X_neyman_distribution_' + str(tt) + '.npy')
                X_neyman_distribution_transformed = scaler.transform(
                    X_neyman_distribution.reshape((-1, X_neyman_distribution.shape[2])))

                # Neyman construction: evaluate distribution sample (raw)
                r_neyman_distribution, _ = ratio.predict(X_neyman_distribution_transformed)
                llr_neyman_distributions.append(
                    -2. * np.sum(np.log(r_neyman_distribution).reshape((-1, settings.n_expected_events)), axis=1))

                # Neyman construction: evaluate distribution sample (calibrated)
                r_neyman_distribution, _ = ratio_calibrated.predict(X_neyman_distribution_transformed)
                llr_neyman_distributions_calibrated.append(
                    -2. * np.sum(np.log(r_neyman_distribution).reshape((-1, settings.n_expected_events)), axis=1))

            llr_neyman_distributions = np.asarray(llr_neyman_distributions)
            llr_neyman_distributions_calibrated = np.asarray(llr_neyman_distributions_calibrated)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_' + str(t) + filename_addition + '.npy',
                    llr_neyman_distributions)
            np.save(neyman_dir + '/neyman_llr_distribution_' + algorithm + '_calibrated_' + str(t)
                    + filename_addition + '.npy',
                    llr_neyman_distributions_calibrated)

        expected_llr = np.asarray(expected_llr)
        expected_llr_calibrated = np.asarray(expected_llr_calibrated)

        logging.info('Starting interpolation')

        interpolator = LinearNDInterpolator(settings.thetas[settings.pbp_training_thetas], expected_llr)
        expected_llr_all = interpolator(settings.thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[settings.pbp_training_thetas], expected_llr)
        # expected_llr_all = gp.predict(thetas)
        np.save(results_dir + '/llr_' + algorithm + filename_addition + '.npy', expected_llr_all)

        interpolator = LinearNDInterpolator(settings.thetas[settings.pbp_training_thetas], expected_llr_calibrated)
        expected_llr_calibrated_all = interpolator(settings.thetas)
        # gp = GaussianProcessRegressor(normalize_y=True,
        #                              kernel=C(1.0) * Matern(1.0, nu=0.5), n_restarts_optimizer=10)
        # gp.fit(thetas[settings.pbp_training_thetas], expected_llr_calibrated)
        # expected_llr_calibrated_all = gp.predict(thetas)
        np.save(results_dir + '/expected_llr_' + algorithm + '_calibrated' + filename_addition + '.npy',
                expected_llr_calibrated_all)
