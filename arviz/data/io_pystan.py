"""PyStan-specific conversion code."""
from collections import OrderedDict
from copy import deepcopy
from operator import itemgetter
import re

import numpy as np
import xarray as xr

from .inference_data import InferenceData
from .base import requires, dict_to_dataset, generate_dims_coords, make_attrs


class PyStanConverter:
    """Encapsulate PyStan specific logic."""

    def __init__(
        self,
        *_,
        posterior=None,
        posterior_predictive=None,
        prior=None,
        prior_predictive=None,
        observed_data=None,
        log_likelihood=None,
        coords=None,
        dims=None
    ):
        self.posterior = posterior
        self.posterior_predictive = posterior_predictive
        self.prior = prior
        self.prior_predictive = prior_predictive
        self.observed_data = observed_data
        self.log_likelihood = log_likelihood
        self.coords = coords
        self.dims = dims
        import pystan

        self.pystan = pystan

    @requires("posterior")
    def posterior_to_xarray(self):
        """Extract posterior samples from fit."""
        posterior = self.posterior
        # filter posterior_predictive and log_likelihood
        posterior_predictive = self.posterior_predictive
        if posterior_predictive is None:
            posterior_predictive = []
        elif isinstance(posterior_predictive, str):
            posterior_predictive = [posterior_predictive]
        log_likelihood = self.log_likelihood
        if not isinstance(log_likelihood, str):
            log_likelihood = []
        else:
            log_likelihood = [log_likelihood]

        ignore = posterior_predictive + log_likelihood + ["lp__"]

        data = get_draws(posterior, ignore=ignore)

        return dict_to_dataset(data, library=self.pystan, coords=self.coords, dims=self.dims)

    @requires("posterior")
    def sample_stats_to_xarray(self):
        """Extract sample_stats from posterior."""
        posterior = self.posterior
        dtypes = {"divergent__": bool, "n_leapfrog__": np.int64, "treedepth__": np.int64}

        ndraws = [s - w for s, w in zip(posterior.sim["n_save"], posterior.sim["warmup2"])]

        extraction = {}
        for pyholder, ndraws in zip(posterior.sim["samples"], ndraws):
            sampler_dict = dict(zip(pyholder["sampler_param_names"], pyholder["sampler_params"]))
            for key, values in sampler_dict.items():
                if key not in extraction:
                    extraction[key] = []
                extraction[key].append(values)

        data = OrderedDict()
        for key, values in extraction.items():
            values = np.stack(values, axis=0)
            dtype = dtypes.get(key)
            values = values.astype(dtype)
            name = re.sub("__$", "", key)
            name = "diverging" if name == "divergent" else name
            data[name] = values

        # copy dims and coords
        dims = deepcopy(self.dims) if self.dims is not None else {}
        coords = deepcopy(self.coords) if self.coords is not None else {}

        # log_likelihood
        log_likelihood = self.log_likelihood
        if log_likelihood is not None:
            log_likelihood_data = get_draws(posterior, variables=log_likelihood)
            data["log_likelihood"] = log_likelihood_data[log_likelihood]
            if isinstance(log_likelihood, str) and log_likelihood in dims:
                dims["log_likelihood"] = dims.pop(log_likelihood)
            if isinstance(log_likelihood, str) and log_likelihood in coords:
                coords["log_likelihood"] = coords.pop(log_likelihood)

        # lp__
        stat_lp = get_draws(posterior, variables="lp__")
        data["lp"] = stat_lp["lp__"]

        return dict_to_dataset(data, library=self.pystan, coords=coords, dims=dims)

    @requires("posterior")
    @requires("posterior_predictive")
    def posterior_predictive_to_xarray(self):
        """Convert posterior_predictive samples to xarray."""
        posterior = self.posterior
        posterior_predictive = self.posterior_predictive
        data = get_draws(posterior, variables=posterior_predictive)
        return dict_to_dataset(data, library=self.pystan, coords=self.coords, dims=self.dims)

    @requires("prior")
    def prior_to_xarray(self):
        """Convert prior samples to xarray."""
        prior = self.prior
        # filter posterior_predictive and log_likelihood
        prior_predictive = self.prior_predictive
        if prior_predictive is None:
            prior_predictive = []
        elif isinstance(prior_predictive, str):
            prior_predictive = [prior_predictive]

        ignore = prior_predictive + ["lp__"]

        data = get_draws(prior, ignore=ignore)
        return dict_to_dataset(data, library=self.pystan, coords=self.coords, dims=self.dims)

    @requires("prior")
    def sample_stats_prior_to_xarray(self):
        """Extract sample_stats_prior from prior."""
        prior = self.prior
        dtypes = {"divergent__": bool, "n_leapfrog__": np.int64, "treedepth__": np.int64}

        ndraws = [s - w for s, w in zip(prior.sim["n_save"], prior.sim["warmup2"])]

        extraction = {}
        for pyholder, ndraws in zip(prior.sim["samples"], ndraws):
            sampler_dict = dict(zip(pyholder["sampler_param_names"], pyholder["sampler_params"]))
            for key, values in sampler_dict.items():
                if key not in extraction:
                    extraction[key] = []
                extraction[key].append(values)

        data = OrderedDict()
        for key, values in extraction.items():
            values = np.stack(values, axis=0)
            dtype = dtypes.get(key)
            values = values.astype(dtype)
            name = re.sub("__$", "", key)
            name = "diverging" if name == "divergent" else name
            data[name] = values

        # lp__
        stat_lp = get_draws(prior, variables="lp__")
        data["lp"] = stat_lp["lp__"]

        return dict_to_dataset(data, library=self.pystan, coords=self.coords, dims=self.dims)

    @requires("prior")
    @requires("prior_predictive")
    def prior_predictive_to_xarray(self):
        """Convert prior_predictive samples to xarray."""
        prior = self.prior
        prior_predictive = self.prior_predictive
        data = get_draws(prior, variables=prior_predictive)
        return dict_to_dataset(data, library=self.pystan, coords=self.coords, dims=self.dims)

    @requires("posterior")
    @requires("observed_data")
    def observed_data_to_xarray(self):
        """Convert observed data to xarray."""
        posterior = self.posterior
        if self.dims is None:
            dims = {}
        else:
            dims = self.dims
        observed_names = self.observed_data
        if isinstance(observed_names, str):
            observed_names = [observed_names]
        observed_data = OrderedDict()
        for key in observed_names:
            vals = np.atleast_1d(posterior.data[key])
            val_dims = dims.get(key)
            val_dims, coords = generate_dims_coords(
                vals.shape, key, dims=val_dims, coords=self.coords
            )
            observed_data[key] = xr.DataArray(vals, dims=val_dims, coords=coords)
        return xr.Dataset(data_vars=observed_data, attrs=make_attrs(library=self.pystan))

    def to_inference_data(self):
        """Convert all available data to an InferenceData object.

        Note that if groups can not be created (i.e., there is no `fit`, so
        the `posterior` and `sample_stats` can not be extracted), then the InferenceData
        will not have those groups.
        """
        return InferenceData(
            **{
                "posterior": self.posterior_to_xarray(),
                "sample_stats": self.sample_stats_to_xarray(),
                "posterior_predictive": self.posterior_predictive_to_xarray(),
                "prior": self.prior_to_xarray(),
                "sample_stats_prior": self.sample_stats_prior_to_xarray(),
                "prior_predictive": self.prior_predictive_to_xarray(),
                "observed_data": self.observed_data_to_xarray(),
            }
        )


def get_draws(fit, variables=None, ignore=None):
    """Extract draws from PyStan fit."""
    if ignore is None:
        ignore = []
    if fit.mode == 1:
        msg = "Model in mode 'test_grad'. Sampling is not conducted."
        raise AttributeError(msg)
    elif fit.mode == 2 or fit.sim.get("samples") is None:
        msg = "Fit doesn't contain samples."
        raise AttributeError(msg)

    dtypes = infer_dtypes(fit)

    if variables is None:
        variables = fit.sim["pars_oi"]
    elif isinstance(variables, str):
        variables = [variables]
    variables = list(variables)

    for var, dim in zip(fit.sim["pars_oi"], fit.sim["dims_oi"]):
        if var in variables and np.prod(dim) == 0:
            del variables[variables.index(var)]

    ndraws = [s - w for s, w in zip(fit.sim["n_save"], fit.sim["warmup2"])]

    var_keys = OrderedDict()
    for key in fit.sim["fnames_oi"]:
        var, *_ = key.split("[")
        if var not in var_keys:
            var_keys[var] = []
        var_keys[var].append(key)

    shapes = dict(zip(fit.sim["pars_oi"], fit.sim["dims_oi"]))

    variables = [var for var in variables if var not in ignore]

    data = OrderedDict()

    for var in variables:
        keys = var_keys.get(var, [var])
        var_draws = []
        shape = shapes.get(var, [])
        dtype = dtypes.get(var)
        for pyholder, ndraw in zip(fit.sim["samples"], ndraws):
            ary = itemgetter(*keys)(pyholder.chains)
            if shape:
                ary = np.column_stack(ary)
            ary = ary[-ndraw:]
            ary = ary.reshape((-1, *shape), order="F")
            var_draws.append(ary)
        ary = np.stack(var_draws, axis=0)
        ary = ary.astype(dtype)
        data[var] = ary

    return data


def infer_dtypes(fit):
    """Infer dtypes from Stan model code.

    Function strips out generated quantities block and searchs for `int`
    dtypes after stripping out comments inside the block.
    """
    pattern_remove_comments = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE
    )
    stan_integer = r"int"
    stan_limits = r"(?:\<[^\>]+\>)*"  # ignore group: 0 or more <....>
    stan_param = r"([^;=\s\[]+)"  # capture group: ends= ";", "=", "[" or whitespace
    stan_ws = r"\s*"  # 0 or more whitespace
    pattern_int = re.compile(
        "".join((stan_integer, stan_ws, stan_limits, stan_ws, stan_param)), re.IGNORECASE
    )
    stan_code = fit.get_stancode()
    # remove deprecated comments
    stan_code = "\n".join(
        line if "#" not in line else line[: line.find("#")] for line in stan_code.splitlines()
    )
    stan_code = re.sub(pattern_remove_comments, "", stan_code)
    stan_code = stan_code.split("generated quantities")[-1]
    dtypes = re.findall(pattern_int, stan_code)
    dtypes = {item.strip(): "int" for item in dtypes if item.strip() in fit.model_pars}
    return dtypes


def from_pystan(
    *,
    posterior=None,
    posterior_predictive=None,
    prior=None,
    prior_predictive=None,
    observed_data=None,
    log_likelihood=None,
    coords=None,
    dims=None
):
    """Convert PyStan data into an InferenceData object.

    Parameters
    ----------
    posterior : StanFit4Model
        PyStan fit object for posterior.
    posterior_predictive : str, a list of str
        Posterior predictive samples for the posterior.
    prior : StanFit4Model
        PyStan fit object for prior.
    prior_predictive : str, a list of str
        Posterior predictive samples for the prior.
    observed_data : str or a list of str
        observed data used in the sampling.
        Observed data is extracted from the `posterior.data`.
    log_likelihood : str
        Pointwise log_likelihood for the data.
        log_likelihood is extracted from the posterior.
    coords : dict[str, iterable]
        A dictionary containing the values that are used as index. The key
        is the name of the dimension, the values are the index values.
    dims : dict[str, List(str)]
        A mapping from variables to a list of coordinate names for the variable.

    Returns
    -------
    InferenceData object
    """
    return PyStanConverter(
        posterior=posterior,
        posterior_predictive=posterior_predictive,
        prior=prior,
        prior_predictive=prior_predictive,
        observed_data=observed_data,
        log_likelihood=log_likelihood,
        coords=coords,
        dims=dims,
    ).to_inference_data()
