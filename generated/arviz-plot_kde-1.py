import arviz as az
non_centered = az.load_arviz_data('non_centered_eight')
mu_posterior = np.concatenate(non_centered.posterior["mu"].values)
az.plot_kde(mu_posterior)
