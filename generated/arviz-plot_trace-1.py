import arviz as az
data = az.load_arviz_data('non_centered_eight')
coords = {'theta_t_dim_0': [0, 1], 'school':['Lawrenceville']}
az.plot_trace(data, var_names=('theta_t', 'theta'), coords=coords)
