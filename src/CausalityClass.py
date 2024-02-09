import numpy as np
from tigramite import data_processing as pp
from tigramite import plotting as tp
from tigramite.pcmci import PCMCI
from tigramite.independence_tests import ParCorr
from tigramite.models import LinearMediation
from matplotlib import pyplot as plt
from yaml import safe_load
import pandas as pd

class CausalityClass:
    """ CausalityClass

        This is the class that implements all functions needed to construct a causal graph from climate indices.
        It uses the PCMCI algorithm implemented in the Tigramite package.
    
    """

    ###############################################
    def __init__(self, D):
        """__init__ 

        Creates instances of the class and initilises their atributes.

        Parameters
        ----------
        var_names : list of strings
            A list of input indices names.
        """

        self.D = D
        self.var_names = list(D.keys())
        self.linear_mediator = None
        self.path = self.read_yaml_file()['path']
        self.tau_min = self.read_yaml_file()['tau_min']
        self.tau_max = self.read_yaml_file()['tau_max']
        self.alpha_level = self.read_yaml_file()['significance_level']
        self.save_path = self.read_yaml_file()['save_path']
        self.range_months = self.read_yaml_file()['range_months']
        self.boot_iter = int(self.read_yaml_file()['boot_iters'])

    ###############################################
    def read_yaml_file(self):
        """read_yaml_file 

        This function reads in the program configuration from yaml file.

        Returns
        -------
        A string of objects
            Returns a string of objects read fromt the yaml file.
        """
        with open('config.yml', 'r') as f:
            config = safe_load(f)
        return config
    
    ###############################################
    def generate_dataframe(self, D):
        """generate_dataframe 

        This function generates dataframes in the common format for TIGRAMITE.

        Parameters
        ----------
        D : dict
            A dictionary containing climate indices.

        Returns
        -------
        Dataframe
            Tigramite's dataframe custom type.
        numpy array
            A list of order indices names.
        """
      
        d_keys = list(D.keys())
        matched_indexes = np.intersect1d(self.var_names, d_keys)
        dataset = [D[k].variables[k].values for k in matched_indexes]

        indices = np.vstack(dataset).transpose()
        print('Input Indices:', indices.shape)

        dataframe = pp.DataFrame(indices, datatime = np.arange(len(indices)), var_names=matched_indexes)
        print('Dataframe size:', dataframe.values.shape)

        if self.boot_iter == 0: self.plot_time_series(dataframe)

        return dataframe, matched_indexes

    ###############################################
    def construct_causal_graph(self, dataframe):
        """run_causal_analysis

        This function runs a causal discovery algorithm - PCMCI algorithm implemented in Tigramite.
        It construct a causal graph from climate indices.

        Parameters
        ----------
        dataframe : Dataframe
             Tigramite's dataframe custom type.

        Returns
        -------
        dict
            A dictionary containing statistically significant causal parents of each actor (index).
        """

        parcorr = ParCorr(significance='analytic', mask_type=None)

        pcmci = PCMCI(dataframe=dataframe, cond_ind_test=parcorr, verbosity=0)

        pcmci.verbosity = 0
        
        results = pcmci.run_pcmci(tau_min=self.tau_min, tau_max=self.tau_max, pc_alpha=None)

        q_matrix = pcmci.get_corrected_pvalues(p_matrix=results['p_matrix'], fdr_method='fdr_bh')

        pcmci.print_significant_links(p_matrix = results['p_matrix'], q_matrix = q_matrix, val_matrix = results['val_matrix'], alpha_level = self.alpha_level)
        
        sig_parents = pcmci.return_significant_parents(pq_matrix=q_matrix, val_matrix=results['val_matrix'], alpha_level=self.alpha_level)

        return sig_parents
    
    ###############################################
    def linear_estimator(self, sig_parents, dataframe):
        """linear_estimator 

        This functions does causal inference on the causal graph.

        Parameters
        ----------
        sig_parents : _type_
            _description_
        dataframe : _type_
            _description_

        Returns
        -------
        _type_
            _description_
        """

        all_parents = sig_parents['parents']
        link_matrix = sig_parents['link_matrix']

        # Calculate beta coefficient
        self.linear_mediator = LinearMediation(dataframe=dataframe, mask_type = 'y', data_transform = None)
        self.linear_mediator.fit_model(all_parents = all_parents, tau_max=self.tau_max)  

        val_matrix = self.linear_mediator.get_val_matrix()
        #print('Beta coefficients:\n', self.linear_mediator.get_coefs())

        return val_matrix, link_matrix

    ###############################################
    def plot_cens_graph(self, val_matrix, link_matrix, save=False):
        """plot_cens_graph 

        This functions plots Causal Effect Network - a causal graph.

        Parameters
        ----------
        dataframe : _type_
            _description_
        var_names : _type_
            _description_
        path_name : str, optional
            _description_, by default ''
        save : bool, optional
            _description_, by default False
        """
        
        #sig_parents = self.construct_causal_graph(dataframe)
        #val_matrix, link_matrix = self.linear_estimator(sig_parents, dataframe)

        fig = plt.figure(figsize=(8, 6), frameon=False)
        ax = fig.add_subplot(111, frame_on=False)

        if save: 
            path_name = self.save_path + 'cen' + "_".join(self.var_names)

            tp.plot_graph(val_matrix=val_matrix,link_matrix=link_matrix, var_names=self.var_names, arrow_linewidth = 14, node_size = 0.4, 
                          node_label_size = 16, link_label_fontsize = 16, cmap_nodes = 'YlOrRd', figsize=(10,8), fig_ax=(fig,ax), curved_radius=0.2, 
                          node_aspect=0.99, vmin_edges=-1.0, vmax_edges=1.0, vmin_nodes=0.0, vmax_nodes=1.0, edge_ticks=0.50, node_ticks=0.2,
                          link_colorbar_label='Path coeff.', node_colorbar_label='Autocorr. path coeff.', label_fontsize=14, show_colorbar=True,
                          save_name=path_name)
    
    ###############################################
    def get_links_beta_coeffs(self):
        """get_links_beta_coeffs 

            This function returns beta coefficients for all causal links in CEN.
        """

        print('\n### Beta coefficients for:\n',)

        names = self.var_names
        n = int(len(names))
        for v, i in zip(names, range(n)): print(i,v)

        coeffs = self.linear_mediator.get_coefs()
        #print(coeffs)

        df = pd.DataFrame(coeffs)
        df.fillna(0, inplace=True)
        print(df)

        #med = self.linear_mediator
        #print("Link coefficient (HP, lag) --> U200: ", med.get_coeff(i=0, tau=1, j=2))
        
    ###############################################
    def plot_time_series(self, dataframe):
        """plot_time_series 

        This function plots all time series.

        Parameters
        ----------
        dataframe : Tigramite's custom datatype
            _description_
        path_name : str, optional
            Output path., by default ''
        """
        
        tp.plot_timeseries(
            dataframe,time_label='Monthly means', 
            figsize=(8,6), 
            skip_ticks_data_x = 2, 
            data_linewidth=1.0, 
            grey_masked_samples=True, 
            label_fontsize=16,
            save_name=self.save_path + 'timeseries_data_plot')
        
    ###############################################
    def generate_random_indices(self):
        """generate_random_indices _summary_

        _extended_summary_

        Returns
        -------
        _type_
            _description_
        """

        # Set for reproducibility of results
        np.random.seed(113)

        # Constant number of months
        n_mons = len(list(range(self.range_months[0], self.range_months[1] + 1)))

        # Number of samples in one time series
        d_keys = list(self.D.keys())
        k = d_keys[0]
        sample_size = list(range(0, self.D[k].variables[k].values.shape[0], n_mons))
        print('Sample size:',sample_size)

        # Number of iteration of random sampling
        n_iter = self.boot_iter

        # Randomly sample indices (years) to remove from dataframe
        # This function should generate indices that start every 12 samples (months)
        rnd_inds = np.random.choice(a=sample_size, size=n_iter, replace=True) 
        print('Selected samples/years:',rnd_inds)

        return rnd_inds

    ###############################################
    def bootrstapping(self):
        """bootrstapping 

        This function performs bootstrapping and measures average causal effect
        and average causal susceptibility metrics. It saves results of the bootstrapping
        to a npz file.
        """

        all_val_matrices = []
        all_ace = []
        all_acs = []

        rnd_inds = self.generate_random_indices()

        for i in rnd_inds:
            
            # Generate data frames in the common format for TIGRAMITE
            dataframe, _ = self.generate_dataframe(self.D)
                        
            # Range of one year
            n_mons = len(list(range(self.range_months[0], self.range_months[1] + 1)))
            rng = list(range(i,i + n_mons))
            print('Selected months:', rng)
            
            # Delete one year from the dataframe
            print('dataframe:', dataframe.values.shape)
            dataframe.values = np.delete(dataframe.values, rng, axis=0)
            print('New dataframe:', dataframe.values.shape)
            
            # Compute causal links
            sig_parents = self.construct_causal_graph(dataframe)
            val_matrix, _ = self.linear_estimator(sig_parents, dataframe)
 
            med = self.linear_mediator
            val_matrix = med.get_val_matrix()
            print('## Coefficient vals:\n', val_matrix)
            
            self.get_links_beta_coeffs()
            
            all_val_matrices.append(val_matrix)

            # ACE and ACS metrics
            all_ace.append(med.get_all_ace())
            all_acs.append(med.get_all_acs())
            print ("Average Causal Effect X=%.2f, Y=%.2f, Z=%.2f, Q=%.2f " % tuple(med.get_all_ace()))
            print ("Average Causal Susceptibility X=%.2f, Y=%.2f, Z=%.2f, Q=%.2f " % tuple(med.get_all_acs()))
            
        # Save to a file
        np.savez(self.path + 'bootstrap' + "_".join(self.var_names), indices=rnd_inds, coeffs=all_val_matrices, all_ace=all_ace, all_acs=all_acs)
        
