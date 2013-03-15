#
# sklearn_utils.py
# Contains custom classes and wrappers for the scikit-learn package.
#
# Copyright (C) 2012, 2013 Tadej Janez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Tadej Janez <tadej.janez@fri.uni-lj.si>
#

import numpy as np
import numpy.ma as ma
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import _num_samples, warn_if_not_float

def check_arrays_without_finite_check(*arrays, **options):
    """Checked that all arrays have consistent first dimensions

    Parameters
    ----------
    *arrays : sequence of arrays or scipy.sparse matrices with same shape[0]
        Python lists or tuples occurring in arrays are converted to 1D numpy
        arrays.

    sparse_format : 'csr', 'csc' or 'dense', None by default
        If not None, any scipy.sparse matrix is converted to
        Compressed Sparse Rows or Compressed Sparse Columns representations.
        If 'dense', an error is raised when a sparse array is
        passed.

    copy : boolean, False by default
        If copy is True, ensure that returned arrays are copies of the original
        (if not already converted to another format earlier in the process).

    check_ccontiguous : boolean, False by default
        Check that the arrays are C contiguous

    dtype : a numpy dtype instance, None by default
        Enforce a specific dtype.
        
        
    Note
    ----
    This function is identical to the sklearn.utils.validation.check_arrays()
    function except that it does not check that all elements are finite.
    
    """
    sparse_format = options.pop('sparse_format', None)
    if sparse_format not in (None, 'csr', 'csc', 'dense'):
        raise ValueError('Unexpected sparse format: %r' % sparse_format)
    copy = options.pop('copy', False)
    check_ccontiguous = options.pop('check_ccontiguous', False)
    dtype = options.pop('dtype', None)
    if options:
        raise TypeError("Unexpected keyword arguments: %r" % options.keys())

    if len(arrays) == 0:
        return None

    n_samples = _num_samples(arrays[0])

    checked_arrays = []
    for array in arrays:
        array_orig = array
        if array is None:
            # special case: ignore optional y=None kwarg pattern
            checked_arrays.append(array)
            continue
        size = _num_samples(array)

        if size != n_samples:
            raise ValueError("Found array with dim %d. Expected %d" % (
                size, n_samples))

        if sparse.issparse(array):
            if sparse_format == 'csr':
                array = array.tocsr()
            elif sparse_format == 'csc':
                array = array.tocsc()
            elif sparse_format == 'dense':
                raise TypeError('A sparse matrix was passed, but dense data '
                    'is required. Use X.todense() to convert to dense.')
            if check_ccontiguous:
                array.data = np.ascontiguousarray(array.data, dtype=dtype)
            else:
                array.data = np.asarray(array.data, dtype=dtype)
        else:
            if check_ccontiguous:
                array = np.ascontiguousarray(array, dtype=dtype)
            else:
                array = np.asarray(array, dtype=dtype)

        if copy and array is array_orig:
            array = array.copy()
        checked_arrays.append(array)

    return checked_arrays

class MeanImputer(BaseEstimator, TransformerMixin):
    """Impute the missing values of (chosen) features with the mean values.
    
    This estimator computes the mean of each (chosen) column and imputes the
    missing values in the column with the computed mean.
    
    Parameters
    ----------
    copy : boolean, optional, default is True
        Set to False to perform inplace column imputation and avoid a copy (if
        the input is already a numpy array).
    
    feat_indices : list, optional, default is None
        A list of column (feature) indices for which the imputation should be
        performed. If None, the imputation is done for all columns (features).
    
    Attributes
    ----------
    feat_indices_ : list
        Indices of features for which the imputation should be performed.
    mean_ : ndarray, shape (n_features,)
        Means of features (only for features in feat_indices_; otherwise zeros).
    
    """
    
    def __init__(self, copy=True, feat_indices=None):
        self.copy = copy
        self.feat_indices = feat_indices
    
    def fit(self, X, y=None):
        """Compute the means of (chosen) columns (features) that will be used
        later for imputation.

        Parameters
        ----------
        X : array-like, shape [n_samples, n_features]
            The data used to compute the means of columns (features) that will
            be used later for imputation of missing values.
        """
        X = check_arrays_without_finite_check(X, sparse_format="dense",
                                              copy=self.copy)[0]
        missing = np.isnan(X)
        if missing.any():
            X_m = ma.masked_array(X, mask=missing)
            self.mean_ = X_m.mean(axis=0)
            if self.mean_.mask.any():
                raise ValueError("Means of some columns could not be computed"
                                 "meaning it will not be possible to impute all"
                                 "missing values")
            else:
                # convert self.mean_ from a MaskedArray to a regular numpy.array
                self.mean_ = self.mean_.data
        else:
            self.mean_ = X.mean(axis=0)
        self.feat_indices_ = (self.feat_indices if self.feat_indices else
                              range(X.shape[1]))
        return self
    
    def fit_old(self, X, y=None):
        """OLDER (AND SLOWER) VERSION of the fit() method."""
        X = check_arrays_without_finite_check(X, sparse_format="dense",
                                              copy=self.copy)[0]
        self.feat_indices_ = (self.feat_indices if self.feat_indices else
                              range(X.shape[1]))
        if sum([1 for i in self.feat_indices_ if i < 0 or i >= X.shape[1]]) > 0:
            raise ValueError("Feature indices should be in range: [0, "
                             "# features).")
        self.mean_ = np.zeros(X.shape[1])
        for j in self.feat_indices_:
            missing = np.isnan(X[:, j])
            if missing.any():
                Xj_m = ma.masked_array(X[:, j], mask=missing)
                self.mean_[j] = Xj_m.mean()
            else:
                self.mean_[j] = X[:, j].mean()
        return self
    
    def transform(self, X):
        """Impute the missing values of features with indices in feat_indices_
        with the means in mean_
        
        Parameters
        ----------
        X : array-like with shape [n_samples, n_features]
            Input data that will be transformed.
        """
        X = check_arrays_without_finite_check(X, sparse_format="dense",
                                              copy=self.copy)[0]
        # convert the input array to 2D if it is 1D
        if len(X.shape) == 1:
            X = np.array([X])
        # convert the self.feat_indices_ list to a boolean array with the same
        # shape as X
        feat_indices_mask = np.zeros(X.shape, dtype="bool")
        feat_indices_mask[:, self.feat_indices_] = True
        # create the imputation mask (a value has to be NaN and it must be
        # selected for imputation by the feat_indices_mask)
        imputation_mask = np.isnan(X) & feat_indices_mask
        # clone the self.mean_ vector as many times as there are rows in X
        repeated_means = np.tile(self.mean_, (len(X), 1))
        # perform the imputation
        X[imputation_mask] = repeated_means[imputation_mask]
        return X
    
    def transform_old(self, X):
        """OLDER (AND SLOWER) VERSION of the transform() method."""
        X = check_arrays_without_finite_check(X, sparse_format="dense",
                                              copy=self.copy)[0]
        # convert the input array to 2D if it is 1D
        if len(X.shape) == 1:
            X = np.array([X])
        # impute the missing values
        for j in self.feat_indices_:
            missing = np.isnan(X[:, j])
            if missing.any():
                Xj_m = ma.masked_array(X[:, j], missing)
                X[:, j] = ma.filled(Xj_m, fill_value=self.mean_[j])
        return X

from sklearn import dummy

def change_dummy_classes(estimator, new_classes):
    """Change the classes of the given DummyClassifier to the given new values.
    Leave the prediction properties of the estimator the same.
    
    Arguments:
    estimator -- sklearn.dummy.DummyClassifier
    new_classes -- numpy.array representing the new class values
    
    """
    if not isinstance(estimator, dummy.DummyClassifier):
        raise ValueError("The given estimator should be a DummyClassifier.")
    old_classes = estimator.classes_
    old_class_prior = estimator.class_prior_
    new_class_prior = np.zeros(new_classes.shape)
    for c in old_classes:
        if c not in new_classes:
            raise ValueError("The old class value {} is not included among "
                             "the new class values: {}".format(c, new_classes))
        old_idx = np.where(old_classes == c)
        new_idx = np.where(new_classes == c)
        new_class_prior[new_idx] = old_class_prior[old_idx]
    estimator.classes_ = new_classes
    estimator.n_classes_ = len(new_classes)
    estimator.class_prior_ = new_class_prior

if __name__ == "__main__":
    X = np.array([[180., 8.],
                  [np.NaN, 10.],
                  [170., 5.],
                  [190., np.NaN]])
    y = np.array([0., 1., 0., 1.])
    
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    
    clf = Pipeline([("imputer", MeanImputer()),
                    ("log_reg", LogisticRegression())])
    clf.fit(X, y)
    
    print "Imputation means: ", clf.named_steps["imputer"].mean_
    print "Log reg coef: ", clf.named_steps["log_reg"].coef_
    
    test = np.array([[200, 5]])
    print clf.predict(test)
