import os
import sys
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from dateutil.relativedelta import *
import matplotlib.pyplot as plt
from IPython.core.pylabtools import figsize


sys.path = ["./"]+sys.path

import fingenerators as fingen


# ============================================================================
def convertcompounded(n,m,imc,returnstr=False):
    inc = n * ( (1 + imc/m) ** (m/n) -1 )
    if returnstr:
        inc = f'Effective x{n} rate of {imc} compounded x{m} is {inc}'
    return inc    


# ============================================================================
def plot_amort_balance(schedules,scenarios):
    """Plot the remaining  balance of all amortisation scenarios
    """
    figsize(12,8)
    fig, ax = plt.subplots(1, 1)
    for scenario in scenarios.keys():
        schedules[scenario].plot(x='Month', y='End Balance', label=f'{scenario}', ax=ax)
    plt.title("Repayment Timelines");
    plt.ylabel("Balance");


# ============================================================================
def plot_amort_annual_interest(schedules,scenarios, stats):
    """Plot the annual interest of all amortisation scenarios
    """
    ys = {}
    labels = {}
    header = {}
    for scenario in scenarios.keys():
        ys[scenario],labels[scenario],header[scenario] = df_annual_amort_interest(schedules[scenario], stats[scenario])

    dfai = pd.concat([ys[scenario] for scenario in ys.keys()], axis=1)
    dfai.columns = header.keys()

    figsize(12,8)
    fig, ax = plt.subplots(1, 1)
    for header in header.keys():
        dfai.plot(y=header, label=f'{header}', ax=ax)
    plt.legend([labels[scenario] for scenario in labels.keys()], loc=1, prop={'size':10})
    plt.title("Interest Payments");


# ============================================================================
def df_annual_amort_interest(schedule, stats):
    """Create a dataframe with annual amortisation interest totals, and a descriptive label
    """
    annint = schedule.set_index('Month')['Interest'].resample("A").sum().reset_index()
    annint["Year"] = annint["Month"].dt.year
    annint.set_index('Year', inplace=True)
    annint.drop('Month', 1, inplace=True)
    label="{} years at {}% with additional payment of {:.0f}".format(stats['BondYears'], stats['Interest Rate']*100, stats['AddPayment'])
    header = f'{stats["AddPayment"]}' 
    return annint, label, header



# ============================================================================
def calc_scenarios(scenarios,cyclesPerAnnum=12,paymentSign=1):
    """Given a scenario dictionary calculate bond schedules and statistics
    """
    schedules = {}
    stats = {}
    
    for scenario in scenarios.keys():
        if 'reqPayment' not in scenarios[scenario].keys():
            scenarios[scenario]['reqPayment'] = \
                paymentSign * round(np.pmt(scenarios[scenario]['intr'] / cyclesPerAnnum, 
                              scenarios[scenario]['years'] * cyclesPerAnnum, 
                              scenarios[scenario]['princ']), 2);
       
        schedules[scenario], stats[scenario] = fingen.amortisation_table(
                        scenarios[scenario]['princ'], 
                        scenarios[scenario]['intr'], 
                        scenarios[scenario]['years'], 
                        scenarios[scenario]['reqPayment'], 
                        scenarios[scenario]['addPayment'],
                        cyclesPerAnnum=12
                    );
    return schedules,stats





# ============================================================================
# to evaluate the tax benefits
def bondtaxsavingsanalysis(principal,interest_rate,bondyears,taxrate,rentpmonth,
                           increasepyear,cyclesPerAnnum=12,addpayment=0,addpayrate=0):
    """Calculate a monthly schedule and summary of tax benefit on bond loan
    """
    
    reqpayment = round(np.pmt(interest_rate/cyclesPerAnnum, bondyears*cyclesPerAnnum, principal), 2)

    # calculate the mortgage 
    df, stats = fingen.amortisation_table(
        principal=principal, 
        interest_rate=interest_rate, 
        bondyears=bondyears, 
        reqpayment = reqpayment,
        addpayment=addpayment,
        cyclesPerAnnum=cyclesPerAnnum, 
        start_date=date(2000, 1,1),
        addpayrate=addpayrate)

    numcycles = stats['Num Payments']
    rischedule = fingen.annIncreaseTable(value=rentpmonth, increasepyear=increasepyear, numcycles=numcycles)
    # Now merge the bond table with the rent income table
    dfc = df.copy().drop(["ReqPayment","AddPayment","Begin Balance"],axis=1)
    dfc = dfc.merge(rischedule.drop(["Month"],axis=1), on='Period')
    
    # number of payments
    dfc['NumPay'] = stats['Num Payments']
    
    # save tax for later
    dfc['TaxRate'] = taxrate
    
    # tax and net income if **NO** bond present
    dfc['TaxNoInter'] = - taxrate * (dfc['Rent'])
    # can't get tax back
    dfc['TaxNoInter'][dfc['TaxNoInter'] > 0] = 0
    dfc['IncomeNoInter'] = dfc['Rent'] + dfc['TaxNoInter']

    # tax and net income if bond present
    dfc['TaxWithInter'] = - taxrate * (dfc['Rent'] + dfc['Interest'])
    # can't get tax back
    dfc['TaxWithInter'][dfc['TaxWithInter'] > 0] = 0
    dfc['IncomeWithInter'] = dfc['Rent'] + dfc['TaxWithInter']

    # net benefit
    dfc['BondBenefit'] = dfc['IncomeWithInter'] - dfc['IncomeNoInter']

    #Create a summary statistics table
    nistats = pd.Series([stats['Principal'],stats['Interest Rate'],
                         stats['ReqPayment'],stats['AddPayment'],dfc["Period"].count(),
                         rentpmonth,  increasepyear,
                         taxrate,
                         dfc["Rent"].sum(),
                         dfc["TaxNoInter"].sum(),
                         dfc["IncomeNoInter"].sum(),
                         dfc["TaxWithInter"].sum(),
                         dfc["IncomeWithInter"].sum(),
                         dfc["BondBenefit"].sum(),
                         100 * dfc["BondBenefit"].sum()/dfc["Rent"].sum(),
                        ],
                       index=["Bond","Interest Rate",
                              "ReqPayment","AddPayment","Num Payments",
                              "InitRent",  "RentIncrease",
                              "TaxRate",
                              "Total Rent",
                              "TaxNoInter",
                              "IncomeNoInter",
                              "TaxWithInter",
                              "IncomeWithInter",
                              "BondBenefit",
                              "Benefit/Rent %",
                             ])

    if False:
        figsize(12,8)
        fig, ax = plt.subplots(1, 1)
        # for scenario in scenarios.keys():
        #     schedules[scenario].plot(x='Month', y='End Balance', label=f'{scenario}', ax=ax)
        dfc.plot(x='Month',y='Rent', label='Rent', ax=ax)    
        dfc.plot(x='Month',y='Interest', label='Interest', ax=ax)    
        dfc.plot(x='Month',y='TaxNoInter', label='TaxNoInter', ax=ax)    
        dfc.plot(x='Month',y='TaxWithInter', label='TaxWithInter', ax=ax)    
        plt.title("Repayment Timelines");
        plt.ylabel("Value");
        plt.xlabel("Time");
        
    return dfc,nistats


