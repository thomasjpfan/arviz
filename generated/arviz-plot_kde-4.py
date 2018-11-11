tau_posterior = np.concatenate(non_centered.posterior["tau"].values)
az.plot_kde(mu_posterior, values2=tau_posterior)
