import arviz as az
data = az.load_arviz_data('radon')
az.plot_ppc(data)
