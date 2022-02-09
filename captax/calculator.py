import copy
import numpy as np
import pandas as pd
from captax.constants import *


class Calculator():
    """Define the object used to calculate and store detailed results.

    Attributes
    ----------
    env : Environment object
        Economic environment parameters.
    wgt : Weights object
        Weights used in calculations.
    pol : Policy object
        Policy parameters.
    rate_of_return : dict
        Nominal and real rates of return on equity and debt.
    econ_depreciation : np.ndarray
        Economic depreciation rates.
    biz_inc_tax_rate_adjustments : dict
        Income tax rate adjustments for businesses (C corps and pass-throughs).
    biz_tax_rates_adjusted : dict
        Adjusted tax rates applied to net income, deductions, and credits of businesses
        (C corps and pass-throughs).
    seca_tax_rates_adjusted : dict
        Adjusted SECA tax rates applied to net income and deductions of pass-throughs.
    req_after_tax_returns_investors : np.ndarray
        Required after-tax rates of return to investors.
    req_after_tax_returns_savers : np.ndarray
        Required after-tax rates of return to savers.
    rates_of_return_adjusted : dict
        Nominal and real rates of return by year, with an adjustment to returns on debt investments
        if the tax-uniformity perspective is selected.
    real_discount_rates : np.ndarray
        Real discount rates.
    CCR_shields : np.ndarray
        Capital cost recovery shields.
    req_before_tax_returns : np.ndarray
        Required before-tax rates of return.

    """

    def __init__(self, env, wgt, pol):
        """Initialize Calculator object.

        Parameters
        ----------
        env : Environment object
            Economic environment parameters.
        wgt : Weights object
            Weights used in calculations.
        pol : Policy object
            Policy parameters.

        Returns
        -------
        None
            Method initializes attributes of Calculator object.

        """
        self.env = env
        self.wgt = wgt
        self.pol = pol
        self.rate_of_return = None
        self.econ_depreciation = None
        self.biz_inc_tax_rate_adjustments = None
        self.biz_tax_rates_adjusted = None
        self.seca_tax_rates_adjusted = None
        self.req_after_tax_returns_investors = None
        self.req_after_tax_returns_savers = None
        self.rates_of_return_adjusted = None
        self.real_discount_rates = None
        self.CCR_shields = None
        self.req_before_tax_returns = None

        return None


    def calc_all(self):
        """Run all calculations for required before- and after-tax rates of return
        used in the calculations of effective marginal tax rates (EMTRs).

        This method includes the first level of hierarchy of methods in the
        Calculator class:
            * self._calc_preliminary_parameters() : Runs preliminary calculations on environment parameters.
            * self._calc_tax_rates_adjusted() : Calculates adjustments to tax rates applied to businesses'
                net income and adjusted tax rates applied to businesses' net income, deductions and credits.
            * self._cal_req_after_tax_returns_investors() : Calculates the required (real) after-tax rate of
                return to investors, which enters the calculation of the C corps effective marginal tax rate
                on investment.
            * self._calc_req_after_tax_returns_savers() : Calculates required after-tax rates of return to savers.
            * self._calc_rates_of_return_adjusted() : Calculates rates of return on equity and debt (by year)
                and applies adjustments to the rates of return on debt if tax uniformity method is used.
            * self._calc_real_discount_rates() : Calculates real discount rates.
            * self._calc_CCR_shields() : Calculates capital cost recovery (CCR) shields, which account for
                tax shields from depreciation deductions and from the investment tax credit.
            * self._calc_req_before_tax_returns() : Calculate required before-tax rates of return.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        None
            This method nests other methods.

        """
        print('\nBegin running detailed calculations')

        self._calc_preliminary_parameters()
        print('* Preliminary calculations on environment parameters completed')

        self._calc_tax_rates_adjusted()
        print('* Calculations of adjusted tax rates completed')

        self.req_after_tax_returns_investors = (
            self._calc_req_after_tax_returns_investors(self.rate_of_return['real'])
        )
        print('* Required after-tax rates of return to investors calculated')

        self.req_after_tax_returns_savers = self._calc_req_after_tax_returns_savers()
        print('* Required after-tax rates of return to savers calculated')

        self.rates_of_return_adjusted = (
            self._calc_rates_of_return_adjusted(self.rate_of_return,
                                                self.req_after_tax_returns_savers,
                                                self.env.inflation_rate)
        )
        print('* Adjusted rates of return calculated')

        if self.pol.perspective == "uniformity":
            self.req_after_tax_returns_savers[:NUM_INDS,
                                              :NUM_ASSETS,
                                              :NUM_FOR_PROFIT_LEGAL_FORMS,
                                              FINANCING_SOURCES['debt'],
                                              ACCOUNT_CATEGORIES['typical'],
                                              :NUM_YEARS] = (
                                                  self.req_after_tax_returns_savers[:NUM_INDS,
                                                                                    :NUM_ASSETS,
                                                                                    :NUM_FOR_PROFIT_LEGAL_FORMS,
                                                                                    FINANCING_SOURCES['typical_equity'],
                                                                                    ACCOUNT_CATEGORIES['typical'],
                                                                                    :NUM_YEARS]
            )
            print('* Required after-tax rates of return to savers equalized')

        self.real_discount_rates = self._calc_real_discount_rates()
        print('* Real discount rates calculated')

        self.CCR_shields = self._calc_CCR_shields()
        print('* Capital cost recovery shields calculated')

        self.req_before_tax_returns = self._calc_req_before_tax_returns()
        print('* Required before-tax rates of return calculated')

        print('Finished running detailed calculations\n')

        return None


    def _calc_preliminary_parameters(self):
        """Run preliminary calculations on environment parameters.

        This method is called in self.calc_all() and calls two other methods:
            * self._combine_rates_of_return()
            * self._combine_detailed_industry()

        The first method combines nominal and real rates of return on equity and
        debt investments into a dictionary, and adjusts nominal rates of retun on debt
        investments if the tax-uniformity perspective is used.

        The second method combines the array of economic depreciation rates by
        detailed industry into an array of economic depreciation rates by industry.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        None
            This method nests other methods.

        """
        self.rate_of_return = (
            self._combine_rates_of_return(self.env.rate_of_return['nominal']['equity'],
                                          self.env.rate_of_return['nominal']['debt'],
                                          self.env.inflation_rate,
                                          self.wgt.weights)
        )

        self.econ_depreciation = (
            self._combine_detailed_industry(self.env.econ_depreciation_detailed_industry,
                                            self.wgt.detailed_industry_weights)
        )

        return None


    def _calc_tax_rates_adjusted(self):
        """Calculate adjustments to tax rates applied to businesses' net income and adjusted
        tax rates applied to businesses' net income, deductions and credits.

        This method is called in self.calc_all() and calls three other methods:
            * self._calc_biz_inc_tax_rate_adjustments()
            * self._calc_biz_tax_rates_adjusted()
            * self._calc_seca_tax_rates_adjusted()

        The first method computes adjustments to tax rates applied to net income of
        businesses (C corps and pass-throughs).

        The second method computes adjusted tax rates applied to net income, deductions
        and credits of businesses (C corps and pass-throughs) by combining the tax rate
        adjustments computed in the first method with timing adjustment parameters
        for net income, deductions and credits.

        The third method computes adjusted tax rates applied to pass-through income taxed
        by the Self-Employed Contributions Act (SECA) tax.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        None
            This method nests other methods.

        """
        self.biz_inc_tax_rate_adjustments = (
            self._calc_biz_inc_tax_rate_adjustments(self.pol.tax_rate_adjustments,
                                                    self.pol.deduction['pass_thru_inc_share_below_thresholds'])
        )

        self.biz_tax_rates_adjusted = (
            self._calc_biz_tax_rates_adjusted(self.pol.tax_rates['c_corp'],
                                              self.pol.tax_rates['pass_thru'],
                                              self.pol.itc['rates'],
                                              self.pol.biz_timing_adjustments,
                                              self.biz_inc_tax_rate_adjustments,
                                              self.wgt.detailed_industry_weights)
        )

        self.seca_tax_rates_adjusted = (
            self._calc_seca_tax_rates_adjusted(self.pol.tax_rates['seca'],
                                               self.pol.biz_timing_adjustments['seca'])
        )

        return None


    def _calc_req_after_tax_returns_investors(self, real_rate_of_return):
        """Calculate the required (real) after-tax rate of return to investors, which
        enters the calculation of the C corps effective marginal tax rate on investment.

        This method is called in self.calc_all().

        Parameters
        ----------
        real_rate_of_return : dict
            Real rates of return on equity and debt.

        Returns
        -------
        req_after_tax_returns_investors : np.ndarray
            Array of after-tax rates of return on equity and debt investments
            required by investors, which varies by:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        req_after_tax_returns_investors = np.zeros((NUM_INDS,
                                                    NUM_ASSETS,
                                                    NUM_FOR_PROFIT_LEGAL_FORMS,
                                                    NUM_FINANCING_SOURCES,
                                                    NUM_YEARS))

        req_after_tax_returns_investors[:] = np.nan

        # Fill array with relevant values
        for financing_source in ['new_equity','retained_earnings','typical_equity']:
            req_after_tax_returns_investors[:NUM_INDS,
                                            :NUM_ASSETS,
                                            LEGAL_FORMS['c_corp'],
                                            FINANCING_SOURCES[financing_source],
                                            :NUM_YEARS] = real_rate_of_return['equity']

        req_after_tax_returns_investors[:NUM_INDS,
                                        :NUM_ASSETS,
                                        LEGAL_FORMS['c_corp'],
                                        FINANCING_SOURCES['debt'],
                                        :NUM_YEARS] = real_rate_of_return['debt']

        return req_after_tax_returns_investors


    def _calc_req_after_tax_returns_savers(self):
        """Calculate required after-tax rates of return to savers.

        This menthod is called in self.calc_all() and calls five other methods:
            * self._calc_req_after_tax_returns_savers_cap_gains()
            * self._calc_req_after_tax_returns_savers_dividends()
            * self._calc_req_after_tax_returns_savers_all_equity()
            * self._calc_req_after_tax_returns_savers_debt()
            * self._fill_req_after_tax_returns_savers_array()

        The first two methods calculate the after-tax rates of return required by savers on
        capital gains and dividends.

        The third method uses the outcomes of the first two methods and calculates the
        after-tax rates of return required by savers on equity investments held in all account
        categories.

        The fourth method calculates the after-tax rates of return required by savers on
        debt investments.

        The fifth method combines the after tax-rates of return on equity and debt investments
        calculated in the third and fourth methods.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        req_after_tax_returns_savers : np.ndarray
            Array of after-tax rates of return required by savers, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 LEN_ACCOUNT_CATEGORIES,
                 NUM_YEARS]

        """
        req_after_tax_returns_savers_cap_gains = (
            self._calc_req_after_tax_returns_savers_cap_gains(
                self.env.cap_gains_share_held,
                self.env.cap_gains_holding_period,
                self.pol.cap_gains_share_held_changes,
                self.pol.holding_period_changes['cap_gains'],
                self.pol.tax_rates['cap_gains'],
                self.rate_of_return['real']['equity'],
                self.env.inflation_rate
            )
        )

        req_after_tax_returns_savers_dividends = (
            self._calc_req_after_tax_returns_savers_dividends(
                self.rate_of_return['real']['equity'],
                self.pol.tax_rates['dividend_inc']
            )
        )

        req_after_tax_returns_savers_all_equity = (
            self._calc_req_after_tax_returns_savers_all_equity(
                self.pol.account_category_shares['c_corp']['equity'],
                self.pol.account_category_shares['pass_thru']['equity'],
                self.pol.account_category_shares['ooh']['equity'],
                self.env.ret_plan_holding_period,
                self.pol.holding_period_changes['ret_plan'],
                self.pol.tax_rates['ret_plan'],
                self.rate_of_return['real']['equity'],
                req_after_tax_returns_savers_cap_gains,
                req_after_tax_returns_savers_dividends,
                self.env.inflation_rate,
                self.env.shares['c_corp_equity']
            )
        )

        req_after_tax_returns_savers_debt = (
            self._calc_req_after_tax_returns_savers_debt(
                self.pol.account_category_shares['c_corp']['debt'],
                self.pol.account_category_shares['pass_thru']['debt'],
                self.pol.account_category_shares['ooh']['debt'],
                self.env.ret_plan_holding_period,
                self.pol.holding_period_changes['ret_plan'],
                self.pol.tax_rates['ret_plan'],
                self.pol.tax_rates['interest_inc'],
                self.rate_of_return['nominal']['debt'],
                self.env.inflation_rate
            )
        )

        req_after_tax_returns_savers = (
            self._fill_req_after_tax_returns_savers_array(
                req_after_tax_returns_savers_all_equity,
                req_after_tax_returns_savers_debt
            )
        )

        return req_after_tax_returns_savers


    def _calc_rates_of_return_adjusted(self,
                                       rate_of_return,
                                       req_after_tax_returns_savers,
                                       inflation_rate):
        """Calculate rates of return on equity and debt (by year) and apply adjustments to the
        rates of return on debt if tax uniformity method is used.

        This menthod is called in self.calc_all().

        Parameters
        ----------
        rate_of_return : dict
            Rates of return on equity and debt.
        req_after_tax_returns_savers : np.ndarray
            After-tax rates of return required by savers.
        inflation_rate : np.float64
            Inflation rate.

        Returns
        -------
        rates_of_return_adjusted : dict
            Dictionary with four arrays of rates of return, each of which varies by year.

        Note
        ----------
        After-tax returns required by savers don't vary by industry and asset type, so any value
        of those two dimensions can be selected when computing adjustments to nominal rates of return
        on debt by year. In the code below, dimensions NUM_INDS-1 and NUM_ASSETS-1 are selected.

        """
        if self.pol.perspective == "comprehensive":

            rates_of_return_adjusted = {
                'nominal' : {
                    'equity' : self._expand_array(rate_of_return['nominal']['equity'], NUM_YEARS),
                    'debt' : self._expand_array(rate_of_return['nominal']['debt'], NUM_YEARS)
                },
                'real' : {
                    'equity' : self._expand_array(rate_of_return['real']['equity'], NUM_YEARS),
                    'debt' : self._expand_array(rate_of_return['real']['debt'], NUM_YEARS)
                }
            }

        elif self.pol.perspective == "uniformity":

            # Adjustments to nominal rates of return on debt
            rates_of_return_adjustments = (
                (req_after_tax_returns_savers[NUM_INDS-1,
                                              NUM_ASSETS-1,
                                              LEGAL_FORMS['c_corp'],
                                              FINANCING_SOURCES['debt'],
                                              ACCOUNT_CATEGORIES['typical'],
                                              :NUM_YEARS]
                 + inflation_rate)
                / (req_after_tax_returns_savers[NUM_INDS-1,
                                                NUM_ASSETS-1,
                                                LEGAL_FORMS['c_corp'],
                                                FINANCING_SOURCES['typical_equity'],
                                                ACCOUNT_CATEGORIES['typical'],
                                                :NUM_YEARS]
                   + inflation_rate)
            )

            # Adjusted rates of return
            rates_of_return_adjusted = {
                'nominal' : {
                    'equity' : self._expand_array(rate_of_return['nominal']['equity'], NUM_YEARS),
                    'debt' : (rate_of_return['nominal']['debt'] / rates_of_return_adjustments)
                },
                'real' : {
                    'equity' : self._expand_array(rate_of_return['real']['equity'], NUM_YEARS),
                    'debt' : (rate_of_return['nominal']['debt'] / rates_of_return_adjustments) - inflation_rate
                }
            }

        return rates_of_return_adjusted


    def _calc_real_discount_rates(self):
        """Calculate real discount rates.

        This is called in self.calc_all() method and calls two other methods:
            * self._calc_NID_flows()
            * self._fill_real_discount_rates()

        The first method calculates the flows of net interest deductions (NIDs), which vary by
        year and depend on the nominal return to debt investments, the share of interest deductible,
        and the marginal tax rates that apply to those deductions.

        The second method fills an array with real discount rates, which account for the flows
        of NIDs.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        real_discount_rates : np.ndarray
            Array of real discount rates, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        NID_flows = (
            self._calc_NID_flows(self.biz_tax_rates_adjusted['c_corp']['deductions'],
                                 self.biz_tax_rates_adjusted['pass_thru']['deductions'],
                                 self.pol.deduction['interest_deductible_shares'],
                                 self.seca_tax_rates_adjusted['deductions'],
                                 self.pol.deduction['mortg_interest_deduction'],
                                 self.rates_of_return_adjusted['nominal']['debt'])
        )

        real_discount_rates = (
            self._fill_real_discount_rates(self.req_after_tax_returns_savers,
                                           self.rates_of_return_adjusted['real'],
                                           NID_flows)
        )

        return real_discount_rates


    def _calc_CCR_shields(self):
        """Calculate capital cost recovery (CCR) shields, which account for tax shields from
        depreciation deductions and from the investment tax credit.

        This method is called in self.calc_all and calls four other methods:
            * self._calc_nominal_discount_rates()
            * self._calc_expens_shares()
            * self._calc_depreciation_deduction_PVs()
            * self._calc_capital_cost_recovery_shields()

        The first method computed nominal discount rates used in the calculation of capital cost
        recovery shields.

        The second method combines information on Section 179 expensing and other expensing by detailed
        industry, asset type and legal form into an array of expensing shares, which is used in the
        calculation of present values (PVs) of depreciation deductions.

        The third method calculates the PDV of depreciation deductions by industry, asset type, legal
        form, financing source and year.

        The fourth method uses PDVs of depreciation deductions, investment tax credits, and tax rates
        that apply to businesses' (C corps and pass-throughs) net income and owner-occupied housing's
        imputed rent to calculate tax shields from capital cost recovery.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        CCR_shields : np.ndarray
            Array of capital cost recovery shields, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        nominal_discount_rates = (
            self._calc_nominal_discount_rates(self.wgt.detailed_industry_weights,
                                              self.req_after_tax_returns_savers,
                                              self.pol.tax_rates['c_corp'],
                                              self.pol.tax_rates['pass_thru'],
                                              self.biz_inc_tax_rate_adjustments,
                                              self.pol.deduction['interest_deductible_shares'],
                                              self.pol.deduction['mortg_interest_deduction'],
                                              self.rates_of_return_adjusted['nominal'],
                                              self.env.inflation_rate)
        )

        expens_shares = (
            self._calc_expens_shares(self.pol.depreciation['c_corp_sec_179_expens_shares'],
                                     self.pol.depreciation['pass_thru_sec_179_expens_shares'],
                                     self.pol.depreciation['other_expens_shares'])
        )

        depreciation_deduction_PVs = (
            self._calc_depreciation_deduction_PVs(self.pol.depreciation['straight_line_flags'],
                                                  self.pol.depreciation['recovery_periods'],
                                                  self.pol.depreciation['acceleration_rates'],
                                                  self.env.econ_depreciation_detailed_industry,
                                                  self.env.inflation_rate,
                                                  self.pol.depreciation['inflation_adjustments'],
                                                  expens_shares,
                                                  nominal_discount_rates,
                                                  self.wgt.detailed_industry_weights)
        )

        CCR_shields = (
            self._calc_capital_cost_recovery_shields(self.pol.itc,
                                                     self.biz_tax_rates_adjusted['c_corp']['deductions'],
                                                     self.biz_tax_rates_adjusted['pass_thru']['deductions'],
                                                     self.biz_tax_rates_adjusted['c_corp']['credits'],
                                                     self.biz_tax_rates_adjusted['pass_thru']['credits'],
                                                     self.seca_tax_rates_adjusted['deductions'],
                                                     self.pol.tax_rates['ooh'],
                                                     depreciation_deduction_PVs)
        )

        return CCR_shields


    def _calc_req_before_tax_returns(self):
        """Calculate required before-tax rates of return.

        This menthod is called in self.calc_all() and calls three other methods:
            * self._calc_proportional_PV_gross_profits_after_tax_rates()
            * self._calc_req_before_tax_returns_biz_inventories()
            * self._req_before_tax_returns()

        The first method calculates the proportional present value (PV) of after-tax gross profits,
        which is a component of the the required before-tax rates of return.

        The second method calculates the required before-tax rates of return on inventories for businesses
        (C corps and pass-throughs).

        The third method calculates the required before-tax rates of return by industry, asset type, legal
        form, financing source and year and includes the required before-tax rates of return on
        business inventories.

        Parameters
        ----------
        None
            Parameters are specified in the methods nested within this method.

        Returns
        -------
        req_before_tax_returns : np.ndarray
            Array of required before-tax rates of return, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        proportional_PV_gross_profits_after_tax_rates = (
            self._calc_proportional_PV_gross_profits_after_tax_rates(self.econ_depreciation,
                                                                     self.biz_tax_rates_adjusted['c_corp']['net_inc'],
                                                                     self.biz_tax_rates_adjusted['pass_thru']['net_inc'],
                                                                     self.seca_tax_rates_adjusted['net_inc'],
                                                                     self.pol.tax_rates['ooh'],
                                                                     self.env.avg_local_prop_tax_rate,
                                                                     self.pol.deduction['prop_tax_deduction'],
                                                                     self.real_discount_rates)
        )

        req_before_tax_returns_biz_inventories = (
            self._calc_req_before_tax_returns_biz_inventories(self.wgt.detailed_industry_weights,
                                                              self.env.inventories_holding_period,
                                                              self.pol.holding_period_changes['inventories'],
                                                              self.biz_tax_rates_adjusted,
                                                              self.env.inflation_rate,
                                                              self.pol.depreciation['inflation_adjustments'],
                                                              self.real_discount_rates)
        )

        req_before_tax_returns = (
            self._calc_req_before_tax_returns_all(self.econ_depreciation,
                                                  self.CCR_shields,
                                                  proportional_PV_gross_profits_after_tax_rates,
                                                  self.pol.tax_rates['ooh'],
                                                  req_before_tax_returns_biz_inventories)
        )

        return req_before_tax_returns


    def _calc_req_after_tax_returns_savers_deferred_assets(self,
                                                           real_rate_of_return,
                                                           inflation_rate,
                                                           holding_periods,
                                                           tax_rates):
        """Calculates after-tax rate of return required by savers on assets held in deferred form.

        Parameters
        ----------
        real_rate_of_return : np.float64
            Real annual rate of return.
        inflation_rate : np.float64
          Inflation rate.
        holding_periods : np.ndarray
          Holding periods of deferred assets.
        tax_rates : np.ndarray
          Tax rates applied to deferred assets.

        Returns
        -------
        req_after_tax_returns_savers_deferred_assets : np.ndarray
            After-tax rate of return required by savers on deferred assets, by year.

        """
        # Nominal cumulative before-tax rate of return
        nominal_cumulative_before_tax_returns = list((real_rate_of_return + inflation_rate)
                                                      * holding_periods)

        # Nominal cumulative after-tax rates of return
        nominal_cumulative_after_tax_returns = list(np.log((1.0 - tax_rates)
                                                           * np.exp(nominal_cumulative_before_tax_returns)
                                                           + tax_rates))

        # Real after-tax rates of return
        req_after_tax_returns_savers_deferred_assets = (nominal_cumulative_after_tax_returns / holding_periods
                                                        - inflation_rate)

        return req_after_tax_returns_savers_deferred_assets


    def _combine_detailed_industry(self, detailed_industry_var, detailed_industry_weights):
        """Combine array with first dimension at the detailed-industry level
        to array with first dimension at the industry level using detailed
        industry weights.

        Parameters
        ----------
        detailed_industry_var : np.ndarray
            Array with first dimension at the detailed-industry level.
        detailed_industry_weights : np.ndarray
            Detailed industry weights.

        Returns
        -------
        industry_var : np.ndarray
            Array with the first dimensions at the industry level.

        """
        # Initialize list where industry averages are stored
        industry_var = list()
        detailed_industry = 0

        # Calculate industry averages
        for industry in range(NUM_INDS):
            cumulative_industry_weight = 0.0
            industry_average = np.zeros(detailed_industry_var[industry].shape)

            while cumulative_industry_weight < 1.0:
                industry_average = (
                    industry_average
                        + (detailed_industry_var[detailed_industry]
                        * detailed_industry_weights[detailed_industry])
                )
                cumulative_industry_weight += detailed_industry_weights[detailed_industry]
                detailed_industry += 1

            industry_var.append(industry_average)

        # Convert back to numpy array
        industry_var = np.asarray(industry_var)

        return industry_var


    def _expand_industry(self, industry_var, detailed_industry_weights):
        """Expand array with first dimension at the industry level to array
        with first dimension at the detailed-industry level using detailed
        industry weights.

        Parameters
        ----------
        industry_var : np.ndarray
            Array with first dimension at the industry level.
        detailed_industry_weights : np.ndarray
            Detailed industry weights.

        Returns
        -------
        detailed_industry_var : np.ndarray
            Detailed industry level array.

        """
        # Initialize list where detailed industry values are stored
        detailed_industry_var = list()
        detailed_industry = 0

        # Calculate detailed industry values
        for industry in range(NUM_INDS):
            cumulative_industry_weight = 0.0

            while cumulative_industry_weight < 1:
                detailed_industry_var.append(industry_var[industry])
                cumulative_industry_weight += detailed_industry_weights[detailed_industry]
                detailed_industry += 1

        # Convert back to numpy array
        detailed_industry_var = np.asarray(detailed_industry_var)

        return detailed_industry_var


    def _expand_array(self, in_array, dim1, dim2=None, dim3=None, dim4=None):
        """Expand arrays for different dimensional requirements. The method allows to expand
        the input array up to four dimensions, which are specified as parameters of the method.

        Example
        ----------
        In order to expand the input array along the industry and asset type dimensions, type:
            expanded_array = self._expand_array(in_array, NUM_INDS, NUM_ASSETS)

        Parameters
        ----------
        in_array : np.ndarray
            Array to be expanded.
        dim1 : float
            First dimension to be expanded.
        dim2 : float
            Second dimension to be expanded.
        dim3 : float
            Third dimension to be expanded.
        dim4 : float
            Fourth dimension to be expanded.

        Returns
        -------
        out_array : np.ndarray
            Expanded array with added dimensions specified in dim1, dim2, dim3 and dim4.

        """
        # Initialize list of dimensions along which to expand the input array
        dims_to_expand = list()

        for dim in (dim1, dim2, dim3, dim4):
            if dim is not None:
                dims_to_expand.append(dim)

        # Append 1s for each dim in input_array, which sets up the np.tile statement
        # to expand the selected dimensions, above
        if in_array.ndim > 0:
            for _ in range(in_array.ndim):
                dims_to_expand.append(1)

        # Expand array
        expanded_array = np.tile(in_array, tuple(dims_to_expand))

        return expanded_array


    def _combine_rates_of_return(self,
                                 nominal_rate_of_return_equity,
                                 nominal_rate_of_return_debt,
                                 inflation_rate,
                                 weights):
        """Combine information on nominal and real rates of return into a dictionary after
         equalizing rates of return on equity and debt investments using a weighted average
         of the two if the tax uniformity perspective is considered.

        Parameters
        ----------
        nominal_rate_of_return_equity : np.float64
            Nominal rate of return on equity.
        nominal_rate_of_return_debt : np.float64
            Nominal rate of return on debt.
        inflation_rate : np.float64
            Inflation rate.
        weights : np.array
            Weights.

        Returns
        -------
        rates_of_return : dict
            Rates of return on equity and debt.

        """
        # Adjust rates of return if tax-uniformity method is used
        if self.pol.perspective == "uniformity":

            # Weights used in calculation of weighted rate of return
            agg_weights_biz_equity = (
                weights[:NUM_BIZ_INDS, ALL_EQUIP_STRUCT_IPP_INVENT, :NUM_BIZ, FINANCING_SOURCES['typical_equity']].sum(axis=(0, 1, 2))
            )
            agg_weights_biz_debt = (
                weights[:NUM_BIZ_INDS, ALL_EQUIP_STRUCT_IPP_INVENT, :NUM_BIZ, FINANCING_SOURCES['debt']].sum(axis=(0, 1, 2))
            )
            agg_weights_biz = (
                weights[:NUM_BIZ_INDS, ALL_EQUIP_STRUCT_IPP_INVENT, :NUM_BIZ, FINANCING_SOURCES['typical (biz)']].sum(axis=(0, 1, 2))
            )

            # Weighted nominal rate of return
            nominal_rate_of_return_equity = (
                nominal_rate_of_return_equity * (agg_weights_biz_equity / agg_weights_biz)
                + nominal_rate_of_return_debt * (agg_weights_biz_debt / agg_weights_biz)
            )

            nominal_rate_of_return_debt = nominal_rate_of_return_equity

        # Combine rates of return into a dictionary
        rates_of_return = {
            'nominal' : {
                'equity' : nominal_rate_of_return_equity,
                'debt' : nominal_rate_of_return_debt
            },
            'real' : {
                'equity' : nominal_rate_of_return_equity - inflation_rate,
                'debt' : nominal_rate_of_return_debt - inflation_rate
            }
        }

        return rates_of_return


    def _calc_biz_inc_tax_rate_adjustments(self,
                                           tax_rate_adjustments,
                                           pass_thru_inc_share_below_thresholds):
        """Calculates income tax rate adjustments for businesses (C corps and pass-throughs).

        Calculation of tax rate adjustments combines adjustments by asset type and by industry.
        Industry-specific adjustments include Section 199A adjustments and other industry
        adjustments for pass-throughs and account for the share of pass-through income below
        specified income thresholds.

        Parameters
        ----------
        tax_rate_adjustments : dict
            Tax rate adjustments by industry and asset type for businesses (C corps and pass-throughs).
        pass_thru_inc_share_below_thresholds : np.array
            Share of pass-through income below income threshold for calculation of Section 199A
            deduction adjustments.

        Returns
        -------
        biz_inc_tax_rate_adjustments : dict
            Dictionary with two arrays of income tax rate adjustments for businesses (C corps and
            pass-throughs), each with dimensions:
                [NUM_DETAILED_INDS,
                 NUM_ASSETS,
                 NUM_YEARS]

        """
        # Initialize dictionaries
        adjustment_types = {}
        adjustments = {}

        # Read in parameters for tax rate adjustments calculations
        #---------------------------------------------------------------------------------
        for legal_form in ['c_corp','pass_thru']:
            adjustment_types[legal_form] = {}
            for adjustment_type in ['asset_type','sec_199A','industry']:
                adjustment_types[legal_form][adjustment_type] = {}
                for adjustment_component in ['eligibility','rate']:

                    # Asset-specific adjustments
                    if adjustment_type == 'asset_type':
                        adjustment_types[legal_form][adjustment_type][adjustment_component] = (
                            self._expand_array(tax_rate_adjustments[legal_form][adjustment_type]
                                                    [:NUM_DETAILED_INDS,
                                                     TAX_RATE_ADJUSTMENTS_COMPONENTS[adjustment_component],
                                                     :NUM_YEARS],
                                                     NUM_DETAILED_INDS)
                        )

                    # Section 199A adjustments (only for pass-throughs)
                    elif adjustment_type == 'sec_199A' and legal_form == 'pass_thru':
                        adjustment_types[legal_form][adjustment_type][adjustment_component] = (
                                self._expand_array(tax_rate_adjustments[legal_form][adjustment_type]
                                                    [:NUM_DETAILED_INDS,
                                                     TAX_RATE_ADJUSTMENTS_COMPONENTS[adjustment_component],
                                                     :NUM_YEARS],
                                                     NUM_ASSETS).transpose((1, 0, 2))
                        )
                    # Other industry-specific adjustments
                    elif adjustment_type == 'industry':
                        adjustment_types[legal_form][adjustment_type][adjustment_component] = (
                                self._expand_array(tax_rate_adjustments[legal_form][adjustment_type]
                                                    [:NUM_DETAILED_INDS,
                                                     TAX_RATE_ADJUSTMENTS_COMPONENTS[adjustment_component],
                                                     :NUM_YEARS],
                                                     NUM_ASSETS).transpose((1, 0, 2))
                    )

        # Share of pass-through income below income threshold for calculation of section 199A deduction
        pass_thru_inc_share_below_thresholds = self._expand_array(pass_thru_inc_share_below_thresholds,
                                                                  NUM_DETAILED_INDS,
                                                                  NUM_ASSETS)

        # Calculate asset type- and industry-specific adjustments by form of organization (C corps and pass-throughs)
        #---------------------------------------------------------------------------------
        for legal_form in ['c_corp','pass_thru']:
            adjustments[legal_form] = {}
            for adjustment_type in ['asset_type','industry']:

                # Adjustments to C corp tax rates and asset-type specific adjustments to pass-through tax rates
                if legal_form == 'c_corp' or (legal_form == 'pass_thru' and adjustment_type == 'asset_type'):
                    adjustments[legal_form][adjustment_type] = (
                        1 - adjustment_types[legal_form][adjustment_type]['eligibility']
                        * adjustment_types[legal_form][adjustment_type]['rate']
                    )

                # Industry-specific adjustments to pass-through tax rates
                elif (legal_form == 'pass_thru' and adjustment_type == 'industry'):
                    adjustments[legal_form][adjustment_type] = (
                        (1 - adjustment_types[legal_form][adjustment_type]['eligibility']
                         * adjustment_types[legal_form][adjustment_type]['rate'])
                        * (1 - pass_thru_inc_share_below_thresholds
                           * adjustment_types[legal_form]['sec_199A']['rate']
                           - (1 - pass_thru_inc_share_below_thresholds)
                           * adjustment_types[legal_form]['sec_199A']['eligibility']
                           * adjustment_types[legal_form]['sec_199A']['rate'])
        )

        # Store tax rate adjustments in dictionary
        #---------------------------------------------------------------------------------
        biz_inc_tax_rate_adjustments = {
            'c_corp' : adjustments['c_corp']['asset_type'] * adjustments['c_corp']['industry'],
            'pass_thru' : adjustments['pass_thru']['asset_type'] * adjustments['pass_thru']['industry']
        }

        return biz_inc_tax_rate_adjustments


    def _calc_biz_tax_rates_adjusted(self,
                                     c_corp_tax_rates,
                                     pass_thru_tax_rates,
                                     itc_rates,
                                     biz_timing_adjustments,
                                     biz_inc_tax_rate_adjustments,
                                     detailed_industry_weights):
        """Compute adjusted tax rates applied to businesses' (C corps and pass-throughs)
        net income, deductions, and credits when accounting for timing adjustment parameters
        and businesses' income tax rates adjustments.

        Parameters
        ----------
        c_corp_tax_rates : np.ndarray
            Marginal tax rates on C corp income.
        pass_thru_tax_rates : np.ndarray
            Marginal tax rates on pass-through income.
        itc_rates : np.ndarray
            Investment tax credit rates.
        biz_timing_adjustments : dict
            Timing adjustment parameters applied to tax rates on net income, deductions and credits.
        biz_inc_tax_rate_adjustments : dict
            Adjustments to businesses' income tax rates.
        detailed_industry_weights : np.ndarray
            Detailed industry weights.

        Returns
        -------
        biz_tax_rates_adjusted : dict
            Dictionary with six arrays of adjusted tax rates, each with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize dictionaries
        tax_rates = {}
        inc_tax_rate_adjustments_comb = {}
        inc_tax_rate_adjustments = {}
        timing_adjustments = {}
        tax_rate_adjustments = {}

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Tax rate parameters
        tax_rates['c_corp'] = self._expand_array(c_corp_tax_rates, NUM_INDS, NUM_ASSETS, NUM_FINANCING_SOURCES)
        tax_rates['pass_thru'] = self._expand_array(pass_thru_tax_rates, NUM_INDS, NUM_ASSETS, NUM_FINANCING_SOURCES)
        itc_rates = self._expand_array(itc_rates, NUM_FINANCING_SOURCES).transpose((1, 2, 0, 3))

        # Other parameters
        for legal_form in ['c_corp','pass_thru']:

            # Income tax rate adjustments
            inc_tax_rate_adjustments_comb[legal_form]  = (
                self._combine_detailed_industry(biz_inc_tax_rate_adjustments[legal_form],
                                               detailed_industry_weights)
            )
            inc_tax_rate_adjustments[legal_form] = (
                self._expand_array(inc_tax_rate_adjustments_comb[legal_form],
                                  NUM_FINANCING_SOURCES).transpose((1, 2, 0, 3))
            )

            # Timing adjustment parameters
            timing_adjustments[legal_form] = {}
            for timing_adjustment in ['net_inc','deductions','credits']:
                timing_adjustments[legal_form][timing_adjustment] = (
                    self._expand_array(biz_timing_adjustments[legal_form][timing_adjustment],
                                      NUM_INDS, NUM_ASSETS, NUM_FINANCING_SOURCES)
                )

        # Calculate adjustments to net income, deductions and credits
        #---------------------------------------------------------------------------------
        for legal_form in ['c_corp','pass_thru']:
            tax_rate_adjustments[legal_form] = {}
            for timing_adjustment in ['net_inc','deductions','credits']:

                # Adjustments to tax rates applied to net income and deductions
                if timing_adjustment in ['net_inc','deductions']:
                    tax_rate_adjustments[legal_form][timing_adjustment] = (
                        inc_tax_rate_adjustments[legal_form]
                        * timing_adjustments[legal_form][timing_adjustment]
                    )

                # Adjustments to tax rates applied to credits
                elif timing_adjustment == 'credits':
                    tax_rate_adjustments[legal_form][timing_adjustment] = (
                        timing_adjustments[legal_form][timing_adjustment]
                    )

        # Store adjusted tax rates for businesses in dictionary
        #---------------------------------------------------------------------------------
        biz_tax_rates_adjusted = {
            'c_corp' : {
                'net_inc' : tax_rates['c_corp'] * tax_rate_adjustments['c_corp']['net_inc'],
                'deductions' : tax_rates['c_corp'] * tax_rate_adjustments['c_corp']['deductions'],
                'credits' : itc_rates * tax_rate_adjustments['c_corp']['credits']
            },
            'pass_thru' : {
                'net_inc' : tax_rates['pass_thru'] * tax_rate_adjustments['pass_thru']['net_inc'],
                'deductions' : tax_rates['pass_thru'] * tax_rate_adjustments['pass_thru']['deductions'],
                'credits' : itc_rates * tax_rate_adjustments['pass_thru']['credits']
            }
        }

        return biz_tax_rates_adjusted


    def _calc_seca_tax_rates_adjusted(self,
                                      seca_tax_rates,
                                      seca_timing_adjustments):
        """Compute adjusted Self-Employed Contributions Act (SECA) tax rates applied
        to pass-through net income and deductions.

        Parameters
        ----------
        seca_tax_rates : np.ndarray
            SECA tax rates.
        seca_timing_adjustments : np.ndarray
            SECA timing adjustments.

        Returns
        -------
        seca_tax_rates_adjusted : dict
            Dictionary with two arrays of adjusted tax rates, each with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Expand SECA parameters
        #---------------------------------------------------------------------------------
        seca_tax_rates = self._expand_array(seca_tax_rates,
                                            NUM_INDS, NUM_ASSETS, NUM_FINANCING_SOURCES)

        for timing_adjustment in ['net_inc','deductions']:
            seca_timing_adjustments[timing_adjustment] = (
                self._expand_array(seca_timing_adjustments[timing_adjustment],
                                   NUM_INDS, NUM_ASSETS, NUM_FINANCING_SOURCES)
            )

        # Store adjusted SECA tax rates in dictionary
        #---------------------------------------------------------------------------------
        seca_tax_rates_adjusted = {
            'net_inc' : seca_tax_rates * seca_timing_adjustments['net_inc'],
            'deductions' : seca_tax_rates * seca_timing_adjustments['deductions']
        }

        return seca_tax_rates_adjusted


    def _calc_req_after_tax_returns_savers_cap_gains(self,
                                                    cap_gains_share_held,
                                                    cap_gains_holding_period,
                                                    cap_gains_share_held_changes,
                                                    cap_gains_holding_period_changes,
                                                    cap_gains_tax_rates,
                                                    real_rate_of_return_equity,
                                                    inflation_rate):
        """Calculate the after-tax returns required by savers on capital gains.

        Parameters
        ----------
        cap_gains_share_held : dict
            Parameters distributing capital gains by duration class.
        cap_gains_holding_period : dict
            Parameters defining capital gain holding periods by duration class.
        cap_gains_share_held_changes : dict
            Changes to baseline values of capital gains parameters by duration class.
        cap_gains_holding_period_changes : dict
            Changes to baseline values of capital gains holding periods by duration class.
        cap_gains_tax_rates : dict
            Marginal tax rates on capital gains by duration class.
        real_rate_of_return_equity : np.float64
            Real rate of return on equity.
        inflation_rate : np.float64
            Inflation rate.

        Returns
        -------
        req_after_tax_returns_savers_cap_gains : dict
            Dictionary with three arrays of after-tax rates of return on capital gains
            (short-term, long-term and at-death), each varying by year.

        """
        # Adjustments for recategorizing capital gains from long-term to short-term and from at death to long-term
        adj_cap_gains_shares_held = {}
        for cap_gains_type in ['short_term', 'at_death']:
            adj_cap_gains_shares_held[cap_gains_type] = (
                (cap_gains_share_held[cap_gains_type] + cap_gains_share_held_changes[cap_gains_type])
                / (1.0 - (cap_gains_share_held[cap_gains_type] + cap_gains_share_held_changes[cap_gains_type]))
            )

        # Weights on discounted values of capital gains
        wgts_short_term = (
            adj_cap_gains_shares_held['short_term']
            / (1.0 + adj_cap_gains_shares_held['short_term'] + adj_cap_gains_shares_held['at_death'])
        )
        wgts_at_death = (
            adj_cap_gains_shares_held['at_death']
            / (1.0 + adj_cap_gains_shares_held['short_term'] + adj_cap_gains_shares_held['at_death'])
        )
        wgts_long_term = 1.0 - wgts_short_term - wgts_at_death

        # Discounted value of types of capital gains
        req_after_tax_returns_savers_cap_gains = {}
        for cap_gains_type in ['short_term', 'long_term', 'at_death']:
            req_after_tax_returns_savers_cap_gains[cap_gains_type] = (
                self._calc_req_after_tax_returns_savers_deferred_assets(real_rate_of_return_equity,
                                                                        inflation_rate,
                                                                        cap_gains_holding_period[cap_gains_type]
                                                                        + cap_gains_holding_period_changes[cap_gains_type],
                                                                        cap_gains_tax_rates[cap_gains_type])
           )

        # Required after-tax return on capital gains
        req_after_tax_returns_savers_cap_gains = (
                (req_after_tax_returns_savers_cap_gains['short_term'] * wgts_short_term
                + req_after_tax_returns_savers_cap_gains['long_term'] * wgts_long_term
                + req_after_tax_returns_savers_cap_gains['at_death'] * wgts_at_death)
        )

        return req_after_tax_returns_savers_cap_gains


    def _calc_req_after_tax_returns_savers_dividends(self,
                                                     real_rate_of_return_equity,
                                                     dividend_inc_tax_rates):
        """Calculate the after tax rate of return required by savers on dividends.

        Parameters
        ----------
        real_rate_of_return_equity : np.float64
            Real rate of return on equity.
        dividend_inc_tax_rates : np.ndarray
            Tax rates on dividends.

        Returns
        -------
        req_after_tax_returns_savers_dividends : np.ndarray
            After-tax rates of return on dividends, by year.

        """
        req_after_tax_returns_savers_dividends = real_rate_of_return_equity * (1.0 - dividend_inc_tax_rates)

        return req_after_tax_returns_savers_dividends


    def _calc_req_after_tax_returns_savers_all_equity(self,
                                                      c_corp_equity_account_category_shares,
                                                      pass_thru_equity_account_category_shares,
                                                      ooh_equity_account_category_shares,
                                                      ret_plan_holding_period,
                                                      ret_plan_holding_period_changes,
                                                      ret_plan_tax_rates,
                                                      real_rate_of_return_equity,
                                                      req_after_tax_returns_savers_cap_gains,
                                                      req_after_tax_returns_savers_dividends,
                                                      inflation_rate,
                                                      c_corp_equity_shares):
        """Calculate the after-tax rates of return required by savers on equity investments.

        Parameters
        ----------
        c_corp_equity_account_category_shares : dict
            Parameters defining accont categories for C corp equity investments.
        pass_thru_equity_account_category_shares : dict
            Parameters defining account categories for pass-through equity investments.
        ooh_equity_account_category_shares : dict
            Parameters defining account categories for owner-occupied housing equity investments.
        ret_plan_holding_period : dict
            Parameters defining holding periods of assets held in retirement plans.
        ret_plan_holding_period_changes : dict
            Changes to baseline values of holding periods in retirement plans.
        ret_plan_tax_rates : dict
            Tax rates on assets held in retirement plans.
        real_rate_of_return_equity : np.float64
            Real rate of return on equity.
        req_after_tax_returns_savers_cap_gains : np.ndarray
            Real rates of return on capital gains.
        req_after_tax_returns_savers_dividends : np.ndarray
            Real rates of return on dividends.
        inflation_rate : np.float64
            Inflation rate.
        c_corp_equity_shares : dict
            C Corp equity financing shares (new equity and retained earnings).

        Returns
        -------
        req_after_tax_returns_savers_all_equity : dict
            Dictionary with thirty-six arrays (three legals forms times three sources of equity
            financing times four account categories) of real after-tax rates of return required
            by savers on equity investments, by year.

        Note
        ----------
        Account categories for pass-throughs and owner-occupied housing are specified as
        parameters but are not currently used because after-tax returns on equity are
        equalized across forms of organizations as a non-arbitrage condition.

        """
        # Initialize dictionary
        req_after_tax_returns_savers_all_equity = {}
        req_after_tax_returns_savers_all_equity['c_corp'] = {}
        req_after_tax_returns_savers_all_equity['pass_thru'] = {}
        req_after_tax_returns_savers_all_equity['ooh'] = {}

        # C corps
        #---------------------------------------------------------------------------------
        # New equity and retained earnings
        for financing_source in ['new_equity', 'retained_earnings']:
            req_after_tax_returns_savers_all_equity['c_corp'][financing_source] = {}
            for account_category in ACCOUNT_CATEGORIES:

                # Taxable accounts for new equity
                if financing_source == 'new_equity' and account_category == 'taxable':
                    req_after_tax_returns_savers_all_equity['c_corp'][financing_source][account_category] = (
                        req_after_tax_returns_savers_dividends
                    )

                # Taxable accounts for retained earnings
                elif financing_source == 'retained_earnings' and account_category == 'taxable':
                    req_after_tax_returns_savers_all_equity['c_corp'][financing_source][account_category] = (
                        req_after_tax_returns_savers_cap_gains
                    )

                # Tax deferred and non-taxable accounts
                elif account_category in ['deferred', 'nontaxable']:
                    req_after_tax_returns_savers_all_equity['c_corp'][financing_source][account_category] = (
                        self._calc_req_after_tax_returns_savers_deferred_assets(real_rate_of_return_equity,
                                                                                inflation_rate,
                                                                                ret_plan_holding_period[account_category]
                                                                                + ret_plan_holding_period_changes[account_category],
                                                                                ret_plan_tax_rates[account_category])
                )

                # Typical accounts
                elif account_category == 'typical':
                    req_after_tax_returns_savers_all_equity['c_corp'][financing_source][account_category] = (
                        (req_after_tax_returns_savers_all_equity['c_corp'][financing_source]['taxable']
                        * c_corp_equity_account_category_shares['taxable'])
                        + (req_after_tax_returns_savers_all_equity['c_corp'][financing_source]['deferred']
                        * c_corp_equity_account_category_shares['deferred'])
                        + (req_after_tax_returns_savers_all_equity['c_corp'][financing_source]['nontaxable']
                        * c_corp_equity_account_category_shares['nontaxable'])
            )

        # Typical equity mix
        req_after_tax_returns_savers_all_equity['c_corp']['typical_equity'] = {}
        for account_category in ACCOUNT_CATEGORIES:
            req_after_tax_returns_savers_all_equity['c_corp']['typical_equity'][account_category] = (
                req_after_tax_returns_savers_all_equity['c_corp']['new_equity'][account_category]
                * c_corp_equity_shares['new_equity']
                + req_after_tax_returns_savers_all_equity['c_corp']['retained_earnings'][account_category]
                * c_corp_equity_shares['retained_earnings']
            )

        # Pass-throughs and owner-occupied housing
        #---------------------------------------------------------------------------------
        for legal_form in ['pass_thru','ooh']:
            for financing_source in ['new_equity','retained_earnings','typical_equity']:

                # New equity and retained earnings
                if financing_source in ['new_equity','retained_earnings']:
                    req_after_tax_returns_savers_all_equity[legal_form][financing_source] = np.nan

                # Typical equity mix
                elif financing_source == 'typical_equity':
                    req_after_tax_returns_savers_all_equity[legal_form]['typical_equity'] = (
                        req_after_tax_returns_savers_all_equity['c_corp']['typical_equity']
                    )

        return req_after_tax_returns_savers_all_equity


    def _calc_req_after_tax_returns_savers_debt(self,
                                                c_corp_debt_account_category_shares,
                                                pass_thru_debt_account_category_shares,
                                                ooh_debt_account_category_shares,
                                                ret_plan_holding_period,
                                                ret_plan_holding_period_changes,
                                                ret_plan_tax_rates,
                                                interest_inc_tax_rates,
                                                nominal_rate_of_return_debt,
                                                inflation_rate):
        """Calculate the after-tax rates of return required by savers on debt investments.

        Parameters
        ----------
        c_corp_debt_account_category_shares : dict
            Parameters defining account categories for C corp debt investments.
        pass_thru_debt_account_category_shares : dict
            Parameters defining account categories for pass-through debt investments.
        ooh_debt_account_category_shares : dict
            Parameters defining account categories for owner-occupied housing debt investments.
        ret_plan_holding_period : dict
            Parameters defining holding periods of assets held in retirement plans.
        ret_plan_holding_period_changes : dict
            Changes to baseline values of holding periods in retirement plans.
        ret_plan_tax_rates : dict
            Tax rates on assets held in retirement plans.
        interest_inc_tax_rates : dict
            Tax rates on interest income.
        nominal_rate_of_return_debt : np.float64
            Nominal rate of return on debt.
        inflation_rate : np.float64
            Inflation rate.

        Returns
        -------
        req_after_tax_returns_savers_debt : dict
            Dictionary with twelve arrays (three legal forms times four account categories) of
            after-tax rates of return required by savers on debt investments, each of which
            varies by year.

        """
        # Set up dictionaries
        req_after_tax_returns_savers_debt = {}
        req_after_tax_returns_savers_debt['c_corp'] = {}
        req_after_tax_returns_savers_debt['pass_thru'] = {}
        req_after_tax_returns_savers_debt['ooh'] = {}

        debt_account_category_shares = {
            'c_corp': c_corp_debt_account_category_shares,
            'pass_thru': pass_thru_debt_account_category_shares,
            'ooh' : ooh_debt_account_category_shares
        }

        # C corps
        #---------------------------------------------------------------------------------
        for account_category in ['taxable','deferred','nontaxable']:

            # Taxable accounts
            if account_category == 'taxable':
                req_after_tax_returns_savers_debt['c_corp'][account_category] = (
                    nominal_rate_of_return_debt
                    * (1.0 - interest_inc_tax_rates['biz'])
                    - inflation_rate
                )

            # Tax deferred and non-taxable accounts
            elif account_category in ['deferred', 'nontaxable']:
                req_after_tax_returns_savers_debt['c_corp'][account_category] = (
                    self._calc_req_after_tax_returns_savers_deferred_assets(nominal_rate_of_return_debt - inflation_rate,
                                                                            inflation_rate,
                                                                            ret_plan_holding_period[account_category]
                                                                            + ret_plan_holding_period_changes[account_category],
                                                                            ret_plan_tax_rates[account_category])
            )

        # Pass-throughs
        #---------------------------------------------------------------------------------
        req_after_tax_returns_savers_debt['pass_thru'] = copy.deepcopy(req_after_tax_returns_savers_debt['c_corp'])

        # Owner-occupied housing
        #---------------------------------------------------------------------------------
        for account_category in ['taxable','deferred','nontaxable']:

            # Taxable accounts
            if account_category == 'taxable':
                req_after_tax_returns_savers_debt['ooh'][account_category] = (
                    nominal_rate_of_return_debt
                    * (1.0 - interest_inc_tax_rates['ooh'])
                    - inflation_rate
                )

            # Tax deferred and non-taxable accounts
            elif account_category in ['deferred', 'nontaxable']:
                req_after_tax_returns_savers_debt['ooh'][account_category] = (
                    req_after_tax_returns_savers_debt['c_corp'][account_category]
                )

        # Typical accounts for C Corps, pass-throughs and owner-occupied housing
        #---------------------------------------------------------------------------------
        for legal_form in ['c_corp','pass_thru','ooh']:
            req_after_tax_returns_savers_debt[legal_form]['typical'] = (
                (req_after_tax_returns_savers_debt[legal_form]['taxable']
                * debt_account_category_shares[legal_form]['taxable'])
                + (req_after_tax_returns_savers_debt[legal_form]['deferred']
                * debt_account_category_shares[legal_form]['deferred'])
                + (req_after_tax_returns_savers_debt[legal_form]['nontaxable']
                * debt_account_category_shares[legal_form]['nontaxable'])
        )

        return req_after_tax_returns_savers_debt


    def _fill_req_after_tax_returns_savers_array(self,
                                                 req_after_tax_returns_savers_equity,
                                                 req_after_tax_returns_savers_debt):
        """Fill the array of after-tax rates of return required by savers on equity
        and debt investments with values self._calc_req_after_tax_returns_savers_all_equity()
        and calculated in self._calc_req_after_tax_returns_savers_debt().

        Parameters
        ----------
        req_after_tax_returns_savers_equity : dict
            After-tax rates of return required by savers on equity investments.
        req_after_tax_returns_savers_debt : dict
            After-tax rates of return required by savers on debt investments.

        Returns
        -------
        req_after_tax_returns_savers : np.ndarray
            Array of after-tax rates of return required by savers, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 LEN_ACCOUNT_CATEGORIES,
                 NUM_YEARS]

        """
        # Store returns to savers on equity and debt investments into dictionary
        req_returns_savers = {
                'equity' : req_after_tax_returns_savers_equity,
                'debt' : req_after_tax_returns_savers_debt
        }

        # Initialize array for returns to savers
        req_after_tax_returns_savers = np.zeros((NUM_INDS,
                                                 NUM_ASSETS,
                                                 NUM_FOR_PROFIT_LEGAL_FORMS,
                                                 NUM_FINANCING_SOURCES,
                                                 LEN_ACCOUNT_CATEGORIES,
                                                 NUM_YEARS))
        req_after_tax_returns_savers[:] = np.nan

        # Fill in array for returns to savers
        #---------------------------------------------------------------------------------
        for legal_form in ['c_corp','pass_thru','ooh']:
            for financing_source in ['new_equity','retained_earnings','typical_equity','debt']:
                for account_category in ACCOUNT_CATEGORIES:

                    # Equity
                    if ((legal_form == 'c_corp' and financing_source in ['new_equity','retained_earnings'])
                    or financing_source == 'typical_equity'):
                        req_after_tax_returns_savers[:NUM_INDS,
                                                     :NUM_ASSETS,
                                                     LEGAL_FORMS[legal_form],
                                                     FINANCING_SOURCES[financing_source],
                                                     ACCOUNT_CATEGORIES[account_category],
                                                     :NUM_YEARS] = (
                                                         self._expand_array(req_returns_savers['equity']
                                                                                              [legal_form]
                                                                                              [financing_source]
                                                                                              [account_category],
                                                                            NUM_INDS, NUM_ASSETS)
                        )

                    # Debt
                    elif financing_source == 'debt':
                        req_after_tax_returns_savers[:NUM_INDS,
                                                     :NUM_ASSETS,
                                                     LEGAL_FORMS[legal_form],
                                                     FINANCING_SOURCES[financing_source],
                                                     ACCOUNT_CATEGORIES[account_category],
                                                     :NUM_YEARS] = (
                             self._expand_array(req_returns_savers['debt']
                                                                  [legal_form]
                                                                  [account_category],
                                                NUM_INDS, NUM_ASSETS)
                        )

        return req_after_tax_returns_savers


    def _calc_NID_flows(self,
                        c_corp_deduction_tax_rates_adjusted,
                        pass_thru_deduction_tax_rates_adjusted,
                        interest_deductible_shares,
                        seca_deduction_tax_rates_adjusted,
                        mortg_interest_deduction,
                        nominal_rates_of_return_debt):
        """Calculate net interest deduction (NID) flows.

        The net interest flow that is deductible in each year accounts for the
        rate of return on debt investments, the share of deductible interest, and the
        tax rate that applies to that interest deduction.

        Parameters
        ----------
        c_corp_deduction_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on C corp deductions.
        pass_thru_deduction_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on pass-through deductions.
        interest_deductible_shares : dict
            Shares of deductible interest across businesses (C corps and pass-throughs).
        seca_deduction_tax_rates_adjusted : np.ndarray
            Adjusted SECA tax rates on deductions.
        mortg_interest_deduction : dict
            Mortgage interest deduction parameters (tax rates and shares deductible).
        nominal_rates_of_return_debt : np.ndarray
            Nominal rates of return to debt, by year.

        Returns
        -------
        NID_flows : np.ndarray
            Array of net interest deduction flows, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        NID_flows = np.zeros((NUM_INDS,
                              NUM_ASSETS,
                              NUM_FOR_PROFIT_LEGAL_FORMS,
                              NUM_FINANCING_SOURCES,
                              NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Nominal rates of return on debt
        nominal_rates_of_return_debt = self._expand_array(nominal_rates_of_return_debt,
                                                          NUM_INDS, NUM_ASSETS)

        # Businesses' shares of business interest expenses that are deductible
        c_corp_interest_deductible_shares = self._expand_array(interest_deductible_shares['c_corp'],
                                                               NUM_INDS, NUM_ASSETS)
        pass_thru_interest_deductible_shares = self._expand_array(interest_deductible_shares['pass_thru'],
                                                                  NUM_INDS, NUM_ASSETS)

        # Mortgage interest deductions parameters
        mortg_interest_deduction_tax_rates = self._expand_array(mortg_interest_deduction['tax_rates'],
                                                                NUM_INDS, NUM_ASSETS)
        mortg_interest_deduction_deductible_shares = self._expand_array(mortg_interest_deduction['deductible_shares'],
                                                                        NUM_INDS, NUM_ASSETS)

        # Calculate NID flows
        #---------------------------------------------------------------------------------
        # C Corps
        NID_flows[:NUM_INDS, :NUM_ASSETS, LEGAL_FORMS['c_corp'], FINANCING_SOURCES['debt'], :NUM_YEARS] = (
            nominal_rates_of_return_debt
            * c_corp_interest_deductible_shares
            * c_corp_deduction_tax_rates_adjusted[:NUM_INDS, :NUM_ASSETS, FINANCING_SOURCES['debt'], :NUM_YEARS]
        )

        # Pass-throughs
        NID_flows[:NUM_INDS, :NUM_ASSETS, LEGAL_FORMS['pass_thru'], FINANCING_SOURCES['debt'], :NUM_YEARS] = (
            nominal_rates_of_return_debt
            * pass_thru_interest_deductible_shares
            * (pass_thru_deduction_tax_rates_adjusted[:NUM_INDS, :NUM_ASSETS, FINANCING_SOURCES['debt'], :NUM_YEARS]
            + seca_deduction_tax_rates_adjusted[:NUM_INDS, :NUM_ASSETS, FINANCING_SOURCES['debt'], :NUM_YEARS])
        )

        # Owner-occupied housing
        NID_flows[OOH_IND, ALL_OOH_ASSETS, LEGAL_FORMS['ooh'], FINANCING_SOURCES['debt'], :NUM_YEARS] = (
            nominal_rates_of_return_debt[OOH_IND, ALL_OOH_ASSETS, :NUM_YEARS]
            * mortg_interest_deduction_deductible_shares[OOH_IND, ALL_OOH_ASSETS, :NUM_YEARS]
            * mortg_interest_deduction_tax_rates[OOH_IND, ALL_OOH_ASSETS, :NUM_YEARS]
        )

        return NID_flows


    def _fill_real_discount_rates(self,
                                  req_after_tax_returns_savers,
                                  real_rates_of_return,
                                  NID_flows):
        """Fill array with real discount rates, which account for net interest deduction flows.

        Parameters
        ----------
        req_after_tax_returns_savers : np.ndarray
            After-tax rates of return required by savers.
        real_rates_of_return : dict
            Real rates of return on equity and debt investments.
        NID_flows : np.ndarray
            Net interest deductions flows.

        Returns
        -------
        real_discount_rates : np.ndarray
            Array of real discount rates, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        #---------------------------------------------------------------------------------
        real_discount_rates = np.zeros((NUM_INDS,
                                        NUM_ASSETS,
                                        NUM_FOR_PROFIT_LEGAL_FORMS,
                                        NUM_FINANCING_SOURCES,
                                        NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Adjustments to nominal rate of return on debt
        real_rates_of_return_equity = self._expand_array(real_rates_of_return['equity'],
                                                         NUM_INDS, NUM_ASSETS, NUM_EQUITY)
        real_rates_of_return_debt = self._expand_array(real_rates_of_return['debt'],
                                                       NUM_INDS, NUM_ASSETS)

        # Build arrays of real discount rates
        #---------------------------------------------------------------------------------
        # C corps
        #---------------------------------------------------------------------------------
        # Equity
        real_discount_rates[:NUM_INDS, :NUM_ASSETS, LEGAL_FORMS['c_corp'], :NUM_EQUITY, :NUM_YEARS] = (
            real_rates_of_return_equity
        )

        # Debt
        real_discount_rates[:NUM_INDS, :NUM_ASSETS, LEGAL_FORMS['c_corp'], FINANCING_SOURCES['debt'], :NUM_YEARS] = (
            real_rates_of_return_debt
        )

        # Pass-throughs
        #---------------------------------------------------------------------------------
        # Equity
        real_discount_rates[:NUM_INDS,
                            :NUM_ASSETS,
                            LEGAL_FORMS['pass_thru'],
                            FINANCING_SOURCES['typical_equity'],
                            :NUM_YEARS] = (
                                 req_after_tax_returns_savers[:NUM_INDS,
                                                              :NUM_ASSETS,
                                                              LEGAL_FORMS['c_corp'],
                                                              FINANCING_SOURCES['typical_equity'],
                                                              ACCOUNT_CATEGORIES['typical'],
                                                              :NUM_YEARS]
        )

        # Debt
        real_discount_rates[:NUM_INDS,
                            :NUM_ASSETS,
                            LEGAL_FORMS['pass_thru'],
                            FINANCING_SOURCES['debt'],
                            :NUM_YEARS] = real_rates_of_return_debt

        # Owner-occupied housing
        #---------------------------------------------------------------------------------
        # Equity
        real_discount_rates[OOH_IND,
                            :NUM_ASSETS,
                            LEGAL_FORMS['ooh'],
                            FINANCING_SOURCES['typical_equity'],
                            :NUM_YEARS] = (
                                 req_after_tax_returns_savers[OOH_IND,
                                                              :NUM_ASSETS,
                                                              LEGAL_FORMS['c_corp'],
                                                              FINANCING_SOURCES['typical_equity'],
                                                              ACCOUNT_CATEGORIES['typical'],
                                                              :NUM_YEARS]
        )

        # Debt
        real_discount_rates[OOH_IND,
                            :NUM_ASSETS,
                            LEGAL_FORMS['ooh'],
                            FINANCING_SOURCES['debt'],
                            :NUM_YEARS] = real_rates_of_return_debt[OOH_IND, :NUM_ASSETS, :NUM_YEARS]

        # Calculate real discount rates
        #---------------------------------------------------------------------------------
        real_discount_rates = real_discount_rates - NID_flows

        return real_discount_rates


    def _calc_nominal_discount_rates(self,
                                     detailed_industry_weights,
                                     req_after_tax_returns_savers,
                                     c_corp_tax_rates,
                                     pass_thru_tax_rates,
                                     biz_inc_tax_rate_adjustments,
                                     interest_deductible_shares,
                                     mortg_interest_deduction,
                                     nominal_rates_of_return,
                                     inflation_rate):
        """Builds the array of nominal discount rates, used in the calculation of the present
        value (PV) of depreciation deductions.

        Parameters
        ----------
        detailed_industry_weights : np.ndarray
            Detailed industry weights.
        req_after_tax_returns_savers : np.ndarray
            Required rates of return to savers.
        c_corp_tax_rates : np.ndarray
            Marginal tax rates on C corp income.
        pass_thru_tax_rates : np.ndarray
            Marginal tax rates on pass-through income.
        biz_inc_tax_rate_adjustments : dict
            Adjustments to marginal tax rates on business income (C corps and pass-throughs).
        interest_deductible_shares : dict
            Shares of deductible interest across businesses (C corps and pass-throughs).
        mortg_interest_deduction : dict
            Home mortgage interest deduction parameters (tax rates and shares  deductible).
        nominal_rates_of_return : np.ndarray
            Nominal rates of return (by year) on equity and debt.
        inflation_rate : np.float64
            Inflation rate.

        Returns
        -------
        nominal_discount_rates : np.ndarray
            Array of nominal discount rates, with dimnension:
                [NUM_DETAILED_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize arrays
        #---------------------------------------------------------------------------------
        # Array for NID shield
        taxshields = np.zeros((NUM_DETAILED_INDS,
                               NUM_ASSETS,
                               NUM_FOR_PROFIT_LEGAL_FORMS,
                               NUM_FINANCING_SOURCES,
                               NUM_YEARS))

        # Array for rates
        nominal_discount_rates = np.zeros((NUM_DETAILED_INDS,
                                           NUM_ASSETS,
                                           NUM_FOR_PROFIT_LEGAL_FORMS,
                                           NUM_FINANCING_SOURCES,
                                           NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Nominal rates of return on equity and debt
        nominal_rates_of_return_equity = self._expand_array(nominal_rates_of_return['equity'],
                                                            NUM_DETAILED_INDS, NUM_ASSETS, NUM_EQUITY)
        nominal_rates_of_return_debt = self._expand_array(nominal_rates_of_return['debt'],
                                                          NUM_DETAILED_INDS, NUM_ASSETS)

        # Returns to savers
        req_after_tax_returns_savers = self._expand_industry(req_after_tax_returns_savers, detailed_industry_weights)

        # Businesses' tax rate parameters
        c_corp_tax_rates = self._expand_array(c_corp_tax_rates,
                                              NUM_DETAILED_INDS, NUM_ASSETS)
        pass_thru_tax_rates = self._expand_array(pass_thru_tax_rates,
                                                 NUM_DETAILED_INDS, NUM_ASSETS)

        # Businesses' shares of deductible interest
        c_corp_interest_deductible_shares = self._expand_array(interest_deductible_shares['c_corp'],
                                                               NUM_DETAILED_INDS, NUM_ASSETS)
        pass_thru_interest_deductible_shares = self._expand_array(interest_deductible_shares['pass_thru'],
                                                                  NUM_DETAILED_INDS, NUM_ASSETS)

        # Mortgage interest deductions parameters
        mortg_interest_deduction_tax_rates = self._expand_array(mortg_interest_deduction['tax_rates'],
                                                                NUM_ASSETS)
        mortg_interest_deduction_deductible_shares = self._expand_array(mortg_interest_deduction['deductible_shares'],
                                                                        NUM_ASSETS)

        # Calculate nominal discount rates
        #---------------------------------------------------------------------------------
        # C corps equity
        nominal_discount_rates[:NUM_DETAILED_INDS,
                               :NUM_ASSETS,
                               LEGAL_FORMS['c_corp'],
                               :NUM_EQUITY,
                               :NUM_YEARS] =  nominal_rates_of_return_equity

        # Pass-through equity
        nominal_discount_rates[:NUM_DETAILED_INDS,
                               :NUM_ASSETS,
                               LEGAL_FORMS['pass_thru'],
                               FINANCING_SOURCES['typical_equity'],
                               :NUM_YEARS] = (
                                    req_after_tax_returns_savers[:NUM_DETAILED_INDS,
                                                                 :NUM_ASSETS,
                                                                 LEGAL_FORMS['pass_thru'],
                                                                 FINANCING_SOURCES['typical_equity'],
                                                                 ACCOUNT_CATEGORIES['typical'],
                                                                 :NUM_YEARS]
                                    + inflation_rate
        )

        # C corps debt
        nominal_discount_rates[:NUM_DETAILED_INDS,
                               :NUM_ASSETS,
                               LEGAL_FORMS['c_corp'],
                               FINANCING_SOURCES['debt'],
                               :NUM_YEARS] = nominal_rates_of_return_debt
        taxshields[:NUM_DETAILED_INDS,
                   :NUM_ASSETS,
                   LEGAL_FORMS['c_corp'],
                   FINANCING_SOURCES['debt'],
                   :NUM_YEARS] = (
                        nominal_rates_of_return_debt
                        * c_corp_interest_deductible_shares
                        * c_corp_tax_rates
                        * biz_inc_tax_rate_adjustments['c_corp']
        )

        # Pass-through debt
        nominal_discount_rates[:NUM_DETAILED_INDS,
                               :NUM_ASSETS,
                               LEGAL_FORMS['pass_thru'],
                               FINANCING_SOURCES['debt'],
                               :NUM_YEARS] = nominal_rates_of_return_debt
        taxshields[:NUM_DETAILED_INDS,
                   :NUM_ASSETS,
                   LEGAL_FORMS['pass_thru'],
                   FINANCING_SOURCES['debt'],
                   :NUM_YEARS] = (
                        nominal_rates_of_return_debt
                        * pass_thru_interest_deductible_shares
                        * pass_thru_tax_rates
                        * biz_inc_tax_rate_adjustments['pass_thru']
                        )

        # Owner-occupied housing, equity
        nominal_discount_rates[OOH_IND_DETAILED,
                               :NUM_ASSETS,
                               LEGAL_FORMS['ooh'],
                               FINANCING_SOURCES['typical_equity'],
                               :NUM_YEARS] = (
                                    req_after_tax_returns_savers[OOH_IND_DETAILED,
                                                                 :NUM_ASSETS,
                                                                 LEGAL_FORMS['ooh'],
                                                                 FINANCING_SOURCES['typical_equity'],
                                                                 ACCOUNT_CATEGORIES['typical'],
                                                                 :NUM_YEARS]
                                    + inflation_rate
        )

        # Owner-occupied housing, debt
        nominal_discount_rates[OOH_IND_DETAILED,
                               :NUM_ASSETS,
                               LEGAL_FORMS['ooh'],
                               FINANCING_SOURCES['debt'],
                               :NUM_YEARS] = nominal_rates_of_return_debt[OOH_IND_DETAILED,
                                                                          :NUM_ASSETS,
                                                                          :NUM_YEARS]
        taxshields[OOH_IND_DETAILED,
                   :NUM_ASSETS,
                   LEGAL_FORMS['ooh'],
                   FINANCING_SOURCES['debt'],
                   :NUM_YEARS] =  (
                        nominal_rates_of_return_debt[OOH_IND_DETAILED, :NUM_ASSETS, :NUM_YEARS]
                        * mortg_interest_deduction_deductible_shares
                        * mortg_interest_deduction_tax_rates
        )

        # Subtract tax shields from nominal discount rates
        nominal_discount_rates = nominal_discount_rates - taxshields

        return nominal_discount_rates


    def _calc_expens_shares(self,
                            c_corp_sec_179_expens_shares,
                            pass_thru_sec_179_expens_shares,
                            other_expens_shares):
        """Calculate expensing shares by detailed industry, asset type, legal form
        and year when accounting for Section 179 expensing and other expensing.

        Parameters
        ----------
        c_corp_sec_179_expens_shares : np.ndarray
            C corp Section 179 expensing shares.
        pass_thru_sec_179_expens_shares : np.ndarray
            Pass-through Section 179 expensing shares.
        other_expens_shares : np.ndarray
            Other expensing shares.

        Returns
        -------
        expens_shares : np.ndarray
            Array of expensing shares, with dimensions:
                [NUM_DETAILED_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_YEARS]

        """
        # Initialize array
        expens_shares = np.zeros((NUM_DETAILED_INDS,
                                  NUM_ASSETS,
                                  NUM_FOR_PROFIT_LEGAL_FORMS,
                                  NUM_YEARS))

        # Calculate expensing shares by legal form of organization
        expens_shares[:NUM_DETAILED_INDS, :NUM_ASSETS, LEGAL_FORMS['c_corp'], :NUM_YEARS] = (
            c_corp_sec_179_expens_shares
            + ((1 - c_corp_sec_179_expens_shares) * other_expens_shares)
        )

        expens_shares[:NUM_DETAILED_INDS, :NUM_ASSETS, LEGAL_FORMS['pass_thru'], :NUM_YEARS] = (
            pass_thru_sec_179_expens_shares
            + ((1 - pass_thru_sec_179_expens_shares) * other_expens_shares)
        )

        expens_shares[:NUM_DETAILED_INDS, :NUM_ASSETS, LEGAL_FORMS['ooh'], :NUM_YEARS] = other_expens_shares

        return expens_shares


    def _calc_depreciation_deduction_PVs(self,
                                         straight_line_flags,
                                         recovery_periods,
                                         acceleration_rates,
                                         econ_depreciation_detailed_industry,
                                         inflation_rate,
                                         inflation_adjustments,
                                         expens_shares,
                                         nominal_discount_rates,
                                         detailed_industry_weights):
        """
        Calculate array of present values (PVs) of depreciation deductions.

        Parameters
        ----------
        straight_line_flags : np.ndarray
            Flags for depreciation method (-1: economic depreciation,
                                            1: switch to straight line depreciation).
        recovery_periods : np.ndarray
            Recovery periods by industry and asset type.
        acceleration_rates : np.ndarray
            Acceleration rates by industry and asset type.
        econ_depreciation_detailed_industry : np.ndarray
            Economic depreciation rates by detailed industry and asset type
        inflation_rate : np.float64
            Inflation rate.
        inflation_adjustments : np.ndarray
            Inflation adjustments by industry and asset type.
        expens_shares : np.ndarray
            Expending shares, including 179 expensing and other expensing.
        nominal_discount_rates : np.ndarray
            Nominal discount rates.
        detailed_industry_weights : np.ndarray
            Detailed industry weights.

        Returns
        -------
        depreciation_deduction_PVs: np.ndarray
            Array of PVs of depreciation deductions, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Depreciation type flag
        depreciation_type = {'econ_depreciation' : -1,
                             'switch_to_straight_line_depreciation' : 1
                            }

        # Suppress RunTimeWarnings for division by zero or 0/0
        with np.errstate(divide='ignore', invalid='ignore'):

            # Geometric rate of decay: used if economic depreciation
            geometric_rate_of_decay0 = (
                np.where(straight_line_flags == depreciation_type['econ_depreciation'],
                         self._expand_array(econ_depreciation_detailed_industry, NUM_YEARS).transpose((1, 2, 0)),
                         np.where(recovery_periods > 0,
                                  acceleration_rates / recovery_periods,
                                  np.nan))
            )

            # Compute switching time array: used if switch to straight line depreciation
            years_before_switching_to_straight_line0 = (
                np.where(straight_line_flags == depreciation_type['switch_to_straight_line_depreciation'],
                         np.where(acceleration_rates > 0,
                                  recovery_periods * (1 - (1.0 / acceleration_rates)),
                                  np.nan),
                        300.0)
            )

            # Adjusted inflation rates
            adjusted_inflation_rates0 = inflation_rate * inflation_adjustments

            # Expand dimensions to match dimensions of array of nominal discount rates
            geometric_rate_of_decay = (
                self._expand_array(geometric_rate_of_decay0,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES)
                .transpose((2, 3, 0, 1, 4))
            )
            years_before_switching_to_straight_line = (
                self._expand_array(years_before_switching_to_straight_line0,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES)
                .transpose((2, 3, 0, 1, 4))
            )
            adjusted_inflation_rates = (
                self._expand_array(adjusted_inflation_rates0,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES)
                .transpose((2, 3, 0, 1, 4))
            )
            expens_shares = (
                self._expand_array(expens_shares,
                                   NUM_FINANCING_SOURCES)
                .transpose((1, 2, 3, 0, 4))
            )
            straight_line_flags = (
                self._expand_array(straight_line_flags,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES)
                .transpose((2, 3, 0, 1, 4))
            )
            econ_depreciation_detailed_industry = (
                self._expand_array(econ_depreciation_detailed_industry,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES, NUM_YEARS)
                .transpose((3, 4, 0, 1, 2))
            )
            recovery_periods = (
                self._expand_array(recovery_periods,
                                   NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES)
                .transpose((2, 3, 0, 1, 4))
            )

            # PV of economic depreciation
            PV_econ_depreciation_detailed_industry = (
                econ_depreciation_detailed_industry
                / (econ_depreciation_detailed_industry + nominal_discount_rates - adjusted_inflation_rates)
            )

            # PV of Modified Accelerated Cost Recovery System (MACRS) depreciation
            PV_tax_depreciation_detailed_industry = (
                (geometric_rate_of_decay
                 / (geometric_rate_of_decay + nominal_discount_rates - adjusted_inflation_rates)
                 * (1. - np.exp(-(geometric_rate_of_decay + nominal_discount_rates)
                 * years_before_switching_to_straight_line)))
                + np.exp(- geometric_rate_of_decay * years_before_switching_to_straight_line)
                * (np.exp(-nominal_discount_rates * years_before_switching_to_straight_line)
                - np.exp(-nominal_discount_rates * recovery_periods))
                / (nominal_discount_rates * (recovery_periods - years_before_switching_to_straight_line)))

            # PV of depreciation deductions by detailed industry
            depreciation_deduction_PVs_detailed_industry = (
                expens_shares
                + (1. - expens_shares)
                * np.where(straight_line_flags == depreciation_type['econ_depreciation'],
                           PV_econ_depreciation_detailed_industry,
                           PV_tax_depreciation_detailed_industry)
            )

            # PV of depreciation deductions by industry
            depreciation_deduction_PVs = self._combine_detailed_industry(depreciation_deduction_PVs_detailed_industry,
                                                                         detailed_industry_weights)

        return depreciation_deduction_PVs


    def _calc_capital_cost_recovery_shields(self,
                                           itc,
                                           c_corp_deduction_tax_rates_adjusted,
                                           pass_thru_deduction_tax_rates_adjusted,
                                           c_corp_credit_tax_rates_adjusted,
                                           pass_thru_credit_tax_rates_adjusted,
                                           seca_deduction_tax_rates_adjusted,
                                           ooh_tax_rates,
                                           depreciation_deduction_PVs):
        """Builds array of present value of tax shields from capital cost recovery.
        Includes present value of shields from depreciation deductions and from
        investment tax credit.

        Parameters
        ----------
        itc : dict
            Investment tax credit parameters (tax rates and non-depreciable bases).
        c_corp_deduction_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on C corp deductions.
        pass_thru_deduction_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on pass-through deductions.
        c_corp_credit_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on C corp tax credits.
        pass_thru_credit_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on pass-through tax credits.
        seca_deduction_tax_rates_adjusted : dict
            Adjusted SECA tax rates on deductions.
        ooh_tax_rates : np.ndarray
            Marginal tax rates on owner-occupied housing imputed rent.
        depreciation_deduction_PVs : np.ndarray
            Present value of depreciation deductions.

        Returns
        -------
        capital_cost_recovery_shields : np.ndarray
            Array of capital cost recovery shields, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        capital_cost_recovery_shields = np.zeros((NUM_INDS,
                                                  NUM_ASSETS,
                                                  NUM_FOR_PROFIT_LEGAL_FORMS,
                                                  NUM_FINANCING_SOURCES,
                                                  NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Investment tax credit parameters
        itc_rates = self._expand_array(itc['rates'], NUM_FINANCING_SOURCES).transpose((1, 2, 0, 3))
        itc_nondeprcbl_bases = self._expand_array(itc['nondeprcbl_bases'],
                                                  NUM_FINANCING_SOURCES).transpose((1, 2, 0, 3))

        # Tax rate parameters
        ooh_tax_rates = self._expand_array(ooh_tax_rates, NUM_FINANCING_SOURCES)

        # Compute present value of tax shield from capital cost recovery
        #---------------------------------------------------------------------------------
        # C corps
        capital_cost_recovery_shields[:NUM_INDS,
                                      :NUM_ASSETS,
                                      LEGAL_FORMS['c_corp'],
                                      :NUM_FINANCING_SOURCES,
                                      :NUM_YEARS] = (
                                              c_corp_credit_tax_rates_adjusted
                                              + ((1.0 - itc_rates * itc_nondeprcbl_bases)
                                              * depreciation_deduction_PVs[:NUM_INDS,
                                                                           :NUM_ASSETS,
                                                                           LEGAL_FORMS['c_corp'],
                                                                           :NUM_FINANCING_SOURCES,
                                                                           :NUM_YEARS]
                                              * c_corp_deduction_tax_rates_adjusted)
        )

        # Pass-through entities
        capital_cost_recovery_shields[:NUM_INDS,
                                      :NUM_ASSETS,
                                      LEGAL_FORMS['pass_thru'],
                                      :NUM_FINANCING_SOURCES,
                                      :NUM_YEARS] = (
                                          pass_thru_credit_tax_rates_adjusted
                                          + ((1.0 - itc_rates * itc_nondeprcbl_bases)
                                          * depreciation_deduction_PVs[:NUM_INDS,
                                                                       :NUM_ASSETS,
                                                                       LEGAL_FORMS['pass_thru'],
                                                                       :NUM_FINANCING_SOURCES,
                                                                       :NUM_YEARS]
                                          * (pass_thru_deduction_tax_rates_adjusted
                                             + seca_deduction_tax_rates_adjusted))
        )

        # Owner-occupied housing, if taxable
        capital_cost_recovery_shields[OOH_IND,
                                      ALL_OOH_ASSETS,
                                      LEGAL_FORMS['ooh'],
                                      :NUM_FINANCING_SOURCES,
                                      :NUM_YEARS] = (
                depreciation_deduction_PVs[OOH_IND,
                                           ALL_OOH_ASSETS,
                                           LEGAL_FORMS['ooh'],
                                           :NUM_FINANCING_SOURCES,
                                           :NUM_YEARS]
                * ooh_tax_rates
        )

        return capital_cost_recovery_shields


    def _calc_proportional_PV_gross_profits_after_tax_rates(self,
                                                            econ_depreciation,
                                                            c_corp_net_inc_tax_rates_adjusted,
                                                            pass_thru_net_inc_tax_rates_adjusted,
                                                            seca_net_inc_tax_rates_adjusted,
                                                            ooh_tax_rates,
                                                            avg_local_prop_tax_rate,
                                                            prop_tax_deduction,
                                                            real_discount_rates):
        """Builds array of proportional present value (PV) of the gross profits net of taxes.

        Parameters
        ----------
        econ_depreciation : np.ndarray
            Economic depreciation rates by industry and asset type.
        c_corp_net_inc_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on C corp net income.
        pass_thru_net_inc_tax_rates_adjusted : np.ndarray
            Adjusted marginal tax rates on pass-through net income.
        seca_net_inc_tax_rates_adjusted: dict
            Adjusted Self-Employed Contributions Act (SECA) tax rates.
        ooh_tax_rates : np.ndarray
            Marginal tax rates on imputed rent.
        avg_local_prop_tax_rate : np.float64
            Average local property tax rate.
        prop_tax_deduction : dict
            Property tax deduction parameters (tax rates and shares deductible).
        real_discount_rates : np.ndarray
            Real discount rates.

        Returns
        -------
        proportional_PV_gross_profits_after_tax_rates : np.ndarray
            Array of proportional present value of gross profits net of taxes,
            with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        proportional_PV_gross_profits_after_tax_rates = np.zeros((NUM_INDS,
                                                                  NUM_ASSETS,
                                                                  NUM_FOR_PROFIT_LEGAL_FORMS,
                                                                  NUM_FINANCING_SOURCES,
                                                                  NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Depreciation parameters
        econ_depreciation = self._expand_array(econ_depreciation,
                                               NUM_FINANCING_SOURCES, NUM_YEARS).transpose((2, 3, 0, 1))

        # Tax rate parameters
        ooh_tax_rates = self._expand_array(ooh_tax_rates,
                                           NUM_FINANCING_SOURCES - FINANCING_SOURCES['typical_equity'])

        # Property tax deductions parameters
        prop_tax_deduction_tax_rates = self._expand_array(prop_tax_deduction['tax_rates'],
                                                          NUM_FINANCING_SOURCES - FINANCING_SOURCES['typical_equity'])
        prop_tax_deduction_deductible_shares = self._expand_array(prop_tax_deduction['deductible_shares'],
                                                                  NUM_FINANCING_SOURCES - FINANCING_SOURCES['typical_equity'])

        # Compute array of proportional present value of the gross profits net of tax rate
        #---------------------------------------------------------------------------------
        # C corps
        proportional_PV_gross_profits_after_tax_rates[:NUM_INDS,
                                                      :NUM_ASSETS,
                                                      LEGAL_FORMS['c_corp'],
                                                      FINANCING_SOURCES['new_equity']:,
                                                      :NUM_YEARS] = (
                                                          (1.0
                                                           - c_corp_net_inc_tax_rates_adjusted[:NUM_INDS,
                                                                                               :NUM_ASSETS,
                                                                                               FINANCING_SOURCES['new_equity']:,
                                                                                               :NUM_YEARS])
                                                          / (real_discount_rates[:NUM_INDS,
                                                                                 :NUM_ASSETS,
                                                                                 LEGAL_FORMS['c_corp'],
                                                                                 FINANCING_SOURCES['new_equity']:,
                                                                                 :NUM_YEARS]
                                                             + econ_depreciation)
        )

        # Pass-throughs
        proportional_PV_gross_profits_after_tax_rates[:NUM_INDS,
                                                      :NUM_ASSETS,
                                                      LEGAL_FORMS['pass_thru'],
                                                      FINANCING_SOURCES['typical_equity']:,
                                                      :NUM_YEARS] = (
                                                          (1.0
                                                           - pass_thru_net_inc_tax_rates_adjusted[:NUM_INDS,
                                                                                                  :NUM_ASSETS,
                                                                                                  FINANCING_SOURCES['typical_equity']:,
                                                                                                  :NUM_YEARS]
                                                           - seca_net_inc_tax_rates_adjusted[:NUM_INDS,
                                                                                             :NUM_ASSETS,
                                                                                             FINANCING_SOURCES['typical_equity']:,
                                                                                             :NUM_YEARS])
                                                          / (real_discount_rates[:NUM_INDS,
                                                                                 :NUM_ASSETS,
                                                                                 LEGAL_FORMS['pass_thru'],
                                                                                 FINANCING_SOURCES['typical_equity']:,
                                                                                 :NUM_YEARS]
                                                             + econ_depreciation[:NUM_INDS,
                                                                                  :NUM_ASSETS,
                                                                                  FINANCING_SOURCES['typical_equity']:,
                                                                                  :NUM_YEARS])
        )

        # Owner-occupied housing
        # Exclude new equity and retained earnings from calculations for owner-occupied housing
        proportional_PV_gross_profits_after_tax_rates[OOH_IND,
                                                      ALL_OOH_ASSETS,
                                                      LEGAL_FORMS['ooh'],
                                                      FINANCING_SOURCES['typical_equity']:,
                                                      :NUM_YEARS] = (
                                                          (1.0 - ooh_tax_rates)
                                                          / (real_discount_rates[OOH_IND,
                                                                                 ALL_OOH_ASSETS,
                                                                                 LEGAL_FORMS['ooh'],
                                                                                 FINANCING_SOURCES['typical_equity']:,
                                                                                 :NUM_YEARS]
                                                             + (econ_depreciation[OOH_IND,
                                                                                   ALL_OOH_ASSETS,
                                                                                   FINANCING_SOURCES['typical_equity']:,
                                                                                   :NUM_YEARS]
                                                                * ooh_tax_rates)
                                                             - (avg_local_prop_tax_rate
                                                                * prop_tax_deduction_tax_rates
                                                                * prop_tax_deduction_deductible_shares
                                                                * (1.0 - ooh_tax_rates)))
        )

        return proportional_PV_gross_profits_after_tax_rates


    def _calc_req_before_tax_returns_biz_inventories(self,
                                                     detailed_industry_weights,
                                                     inventories_holding_period,
                                                     inventories_holding_period_changes,
                                                     biz_tax_rates_adjusted,
                                                     inflation_rate,
                                                     inflation_adjustments,
                                                     real_discount_rates):
        """Calculate the required before-tax rates of return for businesses' (C corps and
        pass-throughs) inventories.

        Parameters
        ----------
        detailed_industry_weights : np.ndarray
            Detailed industries weights.
        inventories_holding_period : np.float64
            Parameter defining inventories' baseline holding period.
        inventories_holding_period_changes : np.ndarray
            Changes to baseline values of inventories' holding period.
        biz_tax_rates_adjusted : dict
            Adjusted marginal tax rates on businesses' net income, tax deductions and tax credits.
        inflation_rate : np.float64
            Inflation rate.
        inflation_adjustments : np.ndarray
            Inflation adjustments by industry and asset type.
        real_discount_rates : np.ndarray
            Real discount rates.

        Returns
        -------
        req_before_tax_returns_business_inventories : np.ndarray
            Array of required before-tax rates of return for business inventories,
            with dimensions:
                [NUM_BIZ_INDS,
                 NUM_BIZ,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize arrays
        #---------------------------------------------------------------------------------
        cumulative_nominal_before_tax_rates_of_return = np.zeros((NUM_BIZ_INDS,
                                                                  NUM_BIZ,
                                                                  NUM_FINANCING_SOURCES,
                                                                  NUM_YEARS))

        req_before_tax_returns_biz_inventories = np.zeros((NUM_BIZ_INDS,
                                                           NUM_BIZ,
                                                           NUM_FINANCING_SOURCES,
                                                           NUM_YEARS))

        # Expand dimensions of arrays used in calculations
        #---------------------------------------------------------------------------------
        # Inflation adjustment parameters
        adjusted_inflation_rates = self._combine_detailed_industry(inflation_adjustments * inflation_rate,
                                                                   detailed_industry_weights)
        adjusted_inflation_rates = (
            self._expand_array(adjusted_inflation_rates,
                               NUM_BIZ, NUM_FINANCING_SOURCES)
            .transpose((2, 3, 0, 1, 4))
        )

        # Tax rates parameters
        adjusted_biz_income_tax_rates = (
            np.stack((biz_tax_rates_adjusted['c_corp']['net_inc'],
                      biz_tax_rates_adjusted['pass_thru']['net_inc']))
            .transpose((1, 2, 0, 3, 4))
        )

        # Inventories parameters
        inventories_holding_periods = self._expand_array(inventories_holding_period
                                                         + inventories_holding_period_changes,
                                                         NUM_INDS, NUM_BIZ, NUM_FINANCING_SOURCES)

        # Calculate required before-tax rates of return for business inventories
        #---------------------------------------------------------------------------------
        # Cumulative nominal before-tax rates of return on inventories
        cumulative_nominal_before_tax_rates_of_return = (
                np.log((np.exp(inventories_holding_periods[ALL_BIZ_INDS,
                                                           :NUM_BIZ,
                                                           :NUM_FINANCING_SOURCES,
                                                           :NUM_YEARS]
                              * (real_discount_rates[ALL_BIZ_INDS,
                                                     INDEX['Inventories'],
                                                     :NUM_BIZ,
                                                     :NUM_FINANCING_SOURCES,
                                                     :NUM_YEARS]
                              + adjusted_inflation_rates[ALL_BIZ_INDS,
                                                         INDEX['Inventories'],
                                                         :NUM_BIZ,
                                                         :NUM_FINANCING_SOURCES,
                                                         :NUM_YEARS]))
                        - adjusted_biz_income_tax_rates[ALL_BIZ_INDS,
                                                        INDEX['Inventories'],
                                                        :NUM_BIZ,
                                                        :NUM_FINANCING_SOURCES,
                                                        :NUM_YEARS])
                      / (1.0 - adjusted_biz_income_tax_rates[ALL_BIZ_INDS,
                                                             INDEX['Inventories'],
                                                             :NUM_BIZ,
                                                             :NUM_FINANCING_SOURCES,
                                                             :NUM_YEARS]))
        )

        # Required before-tax rates of return if non-zero holding period
        req_before_tax_returns_biz_inventories = (
            cumulative_nominal_before_tax_rates_of_return
            / inventories_holding_periods[ALL_BIZ_INDS,
                                          :NUM_BIZ,
                                          :NUM_FINANCING_SOURCES,
                                          :NUM_YEARS]
            - adjusted_inflation_rates[ALL_BIZ_INDS,
                                       INDEX['Inventories'],
                                       :NUM_BIZ,
                                       :NUM_FINANCING_SOURCES,
                                       :NUM_YEARS]
        )

        # Replace required before-tax rates of return with real discount rate if zero holding period
        req_before_tax_returns_biz_inventories = (
            np.where(inventories_holding_periods[ALL_BIZ_INDS,
                                                 :NUM_BIZ,
                                                 :NUM_FINANCING_SOURCES,
                                                 :NUM_YEARS]  == 0.0,
                     real_discount_rates[ALL_BIZ_INDS,
                                         INDEX['Inventories'],
                                         :NUM_BIZ,
                                         :NUM_FINANCING_SOURCES,
                                         :NUM_YEARS],
                     req_before_tax_returns_biz_inventories)
        )

        return req_before_tax_returns_biz_inventories


    def _calc_req_before_tax_returns_all(self,
                                         econ_depreciation,
                                         capital_cost_recovery_shields,
                                         proportional_PV_gross_profits_after_tax_rates,
                                         ooh_tax_rates,
                                         req_before_tax_returns_biz_inventories):
        """Calculate required before-tax rates of return.

        Parameters
        ----------
        econ_depreciation : np.ndarray
            Economic depreciation rates by industry and asset type.
        capital_cost_recovery_shields : np.ndarray
            Capital cost recovery shields.
        proportional_PV_gross_profits_after_tax_rates : np.ndarray
            Proportional present value of gross profits net of taxes.
        ooh_tax_rates : np.ndarray
            Marginal tax rates on imputed rent.
        req_before_tax_returns_biz_inventories : np.ndarray
            Required before-tax rates of return for business inventories.

        Returns
        -------
        req_before_tax_returns : np.ndarray
            Array of required before-tax rates of return, with dimensions:
                [NUM_INDS,
                 NUM_ASSETS,
                 NUM_FOR_PROFIT_LEGAL_FORMS,
                 NUM_FINANCING_SOURCES,
                 NUM_YEARS]

        """
        # Initialize array
        req_before_tax_returns = np.zeros((NUM_INDS,
                                           NUM_ASSETS,
                                           NUM_FOR_PROFIT_LEGAL_FORMS,
                                           NUM_FINANCING_SOURCES,
                                           NUM_YEARS))

        # Expand dimensions of depreciation parameters used in calculations
        econ_depreciation = (
            self._expand_array(econ_depreciation,
                               NUM_FOR_PROFIT_LEGAL_FORMS, NUM_FINANCING_SOURCES, NUM_YEARS)
            .transpose((3, 4, 0, 1, 2))
        )

        # Calculate required before-tax rates of return
        #---------------------------------------------------------------------------------
        # C corps and pass-throughs
        req_before_tax_returns[ALL_BIZ_INDS, :NUM_ASSETS, :NUM_BIZ, :NUM_FINANCING_SOURCES, :NUM_YEARS] = (
            (1.0 - capital_cost_recovery_shields[ALL_BIZ_INDS,
                                                 :NUM_ASSETS,
                                                 :NUM_BIZ,
                                                 :NUM_FINANCING_SOURCES,
                                                 :NUM_YEARS])
            / proportional_PV_gross_profits_after_tax_rates[ALL_BIZ_INDS,
                                                            :NUM_ASSETS,
                                                            :NUM_BIZ,
                                                            :NUM_FINANCING_SOURCES,
                                                            :NUM_YEARS]
            - econ_depreciation[ALL_BIZ_INDS,
                                :NUM_ASSETS,
                                :NUM_BIZ,
                                :NUM_FINANCING_SOURCES,
                                :NUM_YEARS]
        )

        # Owner-occupied housing
        req_before_tax_returns[OOH_IND, ALL_OOH_ASSETS, LEGAL_FORMS['ooh'], :NUM_FINANCING_SOURCES, :NUM_YEARS] = (
            (1.0 - capital_cost_recovery_shields[OOH_IND,
                                                 ALL_OOH_ASSETS,
                                                 LEGAL_FORMS['ooh'],
                                                 :NUM_FINANCING_SOURCES,
                                                 :NUM_YEARS])
            / proportional_PV_gross_profits_after_tax_rates[OOH_IND,
                                                            ALL_OOH_ASSETS,
                                                            LEGAL_FORMS['ooh'],
                                                            :NUM_FINANCING_SOURCES,
                                                            :NUM_YEARS]
            - econ_depreciation[OOH_IND,
                                ALL_OOH_ASSETS,
                                LEGAL_FORMS['ooh'],
                                :NUM_FINANCING_SOURCES,
                                :NUM_YEARS]
            * ooh_tax_rates
        )

        # Replace values
        #---------------------------------------------------------------------------------
        # Business inventories
        req_before_tax_returns[ALL_BIZ_INDS,
                               INDEX['Inventories'],
                               :NUM_BIZ,
                               :NUM_FINANCING_SOURCES,
                               :NUM_YEARS] = req_before_tax_returns_biz_inventories

        # New equity and retained earnings financing for pass-throughs and owner-occupied housing
        for legal_form in ['pass_thru', 'ooh']:
            for financing_source in ['new_equity', 'retained_earnings']:
                req_before_tax_returns[:NUM_INDS,
                                       :NUM_ASSETS,
                                       LEGAL_FORMS[legal_form],
                                       FINANCING_SOURCES[financing_source],
                                       :NUM_YEARS] = np.nan

        return req_before_tax_returns